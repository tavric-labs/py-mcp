"""Runtime-layer shared types."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI

from ..protocol.json_types import JSONValue
from ..protocol.meta import attach_meta, extract_request_meta
from ..protocol.metadata import RequestMetadata

from ..capabilities import build_capabilities
from ..capabilities.registry import ClientCapabilities
from ..protocol.extensions import extension_for_capability_feature
from ..protocol.payload import PayloadFactory, get_payload_factory
from ..protocol.revisions import ProtocolRevision, extension_for_feature
from ..registries.registry import RegistryManager
from ..session.store import SessionManager
from ..session.types import Session
from ..settings import ServerSettings
from ..tasks.cancellation import CancellationManager
from ..tasks.engine import TaskManager


JSONObject = dict[str, Any]


@dataclass(frozen=True)
class DispatchResponse:
    status: int
    json: bool
    payload: JSONObject | None


DispatchResult = DispatchResponse


@dataclass(frozen=True)
class DispatchContext:
    session_id: str
    data: JSONObject
    app: FastAPI
    session: Session
    rpc_id: Any
    method: str
    registry_manager: RegistryManager
    server_settings: ServerSettings
    session_manager: SessionManager
    cancellation_manager: CancellationManager
    task_manager: TaskManager
    protocol_revision: ProtocolRevision | None = None
    request_metadata: RequestMetadata | None = None
    direct_response: bool = False
    queue: asyncio.Queue[str] | None = None

    def supports(self, feature: str) -> bool:
        """Check whether the *server* advertises *feature*."""
        if (
            self.protocol_revision is not None
            and feature not in self.protocol_revision.features
            and extension_for_capability_feature(feature) is None
        ):
            return False
        return self._feature_capability(feature) is not None

    def client_supports(self, feature: str) -> bool:
        """Check whether the *client* declared support for *feature*."""
        if self.request_metadata is not None:
            return ClientCapabilities(self.request_metadata.client_capabilities).supports(feature)
        return self.session.client_capabilities.supports(feature)

    def supports_task_request(self, namespace: str, method: str) -> bool:
        """Check whether the *server* advertises task-augmented request support.

        Used by the tool handler to decide if task-augmented tool calls
        are enabled on the server side.
        """
        capabilities = self._capabilities()
        tasks_caps = self._feature_capability("tasks", capabilities=capabilities)
        if not isinstance(tasks_caps, dict):
            return False
        requests_caps = tasks_caps.get("requests")
        if not isinstance(requests_caps, dict):
            return False
        namespace_caps = requests_caps.get(namespace)
        if not isinstance(namespace_caps, dict):
            return False
        method_caps = namespace_caps.get(method)
        return isinstance(method_caps, dict)

    def _capabilities(self) -> JSONObject:
        capabilities = self.session.capabilities
        if capabilities is None:
            capabilities = build_capabilities(
                self.server_settings.capabilities,
                self.registry_manager.tool_registry,
                self.registry_manager.prompt_registry,
                self.registry_manager.resource_registry,
                protocol_revision=self.protocol_revision,
            )
        return capabilities

    def _feature_capability(
        self,
        feature: str,
        *,
        capabilities: JSONObject | None = None,
    ) -> JSONValue | None:
        capabilities = capabilities or self._capabilities()
        top_level = capabilities.get(feature)
        if top_level is not None:
            return top_level
        extension = extension_for_feature(self.protocol_revision, feature)
        extension_name = extension.name if extension is not None else extension_for_capability_feature(feature)
        if extension_name is not None:
            extensions = capabilities.get("extensions")
            if isinstance(extensions, dict) and extension_name in extensions:
                return extensions[extension_name]
            return None
        return capabilities.get(feature)

    def payloads(self, *, protocol_version: str | None = None) -> PayloadFactory:
        version = protocol_version or self.protocol_version
        return get_payload_factory(version, app=self.app)

    @property
    def protocol_version(self) -> str | None:
        if self.protocol_revision is not None:
            return self.protocol_revision.version
        if self.request_metadata is not None:
            return self.request_metadata.protocol_version
        return self.session.protocol_version

    @property
    def request_meta(self) -> JSONObject:
        if self.request_metadata is not None:
            return dict(self.request_metadata.raw)
        return extract_request_meta(self.data)

    def success_payload(
        self,
        result: JSONObject,
        *,
        meta: JSONObject | None = None,
    ) -> JSONObject:
        payload = self.payloads().success(self.rpc_id, result)
        combined = dict(meta or {})
        if combined:
            return attach_meta(payload, combined)
        return payload

    def error_payload(
        self,
        code: int,
        message: str,
        *,
        meta: JSONObject | None = None,
        data: JSONValue | None = None,
    ) -> JSONObject:
        payload = self.payloads().error(self.rpc_id, code, message, data=data)
        if meta:
            return attach_meta(payload, meta)
        return payload

    async def maybe_enqueue(
        self,
        payload: JSONObject | None,
        *,
        require_id: bool = True,
    ) -> None:
        if self.direct_response or payload is None:
            return
        if require_id and "id" not in self.data:
            return
        queue = self.queue or self.session.queue
        await queue.put(json.dumps(payload))


def make_result(
    status: int,
    *,
    json_response: bool,
    payload: JSONObject | None,
) -> DispatchResult:
    return DispatchResponse(status=status, json=json_response, payload=payload)


__all__ = [
    "DispatchContext",
    "DispatchResponse",
    "DispatchResult",
    "JSONObject",
    "make_result",
]
