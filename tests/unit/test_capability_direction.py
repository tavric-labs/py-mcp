"""Verify build_capabilities produces only server-side capabilities."""

from pymcp.capabilities.registry import build_capabilities
from pymcp.protocol.extensions import (
    DEFAULT_MCP_APPS_UI_MIME_TYPES,
    MCP_APPS_UI,
    MCP_ENTERPRISE_MANAGED_AUTHORIZATION,
    MCP_OAUTH_CLIENT_CREDENTIALS,
)
from pymcp.registries.registry import PromptRegistry, ResourceRegistry, ToolRegistry
from pymcp.settings import CapabilitySettings


def _build(settings: CapabilitySettings | None = None) -> dict:
    settings = settings or CapabilitySettings()
    return build_capabilities(
        settings,
        ToolRegistry(),
        PromptRegistry(),
        ResourceRegistry(),
    )


def test_roots_not_in_server_capabilities():
    caps = _build()
    assert "roots" not in caps


def test_elicitation_not_in_server_capabilities():
    caps = _build()
    assert "elicitation" not in caps


def test_sampling_not_in_server_capabilities():
    caps = _build()
    assert "sampling" not in caps


def test_tools_always_present():
    caps = _build()
    assert "tools" in caps


def test_logging_present_when_enabled():
    caps = _build(CapabilitySettings(logging_enabled=True))
    assert "logging" in caps


def test_logging_absent_when_disabled():
    caps = _build(CapabilitySettings(logging_enabled=False))
    assert "logging" not in caps


def test_completions_present_when_enabled():
    caps = _build(CapabilitySettings(completions_enabled=True))
    assert "completions" in caps


def test_completions_absent_when_disabled():
    caps = _build(CapabilitySettings(completions_enabled=False))
    assert "completions" not in caps


def test_tasks_present_when_enabled():
    caps = _build(CapabilitySettings(tasks_enabled=True))
    assert "tasks" in caps
    tasks = caps["tasks"]
    assert "list" in tasks
    assert "cancel" in tasks
    assert "requests" in tasks


def test_tasks_absent_when_disabled():
    caps = _build(CapabilitySettings(tasks_enabled=False))
    assert "tasks" not in caps


def test_experimental_present_when_set():
    caps = _build(CapabilitySettings(experimental_features={"myFeature": {}}))
    assert "experimental" in caps
    assert "myFeature" in caps["experimental"]


def test_experimental_absent_when_none():
    caps = _build(CapabilitySettings(experimental_features=None))
    assert "experimental" not in caps


def test_official_extensions_absent_by_default():
    caps = _build()
    assert "extensions" not in caps


def test_mcp_apps_extension_present_when_enabled():
    caps = _build(CapabilitySettings(mcp_apps_enabled=True))
    assert caps["extensions"][MCP_APPS_UI] == {"mimeTypes": list(DEFAULT_MCP_APPS_UI_MIME_TYPES)}


def test_auth_extensions_present_when_enabled():
    caps = _build(
        CapabilitySettings(
            oauth_client_credentials_enabled=True,
            enterprise_managed_authorization_enabled=True,
        )
    )
    assert caps["extensions"][MCP_OAUTH_CLIENT_CREDENTIALS] == {}
    assert caps["extensions"][MCP_ENTERPRISE_MANAGED_AUTHORIZATION] == {}


def test_explicit_extension_settings_override_builtin_defaults():
    caps = _build(
        CapabilitySettings(
            mcp_apps_enabled=True,
            extensions={MCP_APPS_UI: {"mimeTypes": ["text/html"]}},
        )
    )
    assert caps["extensions"][MCP_APPS_UI] == {"mimeTypes": ["text/html"]}
