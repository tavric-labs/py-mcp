"""HTTP metadata validation for MCP protocol revisions."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from ..protocol.errors import MCPErrorCode
from ..protocol.metadata import PROTOCOL_VERSION_META_KEY, extract_request_metadata
from ..protocol.revisions import get_protocol_revision


@dataclass(frozen=True, slots=True)
class HttpValidationError:
    status_code: int
    code: int
    message: str
    data: dict[str, Any] | None = None
    rpc_id: Any = None


def request_body_protocol_version(data: dict) -> str | None:
    request_metadata = extract_request_metadata(data)
    if request_metadata is not None:
        return request_metadata.protocol_version
    params = data.get("params")
    params_dict = params if isinstance(params, dict) else {}
    meta = params_dict.get("_meta")
    if isinstance(meta, dict):
        raw = meta.get(PROTOCOL_VERSION_META_KEY)
        return raw if isinstance(raw, str) else None
    return None


def is_stateless_request(data: dict, request: Request) -> bool:
    version = request_body_protocol_version(data) or request.headers.get("MCP-Protocol-Version")
    revision = get_protocol_revision(version)
    return bool(revision and revision.stateless)


def looks_like_stateless_request(data: dict, request: Request, session_id: str | None) -> bool:
    if is_stateless_request(data, request):
        return True
    if session_id:
        return False
    method = data.get("method")
    if method == "initialize":
        return False
    return bool(request_body_protocol_version(data) or request.headers.get("MCP-Protocol-Version"))


def _server_supported_versions(request: Request) -> tuple[str, ...]:
    settings = getattr(request.app.state, "server_settings", None)
    return tuple(settings.protocol_versions) if settings is not None else ()


def _decode_header_value(value: str) -> str | None:
    if value.startswith("=?base64?") and value.endswith("?="):
        encoded = value[len("=?base64?") : -2]
        try:
            return base64.b64decode(encoded).decode("utf-8")
        except Exception:
            return None
    return value


def validate_stateless_http_metadata(request: Request, data: dict) -> HttpValidationError | None:
    rpc_id = data.get("id") if "id" in data else None
    header_version = request.headers.get("MCP-Protocol-Version")
    body_version = request_body_protocol_version(data)
    supported_versions = _server_supported_versions(request)
    if not header_version:
        return HttpValidationError(
            400,
            MCPErrorCode.HEADER_MISMATCH,
            "Header mismatch: MCP-Protocol-Version header required",
            rpc_id=rpc_id,
        )
    if not body_version:
        return None
    if header_version != body_version:
        return HttpValidationError(
            400,
            MCPErrorCode.HEADER_MISMATCH,
            "Header mismatch: MCP-Protocol-Version header does not match request _meta",
            rpc_id=rpc_id,
        )
    if header_version not in supported_versions:
        return HttpValidationError(
            400,
            MCPErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
            "Unsupported protocol version",
            data={"supported": list(supported_versions), "requested": header_version},
            rpc_id=rpc_id,
        )

    method = data.get("method")
    method_name = method if isinstance(method, str) else None
    mcp_method = request.headers.get("Mcp-Method")
    if not mcp_method:
        return HttpValidationError(
            400,
            MCPErrorCode.HEADER_MISMATCH,
            "Header mismatch: Mcp-Method header required",
            rpc_id=rpc_id,
        )
    if mcp_method != method_name:
        return HttpValidationError(
            400,
            MCPErrorCode.HEADER_MISMATCH,
            "Header mismatch: Mcp-Method header does not match request method",
            rpc_id=rpc_id,
        )

    if method_name in {"tools/call", "resources/read", "prompts/get"}:
        params = data.get("params")
        params_dict = params if isinstance(params, dict) else {}
        body_name = params_dict.get("uri") if method_name == "resources/read" else params_dict.get("name")
        header_name = request.headers.get("Mcp-Name")
        decoded_name = _decode_header_value(header_name) if header_name is not None else None
        if not isinstance(body_name, str) or not header_name:
            return HttpValidationError(
                400,
                MCPErrorCode.HEADER_MISMATCH,
                "Header mismatch: Mcp-Name header required",
                rpc_id=rpc_id,
            )
        if decoded_name != body_name:
            return HttpValidationError(
                400,
                MCPErrorCode.HEADER_MISMATCH,
                "Header mismatch: Mcp-Name header does not match request body",
                rpc_id=rpc_id,
            )
    return None


__all__ = [
    "HttpValidationError",
    "looks_like_stateless_request",
    "request_body_protocol_version",
    "validate_stateless_http_metadata",
]
