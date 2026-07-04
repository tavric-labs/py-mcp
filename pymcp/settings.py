"""Application settings for PyMCP Kit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .protocol.extensions import DEFAULT_MCP_APPS_UI_MIME_TYPES
from .protocol.revisions import (
    DEFAULT_PROTOCOL_MODE,
    get_protocol_revision,
    ProtocolMode,
    STABLE_PROTOCOL_VERSIONS,
    enabled_protocol_revisions,
    protocol_versions_for_mode,
)

SUPPORTED_PROTOCOL_VERSIONS = STABLE_PROTOCOL_VERSIONS


JSONObject = dict[str, Any]


@dataclass(slots=True)
class CapabilitySettings:
    # -- server capability knobs (advertised in initialize response) ------
    tools_list_changed: bool = False
    prompts_list_changed: bool = False
    resources_list_changed: bool = False
    resources_subscribe: bool = True
    advertise_empty_prompts: bool = False
    advertise_empty_resources: bool = False
    logging_enabled: bool = False
    completions_enabled: bool = False
    tasks_enabled: bool = True
    tasks_tool_call: bool = True
    tasks_list: bool = True
    tasks_cancel: bool = True
    list_page_size: int = 50
    mcp_apps_enabled: bool = False
    mcp_apps_mime_types: tuple[str, ...] = DEFAULT_MCP_APPS_UI_MIME_TYPES
    mcp_apps_settings: JSONObject | None = None
    oauth_client_credentials_enabled: bool = False
    oauth_client_credentials_settings: JSONObject | None = None
    enterprise_managed_authorization_enabled: bool = False
    enterprise_managed_authorization_settings: JSONObject | None = None
    extensions: dict[str, JSONObject] | None = None
    experimental_features: dict[str, JSONObject] | None = None

    def __post_init__(self) -> None:
        if self.list_page_size <= 0:
            raise ValueError("list_page_size must be a positive integer")
        if self.mcp_apps_enabled and not self.mcp_apps_mime_types:
            raise ValueError("mcp_apps_mime_types cannot be empty when mcp_apps_enabled is true")


@dataclass(slots=True)
class ServerSettings:
    name: str = "pymcp-kit"
    version: str = "0.3.0"
    protocol_mode: ProtocolMode = DEFAULT_PROTOCOL_MODE
    protocol_versions: tuple[str, ...] | None = None
    initializable_protocol_versions: tuple[str, ...] | None = None
    capabilities: CapabilitySettings = field(default_factory=CapabilitySettings)
    title: str | None = None
    description: str | None = None
    website_url: str | None = None
    icons: list[JSONObject] | None = None

    def __post_init__(self) -> None:
        if self.protocol_versions is None:
            self.protocol_versions = protocol_versions_for_mode(self.protocol_mode)
        if not self.protocol_versions:
            raise ValueError(
                "ServerSettings.protocol_versions cannot be empty; "
                "at least one supported version is required"
            )
        enabled_protocol_revisions(tuple(self.protocol_versions))
        if self.initializable_protocol_versions is None:
            self.initializable_protocol_versions = tuple(
                version
                for version in self.protocol_versions
                if (revision := get_protocol_revision(version)) is not None and revision.supports_initialization
            )
        else:
            enabled_protocol_revisions(tuple(self.initializable_protocol_versions))


__all__ = [
    "CapabilitySettings",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "ServerSettings",
]
