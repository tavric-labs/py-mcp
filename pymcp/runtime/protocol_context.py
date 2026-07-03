"""Dispatch context builders for protocol revisions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from ..protocol.metadata import RequestMetadata
from ..protocol.revisions import ProtocolRevision
from ..registries.registry import get_registry_manager
from ..registries.registry import RegistryManager
from ..session.store import SessionManager, get_session_manager
from ..session.types import Session
from ..settings import ServerSettings
from ..tasks.cancellation import get_cancellation_manager
from ..tasks.cancellation import CancellationManager
from ..tasks.engine import get_task_manager
from ..tasks.engine import TaskManager
from .types import DispatchContext, JSONObject


def resolve_protocol_revision(version: str | None, settings: ServerSettings) -> ProtocolRevision | None:
    from ..protocol.revisions import get_protocol_revision

    revision = get_protocol_revision(version)
    if revision is None:
        return None
    if version not in tuple(settings.protocol_versions):
        return None
    return revision


@dataclass(frozen=True, slots=True)
class RuntimeServices:
    registry_manager: RegistryManager
    session_manager: SessionManager
    cancellation_manager: CancellationManager
    task_manager: TaskManager

    @classmethod
    def from_app(cls, app: FastAPI) -> "RuntimeServices":
        return cls(
            registry_manager=get_registry_manager(app),
            session_manager=get_session_manager(app),
            cancellation_manager=get_cancellation_manager(app),
            task_manager=get_task_manager(app),
        )


def transient_stateless_session() -> Session:
    return Session(session_id="stateless", queue=asyncio.Queue())


def build_session_dispatch_context(
    *,
    session_id: str,
    data: JSONObject,
    app: FastAPI,
    session: Session,
    rpc_id: Any,
    method: str,
    server_settings: ServerSettings,
    services: RuntimeServices,
    direct_response: bool,
) -> DispatchContext:
    return DispatchContext(
        session_id=session_id,
        data=data,
        app=app,
        session=session,
        rpc_id=rpc_id,
        method=method,
        registry_manager=services.registry_manager,
        server_settings=server_settings,
        session_manager=services.session_manager,
        cancellation_manager=services.cancellation_manager,
        task_manager=services.task_manager,
        direct_response=direct_response,
        queue=session.queue,
    )


def build_stateless_dispatch_context(
    *,
    data: JSONObject,
    app: FastAPI,
    rpc_id: Any,
    method: str,
    server_settings: ServerSettings,
    services: RuntimeServices,
    protocol_revision: ProtocolRevision,
    request_metadata: RequestMetadata,
    direct_response: bool,
) -> DispatchContext:
    return DispatchContext(
        session_id="stateless",
        data=data,
        app=app,
        session=transient_stateless_session(),
        rpc_id=rpc_id,
        method=method,
        registry_manager=services.registry_manager,
        server_settings=server_settings,
        session_manager=services.session_manager,
        cancellation_manager=services.cancellation_manager,
        task_manager=services.task_manager,
        protocol_revision=protocol_revision,
        request_metadata=request_metadata,
        direct_response=direct_response,
    )


__all__ = [
    "build_session_dispatch_context",
    "build_stateless_dispatch_context",
    "resolve_protocol_revision",
    "RuntimeServices",
    "transient_stateless_session",
]
