"""Server discovery handlers for stateless MCP revisions."""

from __future__ import annotations

from ...capabilities.registry import ServerCapabilities, negotiate_capabilities
from ...observability.logging import get_logger
from ...protocol.json_types import JSONObject
from ..types import DispatchContext, DispatchResult, make_result
from .registry import rpc_method

logger = get_logger(__name__)


def _server_info(ctx: DispatchContext) -> JSONObject:
    settings = ctx.server_settings
    server_info: JSONObject = {
        "name": settings.name,
        "version": settings.version,
    }
    if settings.title is not None:
        server_info["title"] = settings.title
    if settings.description is not None:
        server_info["description"] = settings.description
    if settings.website_url is not None:
        server_info["websiteUrl"] = settings.website_url
    if settings.icons is not None:
        server_info["icons"] = settings.icons
    return server_info


@rpc_method("server/discover")
async def handle_server_discover(ctx: DispatchContext) -> DispatchResult:
    server_capabilities = ServerCapabilities(app=ctx.app, protocol_revision=ctx.protocol_revision)
    client_capabilities = (
        ctx.request_metadata.client_capabilities
        if ctx.request_metadata is not None
        else ctx.session.client_capabilities.get_capabilities()
    )
    capabilities = negotiate_capabilities(client_capabilities, server_capabilities)
    authorizer = getattr(getattr(ctx.app, "state", None), "authorizer", None)
    principal = ctx.session.principal
    if authorizer is not None:
        try:
            filtered = authorizer.filter_capabilities(principal, capabilities)
            if isinstance(filtered, dict):
                capabilities = filtered
        except Exception:
            logger.exception(
                "Failed to filter discovery capabilities for principal %s",
                principal.subject if principal is not None else None,
            )
    result: JSONObject = {
        "supportedVersions": list(ctx.server_settings.protocol_versions),
        "capabilities": capabilities,
        "serverInfo": _server_info(ctx),
    }
    payload = ctx.payloads().success(ctx.rpc_id, result)
    await ctx.maybe_enqueue(payload)
    return make_result(200, json_response=True, payload=payload)


__all__ = ["handle_server_discover"]
