# Documentation Plan

This page tracks where the documentation stands and what gets written next, so
docs work stays deliberate instead of ad hoc.

## Current State

| Area | Page | Status |
| --- | --- | --- |
| Landing / overview | `index.md` | Done — value proposition, protocol surface, architecture diagram |
| Onboarding | `getting-started.md` | Done — install, app factory, both transports |
| Middleware | `middleware.md` | Done |
| Tasks | `tasks.md` | Done — execution flow diagram, opt-in, helpers, example |
| Security | `security.md` | Done — auth flow diagram, token map, introspection, authz rules |
| Runtime reference | `runtime-surface.md` | Done — revisions, stateless draft flow, endpoints |
| Docs infrastructure | `deployment.md` | Done |
| Release process | `release.md` | Done |

## Gaps To Fill Next

Ordered by expected reader value.

### Phase 1 — Reference completeness

- **API reference.** Generate from docstrings with `mkdocstrings[python]` so
  `create_app()`, registries, `ServerSettings`, task helpers, and the security
  types have a browsable reference instead of living only in guide prose.
- **Settings reference.** A dedicated page for `ServerSettings` and
  `MiddlewareConfig`: every knob, default, and which guide explains it.
- **Transports guide.** Streamable HTTP details (sessions, SSE streams,
  shutdown behavior, `http_validation` rules) and stdio framing in one place;
  today this is scattered across `runtime-surface.md` and `getting-started.md`.

### Phase 2 — Task-oriented guides

- **Resources and subscriptions.** `resources/subscribe`, update
  notifications, and the `subscriptions.py` transport surface.
- **Prompts and roots.** Short guides matching the depth tools already have.
- **Observability.** What `pymcp.observability.logging` emits and how to wire
  it into an existing logging setup.
- **Cookbook.** Promote `example/` (config-driven server, web-based example)
  into narrated recipes.

### Phase 3 — Operations and policy

- **Testing and conformance.** How to run the MCP conformance suite locally
  and what the CI baseline (`conformance-baseline.yml`) means.
- **Versioning policy.** Which MCP revisions are supported, how draft support
  is gated, and what the deprecation path looks like.
- **Troubleshooting / FAQ.** Start from real issues (session errors, 401/403
  challenges, task lifecycle confusion) as they come up.

## Conventions

- Every page must be reachable from `nav` in `mkdocs.yml`; builds run with
  `--strict`, so broken links and orphaned snippets fail CI.
- Diagrams are Mermaid fenced blocks (` ```mermaid `) rendered through
  `pymdownx.superfences` with `fence_code_format` and Material's built-in
  Mermaid support. Do **not** switch back to `fence_div_format` or add a
  custom Mermaid loader script: `fence_div_format` emits a plain `<div>`,
  the `minify` plugin collapses the newlines inside it, and Mermaid cannot
  parse the flattened source.
- Prefer one flow diagram plus focused code examples per guide over long
  prose; match the structure of `tasks.md` and `security.md`.
- Keep `README.md` links pointing at the hosted pages listed here.
