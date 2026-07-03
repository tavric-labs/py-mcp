from fastapi.testclient import TestClient

from pymcp import CapabilitySettings, ServerSettings, create_app
from pymcp.protocol.errors import MCPErrorCode
from pymcp.protocol.extensions import (
    DEFAULT_MCP_APPS_UI_MIME_TYPES,
    MCP_APPS_UI,
    MCP_ENTERPRISE_MANAGED_AUTHORIZATION,
    MCP_OAUTH_CLIENT_CREDENTIALS,
    MCP_TASKS,
)
from pymcp.runtime.protocol_context import (
    RuntimeServices,
    build_stateless_dispatch_context,
)
from pymcp.protocol.metadata import RequestMetadata
from pymcp.protocol.revisions import LATEST_DRAFT_PROTOCOL_VERSION, get_protocol_revision
from pymcp.security.authn import Principal


DRAFT_VERSION = LATEST_DRAFT_PROTOCOL_VERSION


def _draft_meta(version: str = DRAFT_VERSION) -> dict:
    return {
        "io.modelcontextprotocol/protocolVersion": version,
        "io.modelcontextprotocol/clientInfo": {"name": "test-client", "version": "1.0.0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def _draft_headers(method: str, *, version: str = DRAFT_VERSION, name: str | None = None) -> dict:
    headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": version,
        "Mcp-Method": method,
    }
    if name is not None:
        headers["Mcp-Name"] = name
    return headers


def test_protocol_mode_defaults_and_opt_ins():
    assert ServerSettings().protocol_versions == (
        "2025-11-25",
        "2025-06-18",
        "2025-03-26",
        "2024-11-05",
    )
    assert ServerSettings(protocol_mode="draft").protocol_versions == (DRAFT_VERSION,)
    assert ServerSettings(protocol_mode="dual").protocol_versions[0] == DRAFT_VERSION


def test_draft_server_discover_is_stateless_and_cacheable():
    client = TestClient(create_app(protocol_mode="draft", middleware_config=None))

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "discover-1",
            "method": "server/discover",
            "params": {"_meta": _draft_meta()},
        },
        headers=_draft_headers("server/discover"),
    )

    assert response.status_code == 200
    assert "MCP-Session-Id" not in response.headers
    result = response.json()["result"]
    assert result["resultType"] == "complete"
    assert result["supportedVersions"] == [DRAFT_VERSION]
    assert result["serverInfo"]["name"] == "pymcp-kit"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    extensions = result["capabilities"]["extensions"]
    assert MCP_TASKS in extensions
    assert "tasks" not in result["capabilities"]


def test_draft_tools_list_uses_result_type_and_cache_fields():
    client = TestClient(create_app(protocol_mode="draft", middleware_config=None))

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {"_meta": _draft_meta()},
        },
        headers=_draft_headers("tools/list"),
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["resultType"] == "complete"
    assert result["tools"] == []
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"


def test_draft_tasks_are_supported_as_extension_capability():
    client = TestClient(create_app(protocol_mode="draft", middleware_config=None))

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/list",
            "params": {"_meta": _draft_meta()},
        },
        headers=_draft_headers("tasks/list"),
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["resultType"] == "complete"
    assert result["tasks"] == []


def test_draft_tasks_update_validates_missing_task():
    client = TestClient(create_app(protocol_mode="draft", middleware_config=None))

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/update",
            "params": {
                "_meta": _draft_meta(),
                "taskId": "missing",
                "inputResponses": {},
            },
        },
        headers=_draft_headers("tasks/update"),
    )

    assert response.status_code == 200
    assert response.json()["error"]["code"] == MCPErrorCode.INVALID_PARAMS


def test_draft_custom_extensions_are_advertised():
    client = TestClient(
        create_app(
            server_settings=ServerSettings(
                protocol_mode="draft",
                capabilities=CapabilitySettings(
                    extensions={"io.modelcontextprotocol/custom": {"enabled": True}},
                ),
            ),
            middleware_config=None,
        )
    )

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "discover-1",
            "method": "server/discover",
            "params": {"_meta": _draft_meta()},
        },
        headers=_draft_headers("server/discover"),
    )

    assert response.status_code == 200
    extensions = response.json()["result"]["capabilities"]["extensions"]
    assert extensions["io.modelcontextprotocol/custom"] == {"enabled": True}


def test_draft_official_extensions_are_advertised_when_enabled():
    client = TestClient(
        create_app(
            server_settings=ServerSettings(
                protocol_mode="draft",
                capabilities=CapabilitySettings(
                    mcp_apps_enabled=True,
                    oauth_client_credentials_enabled=True,
                    enterprise_managed_authorization_enabled=True,
                ),
            ),
            middleware_config=None,
        )
    )

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "discover-1",
            "method": "server/discover",
            "params": {"_meta": _draft_meta()},
        },
        headers=_draft_headers("server/discover"),
    )

    assert response.status_code == 200
    extensions = response.json()["result"]["capabilities"]["extensions"]
    assert extensions[MCP_APPS_UI] == {"mimeTypes": list(DEFAULT_MCP_APPS_UI_MIME_TYPES)}
    assert extensions[MCP_OAUTH_CLIENT_CREDENTIALS] == {}
    assert extensions[MCP_ENTERPRISE_MANAGED_AUTHORIZATION] == {}


def test_draft_http_requires_mcp_method_header():
    client = TestClient(create_app(protocol_mode="draft", middleware_config=None))

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {"_meta": _draft_meta()},
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": DRAFT_VERSION,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == MCPErrorCode.HEADER_MISMATCH


def test_draft_http_unsupported_version_lists_supported_versions():
    client = TestClient(create_app(protocol_mode="dual", middleware_config=None))

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "server/discover",
            "params": {"_meta": _draft_meta("1900-01-01")},
        },
        headers=_draft_headers("server/discover", version="1900-01-01"),
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == MCPErrorCode.UNSUPPORTED_PROTOCOL_VERSION
    assert error["data"]["requested"] == "1900-01-01"
    assert DRAFT_VERSION in error["data"]["supported"]


def test_stateless_dispatch_context_carries_principal():
    app = create_app(protocol_mode="draft", middleware_config=None)
    services = RuntimeServices.from_app(app)
    principal = Principal(subject="alice")
    ctx = build_stateless_dispatch_context(
        data={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {"_meta": _draft_meta()},
        },
        app=app,
        rpc_id=1,
        method="tools/list",
        server_settings=app.state.server_settings,
        services=services,
        protocol_revision=get_protocol_revision(DRAFT_VERSION),
        request_metadata=RequestMetadata(
            protocol_version=DRAFT_VERSION,
            client_info={"name": "test-client", "version": "1.0.0"},
            client_capabilities={},
            raw=_draft_meta(),
        ),
        principal=principal,
        direct_response=True,
    )

    assert ctx.session.principal == principal
