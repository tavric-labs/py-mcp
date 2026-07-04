# PyMCP Kit

<div class="hero" markdown>

Capability-first MCP server tooling for FastAPI. `pymcp-kit` keeps the built-in transport surface small, exposes app-scoped registries, and ships the MCP features you typically need first: tools, prompts, resources, roots, task-aware execution, optional auth hooks, OAuth protected-resource metadata, and opt-in draft MCP support.

<div class="hero-actions" markdown>
[Get Started](getting-started.md){ .md-button .md-button--primary }
[Runtime Surface](runtime-surface.md){ .md-button }
</div>

</div>

<div class="pymcp-grid" markdown>

<div class="pymcp-card" markdown>

### Small transport surface

Use Streamable HTTP at `/mcp` for networked clients and stdio for subprocess-based MCP hosts.

</div>

<div class="pymcp-card" markdown>

### App-scoped registries

Register tools, prompts, and resources globally for simple setups, then let `create_app()` snapshot them into an isolated app runtime.

</div>

<div class="pymcp-card" markdown>

### Tasks that stay useful

Opt tools into task execution, emit progress, request user input, support cancellation, and return results without flattening structured payloads.

</div>

<div class="pymcp-card" markdown>

### Security when you need it

Add bearer-token authentication, rule-based authorization, token introspection, and OAuth protected-resource metadata without turning the package into a large framework.

</div>

<div class="pymcp-card" markdown>

### Spec conformant

Passes the official [MCP conformance suite](https://github.com/modelcontextprotocol/conformance) in full against the [2025-11-25 spec](https://modelcontextprotocol.io/specification/2025-11-25), verified in CI on every change.

</div>

</div>

## Quick Install

```bash
pip install pymcp-kit
```

## What Ships Today

- Streamable HTTP mounted at `/mcp`
- Stdio transport through `run_stdio_server(app)`
- Stable MCP revisions by default, with opt-in draft `2026-07-28` stateless support
- Tool, prompt, and resource registries
- Roots and resource subscriptions
- Task-aware tool execution with progress, cancellation, and elicitation
- Optional authentication, authorization, and OAuth protected-resource metadata hooks

## Main Protocol Surface

- Lifecycle: `initialize`, `ping`, `notifications/initialized`, `notifications/cancelled`
- Tools: `tools/list`, `tools/call`
- Prompts: `prompts/list`, `prompts/get`
- Resources: `resources/list`, `resources/read`, `resources/subscribe`, `resources/unsubscribe`
- Roots: `roots/list`
- Tasks: `tasks/list`, `tasks/get`, `tasks/cancel`, `tasks/result`
- Draft discovery: `server/discover` when draft mode is enabled

## Read Next

- [Getting Started](getting-started.md): installation, the basic app factory flow, and the built-in transports.
- [Tasks](tasks.md): task-aware tool execution, progress, cancellation, and result polling.
- [Security](security.md): bearer tokens, rule-based authorization, and capability filtering.
- [Runtime Surface](runtime-surface.md): protocol revisions, draft stateless flow, endpoints, and capability settings.
- [Docs Deployment](deployment.md): how this site is built and published with GitHub Pages.
- [Release Process](release.md): version bump, tag, GitHub Release, and PyPI publishing flow.
