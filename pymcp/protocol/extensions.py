"""Known MCP extension identifiers and capability helpers."""

from __future__ import annotations

from typing import Any


JSONObject = dict[str, Any]

MCP_TASKS = "io.modelcontextprotocol/tasks"
MCP_APPS_UI = "io.modelcontextprotocol/ui"
MCP_OAUTH_CLIENT_CREDENTIALS = "io.modelcontextprotocol/oauth-client-credentials"
MCP_ENTERPRISE_MANAGED_AUTHORIZATION = "io.modelcontextprotocol/enterprise-managed-authorization"

DEFAULT_MCP_APPS_UI_MIME_TYPES = ("text/html;profile=mcp-app",)

_FEATURE_TO_EXTENSION = {
    "tasks": MCP_TASKS,
    "ui": MCP_APPS_UI,
    "apps_ui": MCP_APPS_UI,
    "oauth_client_credentials": MCP_OAUTH_CLIENT_CREDENTIALS,
    "enterprise_managed_authorization": MCP_ENTERPRISE_MANAGED_AUTHORIZATION,
}


def extension_for_capability_feature(feature: str) -> str | None:
    return _FEATURE_TO_EXTENSION.get(feature)


def has_extension(capabilities: JSONObject, extension_name: str) -> bool:
    extensions = capabilities.get("extensions")
    return isinstance(extensions, dict) and extension_name in extensions


__all__ = [
    "DEFAULT_MCP_APPS_UI_MIME_TYPES",
    "MCP_APPS_UI",
    "MCP_ENTERPRISE_MANAGED_AUTHORIZATION",
    "MCP_OAUTH_CLIENT_CREDENTIALS",
    "MCP_TASKS",
    "extension_for_capability_feature",
    "has_extension",
]
