"""JSON-RPC message processors for session and stateless protocol revisions."""

from __future__ import annotations

from typing import Protocol

from fastapi import FastAPI

from ..observability.logging import get_logger
from ..protocol.errors import build_error_response
from ..security.authn import Principal
from ..session.store import get_session_manager
from .protocol_context import RuntimeServices, build_session_dispatch_context
from .types import DispatchResult, JSONObject, make_result


logger = get_logger(__name__)


class SessionMessageProcessor(Protocol):
    async def process(
        self,
        *,
        data: JSONObject,
        app: FastAPI,
        direct_response: bool = False,
        session_id: str,
    ) -> DispatchResult:
        ...


class StatelessMessageProcessor(Protocol):
    async def process(
        self,
        *,
        data: JSONObject,
        app: FastAPI,
        principal: Principal | None = None,
        direct_response: bool = True,
    ) -> DispatchResult:
        ...


class SessionJsonRpcMessageProcessor:
    def __init__(self, dispatcher):
        self._dispatcher = dispatcher

    async def process(
        self,
        *,
        data: JSONObject,
        app: FastAPI,
        direct_response: bool = False,
        session_id: str,
    ) -> DispatchResult:
        try:
            return await self._dispatcher.dispatch(
                session_id=session_id,
                data=data,
                app=app,
                direct_response=direct_response,
            )
        except self._dispatcher.dispatch_error_type as exc:
            payload = build_error_response(exc.rpc_id, exc.code, exc.message, exc.data)
            try:
                session = get_session_manager(app).get_session(session_id)
                server_settings = getattr(app.state, "server_settings", None)
                if session is not None and server_settings is not None:
                    services = RuntimeServices.from_app(app)
                    ctx = build_session_dispatch_context(
                        session_id=session_id,
                        data=data,
                        app=app,
                        session=session,
                        rpc_id=self._dispatcher.rpc_id_from_data(data),
                        method=data.get("method") if isinstance(data.get("method"), str) else "<unknown>",
                        server_settings=server_settings,
                        services=services,
                        direct_response=direct_response,
                    )
                    await ctx.maybe_enqueue(payload, require_id=exc.require_id)
            except Exception:
                logger.exception("Failed to enqueue dispatch error for session %s", session_id)
            return make_result(exc.status, json_response=True, payload=payload)


class StatelessJsonRpcMessageProcessor:
    def __init__(self, dispatcher):
        self._dispatcher = dispatcher

    async def process(
        self,
        *,
        data: JSONObject,
        app: FastAPI,
        principal: Principal | None = None,
        direct_response: bool = True,
    ) -> DispatchResult:
        try:
            return await self._dispatcher.dispatch_stateless(
                data=data,
                app=app,
                principal=principal,
                direct_response=direct_response,
            )
        except self._dispatcher.dispatch_error_type as exc:
            payload = build_error_response(exc.rpc_id, exc.code, exc.message, exc.data)
            return make_result(exc.status, json_response=True, payload=payload)


__all__ = [
    "SessionMessageProcessor",
    "SessionJsonRpcMessageProcessor",
    "StatelessMessageProcessor",
    "StatelessJsonRpcMessageProcessor",
]
