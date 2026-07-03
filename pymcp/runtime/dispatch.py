"""Transport-agnostic JSON-RPC dispatcher."""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from typing import Awaitable, Protocol

from fastapi import FastAPI

from ..observability.logging import get_logger
from ..protocol.errors import MCPErrorCode, build_error_response
from ..protocol.meta import MetaValidationError, validate_request_meta
from ..protocol.metadata import RequestMetadataError, require_request_metadata
from ..protocol.validate import validate_jsonrpc_request
from ..security.authn import Principal
from ..security.authz import AuthorizationError, build_authz_request
from ..session.store import SessionManager, get_session_manager
from ..session.types import Session, SessionState
from .processors import (
    SessionJsonRpcMessageProcessor,
    SessionMessageProcessor,
    StatelessJsonRpcMessageProcessor,
    StatelessMessageProcessor,
)
from .protocol_context import (
    RuntimeServices,
    build_session_dispatch_context,
    build_stateless_dispatch_context,
    resolve_protocol_revision,
)
from .handlers.registry import get_registered_handlers
from .types import DispatchContext, DispatchResponse, DispatchResult, JSONObject

# Side-effect imports register built-in handlers.
from .handlers import completions as _completions  # noqa: F401
from .handlers import lifecycle as _lifecycle  # noqa: F401
from .handlers import discovery as _discovery  # noqa: F401
from .handlers import logging as _logging  # noqa: F401
from .handlers import prompts as _prompts  # noqa: F401
from .handlers import resources as _resources  # noqa: F401
from .handlers import roots as _roots  # noqa: F401
from .handlers import tasks as _tasks  # noqa: F401
from .tools import handlers as _tools  # noqa: F401


logger = get_logger(__name__)

_PRE_INIT_ALLOWED = frozenset({"initialize"})
_POST_INIT_ALLOWED = frozenset({"initialize", "notifications/initialized", "ping"})


class DispatchError(Exception):
    def __init__(
        self,
        *,
        status: int,
        code: int,
        message: str,
        rpc_id,
        require_id: bool = True,
        data=None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.rpc_id = rpc_id
        self.require_id = require_id
        self.data = data


def _rpc_id_from_data(data: JSONObject):
    raw_id = data.get("id")
    if raw_id is None or (isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool)):
        return raw_id
    return None


class DispatchNext(Protocol):
    def __call__(self, ctx: DispatchContext) -> Awaitable[DispatchResponse]:
        ...


class DispatchMiddleware(Protocol):
    async def __call__(self, ctx: DispatchContext, call_next: DispatchNext) -> DispatchResponse:
        ...


class ErrorBoundaryMiddleware:
    async def __call__(self, ctx: DispatchContext, call_next: DispatchNext) -> DispatchResponse:
        try:
            return await call_next(ctx)
        except Exception:
            logger.exception("Unhandled exception in dispatch pipeline for method %s", ctx.method)
            payload = build_error_response(
                ctx.rpc_id if "id" in ctx.data else None,
                MCPErrorCode.INTERNAL_ERROR,
                "Internal error",
            )
            await ctx.maybe_enqueue(payload)
            return DispatchResponse(status=200, json=True, payload=payload)


class InitGateMiddleware:
    def __init__(
        self,
        *,
        pre_init_allowed: AbstractSet[str],
        post_init_allowed: AbstractSet[str],
    ):
        self._pre_init_allowed = frozenset(pre_init_allowed)
        self._post_init_allowed = frozenset(post_init_allowed)

    async def __call__(self, ctx: DispatchContext, call_next: DispatchNext) -> DispatchResponse:
        if ctx.protocol_revision is not None and ctx.protocol_revision.stateless:
            return await call_next(ctx)
        state = ctx.session.lifecycle_state
        if state == SessionState.CLOSED:
            payload = build_error_response(ctx.rpc_id, MCPErrorCode.SESSION_NOT_FOUND, "Session is closed")
            await ctx.maybe_enqueue(payload)
            return DispatchResponse(status=404, json=True, payload=payload)
        if state == SessionState.WAIT_INIT and ctx.method not in self._pre_init_allowed:
            payload = build_error_response(ctx.rpc_id, MCPErrorCode.INVALID_REQUEST, "server not initialized.")
            await ctx.maybe_enqueue(payload)
            return DispatchResponse(status=200, json=True, payload=payload)
        if state == SessionState.WAIT_INITIALIZED and ctx.method not in self._post_init_allowed:
            payload = build_error_response(ctx.rpc_id, MCPErrorCode.INVALID_REQUEST, "server not initialized.")
            await ctx.maybe_enqueue(payload)
            return DispatchResponse(status=200, json=True, payload=payload)
        if state == SessionState.READY and ctx.method == "initialize":
            payload = build_error_response(ctx.rpc_id, MCPErrorCode.INVALID_REQUEST, "server already initialized.")
            await ctx.maybe_enqueue(payload)
            return DispatchResponse(status=200, json=True, payload=payload)
        return await call_next(ctx)


class CapabilityGateMiddleware:
    _PREFIXES = (
        ("tools/", "tools"),
        ("prompts/", "prompts"),
        ("resources/", "resources"),
        ("tasks/", "tasks"),
        ("completion/", "completions"),
        ("logging/", "logging"),
    )

    async def __call__(self, ctx: DispatchContext, call_next: DispatchNext) -> DispatchResponse:
        for prefix, feature in self._PREFIXES:
            if ctx.method.startswith(prefix) and not ctx.supports(feature):
                payload = build_error_response(ctx.rpc_id, MCPErrorCode.METHOD_NOT_FOUND, f"{feature} not supported")
                await ctx.maybe_enqueue(payload)
                return DispatchResponse(status=200, json=True, payload=payload)
        return await call_next(ctx)


class RevisionMethodGateMiddleware:
    _STATELESS_UNSUPPORTED = frozenset(
        {
            "initialize",
            "notifications/initialized",
            "ping",
            "resources/subscribe",
            "resources/unsubscribe",
            "logging/setLevel",
        }
    )

    async def __call__(self, ctx: DispatchContext, call_next: DispatchNext) -> DispatchResponse:
        revision = ctx.protocol_revision
        if revision is not None and revision.stateless and ctx.method in self._STATELESS_UNSUPPORTED:
            payload = build_error_response(
                ctx.rpc_id,
                MCPErrorCode.METHOD_NOT_FOUND,
                f"Method not found: {ctx.method}",
            )
            await ctx.maybe_enqueue(payload)
            return DispatchResponse(status=200, json=True, payload=payload)
        if revision is not None and not revision.supports_discovery and ctx.method == "server/discover":
            payload = build_error_response(
                ctx.rpc_id,
                MCPErrorCode.METHOD_NOT_FOUND,
                f"Method not found: {ctx.method}",
            )
            await ctx.maybe_enqueue(payload)
            return DispatchResponse(status=200, json=True, payload=payload)
        return await call_next(ctx)


class AuthorizationGateMiddleware:
    async def __call__(self, ctx: DispatchContext, call_next: DispatchNext) -> DispatchResponse:
        authorizer = getattr(getattr(ctx.app, "state", None), "authorizer", None)
        if not authorizer:
            return await call_next(ctx)

        params = ctx.data.get("params")
        params_dict = params if isinstance(params, dict) else None
        request = build_authz_request(rpc_method=ctx.method, params=params_dict)
        principal = ctx.session.principal
        try:
            authorizer.authorize(principal, request)
        except AuthorizationError as exc:
            payload = build_error_response(ctx.rpc_id, MCPErrorCode.FORBIDDEN, str(exc))
            await ctx.maybe_enqueue(payload)
            return DispatchResponse(status=200, json=True, payload=payload)
        return await call_next(ctx)


class Dispatcher:
    dispatch_error_type = DispatchError
    rpc_id_from_data = staticmethod(_rpc_id_from_data)

    def __init__(
        self,
        *,
        handlers: dict[str, object] | None = None,
        middlewares: list[DispatchMiddleware] | None = None,
    ) -> None:
        self._handlers = handlers
        self._middlewares = (
            middlewares
            if middlewares is not None
            else [
                ErrorBoundaryMiddleware(),
                InitGateMiddleware(
                    pre_init_allowed=_PRE_INIT_ALLOWED,
                    post_init_allowed=_POST_INIT_ALLOWED,
                ),
                RevisionMethodGateMiddleware(),
                CapabilityGateMiddleware(),
                AuthorizationGateMiddleware(),
            ]
        )

    @staticmethod
    def _validate_envelope(data: JSONObject) -> tuple[object, str]:
        rpc_id = _rpc_id_from_data(data)
        method = data.get("method")
        if data.get("jsonrpc") != "2.0" or not isinstance(method, str) or not method:
            raise DispatchError(
                status=200,
                code=MCPErrorCode.INVALID_REQUEST,
                message="Invalid JSON-RPC request",
                rpc_id=rpc_id if "id" in data else None,
            )
        return rpc_id, method

    @staticmethod
    def _validate_request(data: JSONObject) -> None:
        if "id" not in data:
            return
        ok, error_message = validate_jsonrpc_request(data)
        if not ok:
            raise DispatchError(
                status=200,
                code=MCPErrorCode.INVALID_REQUEST,
                message=error_message,
                rpc_id=_rpc_id_from_data(data) if "id" in data else None,
            )

    @staticmethod
    def _get_session(*, session_id: str, data: JSONObject, app: FastAPI) -> tuple[SessionManager, Session]:
        session_manager = get_session_manager(app)
        session = session_manager.get_session(session_id)
        if session is None:
            raise DispatchError(
                status=404,
                code=MCPErrorCode.SESSION_NOT_FOUND,
                message="Session not found",
                rpc_id=_rpc_id_from_data(data) if "id" in data else None,
            )
        return session_manager, session

    async def _call_handler(self, ctx: DispatchContext) -> DispatchResponse:
        handlers = self._handlers if self._handlers is not None else get_registered_handlers()
        handler = handlers.get(ctx.method)
        if handler is None:
            payload = build_error_response(ctx.rpc_id, MCPErrorCode.METHOD_NOT_FOUND, f"Method not found: {ctx.method}")
            await ctx.maybe_enqueue(payload)
            return DispatchResponse(status=200, json=True, payload=payload)
        return await handler.handle(ctx)

    async def _run_pipeline(self, ctx: DispatchContext) -> DispatchResponse:
        async def call_at(index: int, current: DispatchContext) -> DispatchResponse:
            if index >= len(self._middlewares):
                return await self._call_handler(current)
            middleware = self._middlewares[index]
            return await middleware(current, lambda next_ctx: call_at(index + 1, next_ctx))

        return await call_at(0, ctx)

    async def dispatch(
        self,
        *,
        session_id: str,
        data: JSONObject,
        app: FastAPI,
        direct_response: bool = False,
    ) -> DispatchResponse:
        session_manager, session = self._get_session(session_id=session_id, data=data, app=app)
        rpc_id, method = self._validate_envelope(data)
        self._validate_request(data)
        try:
            validate_request_meta(data)
        except MetaValidationError as exc:
            raise DispatchError(
                status=200,
                code=exc.code,
                message=str(exc),
                rpc_id=rpc_id if "id" in data else None,
            ) from exc

        server_settings = getattr(app.state, "server_settings", None)
        if server_settings is None:
            raise RuntimeError("app.state.server_settings is not set; initialize the app with create_app")

        services = RuntimeServices.from_app(app)
        ctx = build_session_dispatch_context(
            session_id=session_id,
            data=data,
            app=app,
            session=session,
            rpc_id=rpc_id,
            method=method,
            server_settings=server_settings,
            services=services,
            direct_response=direct_response,
        )
        return await self._run_pipeline(ctx)

    async def dispatch_stateless(
        self,
        *,
        data: JSONObject,
        app: FastAPI,
        principal: Principal | None = None,
        direct_response: bool = True,
    ) -> DispatchResponse:
        rpc_id, method = self._validate_envelope(data)
        self._validate_request(data)
        try:
            validate_request_meta(data)
            request_metadata = require_request_metadata(data)
        except MetaValidationError as exc:
            raise DispatchError(
                status=200,
                code=exc.code,
                message=str(exc),
                rpc_id=rpc_id if "id" in data else None,
            ) from exc
        except RequestMetadataError as exc:
            raise DispatchError(
                status=400,
                code=exc.code,
                message=str(exc),
                rpc_id=rpc_id if "id" in data else None,
            ) from exc

        server_settings = getattr(app.state, "server_settings", None)
        if server_settings is None:
            raise RuntimeError("app.state.server_settings is not set; initialize the app with create_app")

        revision = resolve_protocol_revision(request_metadata.protocol_version, server_settings)
        if revision is None:
            raise DispatchError(
                status=400,
                code=MCPErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
                message="Unsupported protocol version",
                rpc_id=rpc_id if "id" in data else None,
                data={
                    "supported": list(server_settings.protocol_versions),
                    "requested": request_metadata.protocol_version,
                },
            )
        if not revision.stateless:
            raise DispatchError(
                status=400,
                code=MCPErrorCode.INVALID_PARAMS,
                message="Invalid params: stateless request metadata requires a stateless protocol version",
                rpc_id=rpc_id if "id" in data else None,
            )

        services = RuntimeServices.from_app(app)
        ctx = build_stateless_dispatch_context(
            data=data,
            app=app,
            rpc_id=rpc_id,
            method=method,
            server_settings=server_settings,
            services=services,
            protocol_revision=revision,
            request_metadata=request_metadata,
            principal=principal,
            direct_response=direct_response,
        )
        return await self._run_pipeline(ctx)


_dispatcher = Dispatcher()


_session_processor = SessionJsonRpcMessageProcessor(_dispatcher)
_stateless_processor = StatelessJsonRpcMessageProcessor(_dispatcher)


async def process_jsonrpc_message(
    session_id: str,
    data: JSONObject,
    *,
    app: FastAPI,
    direct_response: bool = False,
) -> DispatchResult:
    return await _session_processor.process(
        session_id=session_id,
        data=data,
        app=app,
        direct_response=direct_response,
    )


async def process_stateless_jsonrpc_message(
    data: JSONObject,
    *,
    app: FastAPI,
    principal: Principal | None = None,
    direct_response: bool = True,
) -> DispatchResult:
    return await _stateless_processor.process(
        data=data,
        app=app,
        principal=principal,
        direct_response=direct_response,
    )


__all__ = [
    "DispatchError",
    "Dispatcher",
    "SessionMessageProcessor",
    "SessionJsonRpcMessageProcessor",
    "StatelessMessageProcessor",
    "StatelessJsonRpcMessageProcessor",
    "process_jsonrpc_message",
    "process_stateless_jsonrpc_message",
]
