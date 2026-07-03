# Runtime Surface

`pymcp-kit` keeps the built-in surface intentionally narrow. This page is the quickest way to see what the package exposes at runtime and what capability toggles affect the MCP handshake.

## Supported Protocol Versions

`ServerSettings.protocol_mode` defaults to `"stable"`, which enables:

- `2025-11-25`
- `2025-06-18`
- `2025-03-26`
- `2024-11-05`

Draft `2026-07-28` support is opt-in:

```python
ServerSettings(protocol_mode="draft")  # draft only
ServerSettings(protocol_mode="dual")   # draft plus stable versions
```

`ServerSettings(protocol_versions=(...))` can be used as an explicit override
for compatibility testing.

## Draft Stateless Request Flow

Draft `2026-07-28` requests skip `initialize`/sessions entirely. Every request
carries its own protocol version, client info, and client capabilities in
`params._meta`, and is validated against matching HTTP headers before
dispatch:

```
Client                                   HTTP Transport                              Dispatcher                          Handler
  |                                            |                                           |                                  |
  | POST /mcp                                  |                                           |                                  |
  | headers: MCP-Protocol-Version,             |                                           |                                  |
  |          Mcp-Method, [Mcp-Name]            |                                           |                                  |
  | body:    params._meta = {                  |                                           |                                  |
  |            protocolVersion,                |                                           |                                  |
  |            clientInfo,                     |                                           |                                  |
  |            clientCapabilities }            |                                           |                                  |
  |------------------------------------------->|                                           |                                  |
  |                                  [origin check]                                        |                                  |
  |                                  request_body_protocol_version(data)                   |                                  |
  |                                  looks_like_stateless_request() -> True                |                                  |
  |                                  validate_stateless_http_metadata()                    |                                  |
  |                                    - MCP-Protocol-Version present & == body._meta       |                                  |
  |                                    - version in ServerSettings.protocol_versions        |                                  |
  |                                    - Mcp-Method present & == body.method                |                                  |
  |                                    - Mcp-Name required/matched for                      |                                  |
  |                                      tools/call | resources/read | prompts/get          |                                  |
  |                                    (any failure -> HEADER_MISMATCH /                    |                                  |
  |                                     UNSUPPORTED_PROTOCOL_VERSION, HTTP error)            |                                  |
  |                                            |                                           |                                  |
  |                        [subscriptions/listen] --> stream_stateless_subscription (SSE)   |                                  |
  |                                            |                                           |                                  |
  |                                  process_stateless_jsonrpc_message(data)                |                                  |
  |                                            |------------------------------------------>|                                  |
  |                                            |                            require_request_metadata(data)                   |
  |                                            |                              -> RequestMetadata(protocol_version,            |
  |                                            |                                 client_info, client_capabilities)            |
  |                                            |                            resolve_protocol_revision(version, settings)      |
  |                                            |                              -> ProtocolRevision (must be stateless)         |
  |                                            |                            build_stateless_dispatch_context(...)             |
  |                                            |                              -> DispatchContext (transient session,          |
  |                                            |                                 protocol_revision, request_metadata)         |
  |                                            |                            middleware pipeline:                             |
  |                                            |                              ErrorBoundary                                  |
  |                                            |                              -> InitGateMiddleware (bypassed, stateless)     |
  |                                            |                              -> RevisionMethodGateMiddleware                 |
  |                                            |                                 (blocks initialize/ping/subscribe/etc.,      |
  |                                            |                                  blocks server/discover if unsupported)      |
  |                                            |                              -> CapabilityGateMiddleware                     |
  |                                            |                              -> AuthorizationGateMiddleware                  |
  |                                            |                              -> call_next -----------------------------------|
  |                                            |                                                                              |
  |                                            |                                                             rpc_method handler runs
  |                                            |                                                             (e.g. server/discover,
  |                                            |                                                              tools/list, tasks/update)
  |                                            |                                                             ctx.payloads() ->
  |                                            |                                                             PayloadFactory_2026_07_28:
  |                                            |                                                               resultType="complete"
  |                                            |                                                               ttlMs=0,
  |                                            |                                                               cacheScope="private"
  |                                            |                            <-----------------------------------------------|
  |                                            |<-------------------------------------------                                 |
  |<-------------------------------------------|                                                                              |
  | 200 OK, no MCP-Session-Id header           |                                                                              |
  | body: { result: {..., resultType,          |                                                                              |
  |         ttlMs, cacheScope} }               |                                                                              |
```

Errors short-circuit at the HTTP layer (`HEADER_MISMATCH`,
`UNSUPPORTED_PROTOCOL_VERSION`) before ever reaching the dispatcher, and
`RequestMetadataError` short-circuits inside `dispatch_stateless` for
malformed or missing `_meta` fields.

## Conformance

`pymcp-kit` passes the official [MCP conformance suite](https://github.com/modelcontextprotocol/conformance)
in full against the [2025-11-25 specification](https://modelcontextprotocol.io/specification/2025-11-25).
The suite runs in CI on every change (the `MCP Conformance` workflow) against the
fixture server in `tests/conformance_server.py`, covering tool content blocks
(text, image, audio, embedded, and mixed resources), tool errors, progress,
logging, sampling, elicitation (including SEP-1034 defaults and SEP-1330 enum
variants), resource reads/templates/subscriptions, and prompt retrieval.

## Built-In HTTP Endpoints

- `GET /`: basic server metadata
- `POST /mcp`: Streamable HTTP MCP endpoint
- `GET /mcp`: transport support endpoint for streamable sessions
- `DELETE /mcp`: session termination endpoint for streamable sessions

## Implemented MCP Methods

### Lifecycle

- `initialize`
- `ping`
- `notifications/initialized`
- `notifications/cancelled`

When draft `2026-07-28` is enabled, stateless requests use per-request `_meta`
instead of `initialize`, and `server/discover` is available for discovery.
Draft extension capabilities are advertised under `capabilities.extensions`.
For example, task support is exposed as
`io.modelcontextprotocol/tasks` instead of the stable top-level `tasks` key.

### Tools

- `tools/list`
- `tools/call`

Tool registration supports optional declaration metadata:

- `title`
- `outputSchema`
- `annotations` (`readOnlyHint`, `destructiveHint`, `openWorldHint`, `idempotentHint`)
- `icons`

Tool handlers may return `structuredContent` alongside `content` blocks in `tools/call` results.

A tool can also accept a `request_context` parameter to report progress. When the
client includes `_meta.progressToken` on the `tools/call` request, `report_progress`
emits `notifications/progress`; otherwise it is a no-op.

```python
from pymcp import tool_registry
from pymcp.runtime.context import RequestContext

@tool_registry.register(title="Long job")
async def longJobTool(request_context: RequestContext) -> dict:
    await request_context.report_progress(0, 100)
    await request_context.report_progress(100, 100, message="done")
    return {"content": [{"type": "text", "text": "complete"}]}
```

```python
from pymcp import tool_registry

@tool_registry.register(
    title="Add numbers",
    output_schema={"type": "object", "properties": {"sum": {"type": "number"}}},
    annotations={"readOnlyHint": True, "destructiveHint": False},
)
def addNumbersTool(a: float, b: float) -> dict:
    total = a + b
    return {
        "content": [{"type": "text", "text": str(total)}],
        "structuredContent": {"sum": total},
    }
```

### Prompts

- `prompts/list`
- `prompts/get`

### Resources

- `resources/list`
- `resources/templates/list`
- `resources/read`
- `resources/subscribe`
- `resources/unsubscribe`
- `notifications/resources/updated`

`resources/subscribe` and `resources/unsubscribe` return an empty result (`{}`)
per the spec; subscription state is observable through
`notifications/resources/updated`, not the response body.

### Roots (Client Capability)

Roots are a *client* capability. The server can request the client's roots
via the `request_roots_list()` helper (sends `roots/list` to the client).

- `notifications/roots/list_changed` (client -> server notification)

### Completions

- `completion/complete`

Prompt argument completions are resolved from each argument's `schema.enum` or
explicit `completion` list. Resource template variable completions are resolved
from optional `variables` metadata passed to `register_template()`.

```python
@prompt_registry.register(
    arguments=[
        {
            "name": "language",
            "required": True,
            "schema": {"type": "string", "enum": ["python", "javascript", "rust"]},
        }
    ]
)
def languagePrompt(language: str) -> str:
    return language

@resource_registry.register_template(
    uri_template="memo://{topic}",
    variables={"topic": {"completion": ["welcome", "release-notes"]}},
)
def memoTemplate(topic: str) -> str:
    return topic
```

### Tasks

- `tasks/list`
- `tasks/get`
- `tasks/cancel`
- `tasks/result`
- `notifications/tasks/status`
- `notifications/progress`

### Elicitation (Client Capability)

Elicitation is a *client* capability. The server sends `elicitation/create`
to the client via the `request_elicitation()` helper. Both `form` and `url`
modes are supported.

### Sampling (Client Capability)

Sampling is a *client* capability. The server sends `sampling/createMessage`
to the client via the `request_sampling()` helper.

### Logging

- `logging/setLevel`
- `notifications/message` (server -> client log notification via `send_log_message()`)

## Request and Result Metadata (`_meta`)

JSON-RPC requests may carry `_meta` at the top level or under `params`. The runtime validates that each present `_meta` value is an object and merges top-level and params metadata for handlers that need progress tokens or related-task links.

Tool handlers lift `_meta` from a tool result body onto the JSON-RPC response envelope so clients receive metadata alongside the MCP result object. Task result responses use the same envelope-level `_meta` pattern.

## Capability Settings

`CapabilitySettings` controls which fragments appear in `initialize.result.capabilities` and which optional runtime behaviors are enabled.

Per the MCP 2025-11-25 spec, **server** capabilities (advertised in the initialize response) include: tools, prompts, resources, logging, completions, tasks, and experimental. **Client** capabilities (roots, sampling, elicitation) are declared by the client in the initialize request and are NOT part of server capability settings.

| Setting | Default | Effect |
| --- | --- | --- |
| `tools_list_changed` | `False` | Advertise `tools.listChanged` support. |
| `prompts_list_changed` | `False` | Advertise `prompts.listChanged` support. |
| `resources_list_changed` | `False` | Advertise `resources.listChanged` support. |
| `resources_subscribe` | `True` | Advertise and enable resource subscription support. |
| `advertise_empty_prompts` | `False` | Expose a prompts capability even when no prompts are registered. |
| `advertise_empty_resources` | `False` | Expose a resources capability even when no resources are registered. |
| `logging_enabled` | `False` | Advertise `logging` capability. |
| `completions_enabled` | `False` | Advertise `completions` capability and enable `completion/complete` handler. |
| `tasks_enabled` | `True` | Expose task capability fragments and task handlers. |
| `tasks_tool_call` | `True` | Advertise task augmentation for `tools/call`. |
| `tasks_list` | `True` | Advertise the `tasks/list` capability fragment. |
| `tasks_cancel` | `True` | Advertise the `tasks/cancel` capability fragment. |
| `mcp_apps_enabled` | `False` | Advertise `io.modelcontextprotocol/ui` support. |
| `mcp_apps_mime_types` | `("text/html;profile=mcp-app",)` | MIME types advertised for MCP Apps UI support. |
| `mcp_apps_settings` | `None` | Explicit settings object for `io.modelcontextprotocol/ui`; overrides `mcp_apps_mime_types` when set. |
| `oauth_client_credentials_enabled` | `False` | Advertise `io.modelcontextprotocol/oauth-client-credentials` support. |
| `oauth_client_credentials_settings` | `None` | Explicit settings object for OAuth client credentials support. |
| `enterprise_managed_authorization_enabled` | `False` | Advertise `io.modelcontextprotocol/enterprise-managed-authorization` support. |
| `enterprise_managed_authorization_settings` | `None` | Explicit settings object for enterprise-managed authorization support. |
| `extensions` | `None` | Dict of spec extension capabilities to advertise under `capabilities.extensions`. |
| `experimental_features` | `None` | Dict of experimental server features to advertise. |

Extension flags only advertise support. Auth token validation, enterprise policy
enforcement, and MCP Apps rendering/hosting remain the responsibility of the
application integrating the framework.

## Server Metadata

By default, `ServerSettings()` uses:

```python
ServerSettings(
    name="pymcp-kit",
    version="0.2.0",
)
```

Those defaults flow into both:

- the HTTP root payload returned from `GET /`
- `initialize.result.serverInfo` for session-based revisions
- `server/discover.result.serverInfo` for draft stateless revisions

## Current Non-Goals

- SSE and HTTP NDJSON transports are intentionally not bundled
- metrics and tracing are not part of the shipped surface
- the package focuses on a practical MCP server core rather than a full framework stack
