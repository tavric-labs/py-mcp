"""Per-request metadata helpers for stateless MCP revisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import MCPErrorCode


PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
LOG_LEVEL_META_KEY = "io.modelcontextprotocol/logLevel"


@dataclass(frozen=True, slots=True)
class RequestMetadata:
    protocol_version: str
    client_info: dict[str, Any]
    client_capabilities: dict[str, Any]
    raw: dict[str, Any]


class RequestMetadataError(Exception):
    def __init__(self, message: str, *, code: int = MCPErrorCode.INVALID_PARAMS):
        super().__init__(message)
        self.code = code


def extract_params(data: dict[str, Any]) -> dict[str, Any]:
    params = data.get("params")
    return params if isinstance(params, dict) else {}


def _read_request_metadata(data: dict[str, Any]) -> tuple[dict[str, Any] | None, Any, Any, Any]:
    params = extract_params(data)
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return None, None, None, None
    return (
        meta,
        meta.get(PROTOCOL_VERSION_META_KEY),
        meta.get(CLIENT_INFO_META_KEY),
        meta.get(CLIENT_CAPABILITIES_META_KEY),
    )


def extract_request_metadata(data: dict[str, Any]) -> RequestMetadata | None:
    meta, version, client_info, client_capabilities = _read_request_metadata(data)
    if meta is None or not isinstance(version, str):
        return None
    return RequestMetadata(
        protocol_version=version,
        client_info=client_info if isinstance(client_info, dict) else {},
        client_capabilities=client_capabilities if isinstance(client_capabilities, dict) else {},
        raw=meta,
    )


def require_request_metadata(data: dict[str, Any]) -> RequestMetadata:
    meta, version, client_info, client_capabilities = _read_request_metadata(data)
    if meta is None:
        raise RequestMetadataError("Invalid params: missing _meta")

    if not isinstance(version, str) or not version:
        raise RequestMetadataError(f"Invalid params: missing {PROTOCOL_VERSION_META_KEY}")

    if not isinstance(client_info, dict):
        raise RequestMetadataError(f"Invalid params: missing {CLIENT_INFO_META_KEY}")
    if not isinstance(client_info.get("name"), str) or not isinstance(client_info.get("version"), str):
        raise RequestMetadataError(f"Invalid params: malformed {CLIENT_INFO_META_KEY}")

    if not isinstance(client_capabilities, dict):
        raise RequestMetadataError(f"Invalid params: missing {CLIENT_CAPABILITIES_META_KEY}")

    return RequestMetadata(
        protocol_version=version,
        client_info=client_info,
        client_capabilities=client_capabilities,
        raw=meta,
    )


__all__ = [
    "CLIENT_CAPABILITIES_META_KEY",
    "CLIENT_INFO_META_KEY",
    "LOG_LEVEL_META_KEY",
    "PROTOCOL_VERSION_META_KEY",
    "RequestMetadata",
    "RequestMetadataError",
    "extract_request_metadata",
    "require_request_metadata",
]
