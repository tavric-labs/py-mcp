# Security

`pymcp-kit` ships optional authentication and authorization hooks. They are off by default and are activated through `create_app(...)` or `MiddlewareConfig(...)`.

## Bearer Token Authentication

`TokenMapAuthenticator` maps static Bearer tokens to `Principal` objects:

```python
from pymcp import create_app
from pymcp.security import TokenMapAuthenticator


app = create_app(
    authn=TokenMapAuthenticator(
        {
            "secret-token": {
                "subject": "alice",
                "display_name": "Alice",
                "roles": ["ops"],
                "scopes": ["tools:*", "tasks:*"],
                "claims": {"tenant": "acme"},
            }
        }
    ),
    require_authn=True,
)
```

With `require_authn=True`, unauthenticated requests receive `401`.

By default, the `WWW-Authenticate` challenge derives `resource_metadata` from the inbound request. If your deployment needs a public URL that differs from the request URL, set `resource_metadata_url` on `OAuthProtectedResourceConfig`.

## Token Introspection

`TokenIntrospectionAuthenticator` validates each Bearer token against a remote introspection endpoint and builds the request principal from the returned claims:

```python
from pymcp import create_app
from pymcp.security import TokenIntrospectionAuthenticator


app = create_app(
    authn=TokenIntrospectionAuthenticator(
        "https://auth.example.com/oauth2/introspect",
        client_id="pymcp-server",
        client_secret="super-secret",
        expected_audience="mcp-api",
        expected_resource="https://mcp.example.com/test-mcp",
        expected_issuer="https://auth.example.com",
    ),
    require_authn=True,
)
```

Use this when your deployment validates opaque access tokens through an authorization server or gateway instead of local JWT verification.
Set `expected_audience` and/or `expected_resource` to the public MCP resource URI or audience your authorization server issues tokens for.

Access tokens in the URI query string are rejected by the HTTP auth middleware.

## OAuth Protected Resource Metadata

Configure `OAuthProtectedResourceConfig` when clients should discover the MCP
resource server metadata described by RFC 9728:

```python
from pymcp import create_app
from pymcp.security import OAuthProtectedResourceConfig, TokenMapAuthenticator


app = create_app(
    authn=TokenMapAuthenticator({"secret-token": {"subject": "alice"}}),
    require_authn=True,
    oauth=OAuthProtectedResourceConfig(
        authorization_servers=["https://auth.example.com"],
        resource="https://mcp.example.com/mcp",
        scopes_supported=["tools:read", "tools:call"],
        bearer_methods_supported=["header"],
    ),
)
```

The HTTP transport serves metadata at:

- `/.well-known/oauth-protected-resource`
- `/.well-known/oauth-protected-resource/mcp`

Authentication failures include a Bearer `WWW-Authenticate` challenge with a
`resource_metadata` URL. Set `resource_metadata_url` when the public URL differs
from the inbound request URL behind a proxy or gateway.

## Rule-Based Authorization

`RuleBasedAuthorizer` evaluates ordered allow/deny rules:

```python
from pymcp import create_app
from pymcp.security import RuleBasedAuthorizer, TokenMapAuthenticator


authn = TokenMapAuthenticator(
    {
        "secret-token": {
            "subject": "alice",
            "roles": ["ops"],
            "scopes": ["tools:*", "tasks:*"],
        }
    }
)

authz = RuleBasedAuthorizer(
    {
        "default_effect": "deny",
        "hide_unauthorized_capabilities": True,
        "hide_unauthorized_tools": True,
        "rules": [
            {
                "methods": ["initialize", "ping", "tools/list", "tasks/list", "tasks/get", "tasks/result"],
                "allow_subjects": ["alice"],
                "effect": "allow",
            },
            {
                "methods": ["tools/call"],
                "tool": "deploy_*",
                "allow_roles": ["ops"],
                "effect": "allow",
            },
        ],
    }
)

app = create_app(
    authn=authn,
    authz=authz,
    require_authn=True,
)
```

## Loading Authz Rules From JSON

```python
from pymcp.security import RuleBasedAuthorizer, load_json_config


authz = RuleBasedAuthorizer(load_json_config("authz_policy.json"))
```

## Useful Knobs

- `hide_unauthorized_capabilities`: remove disallowed capability fragments from `initialize`
- `hide_unauthorized_tools`: filter `tools/list` output to only visible tools
- `auth_exempt_paths`: skip auth middleware on selected HTTP routes

## Task Visibility Under Auth

When authentication is enabled, task ownership follows the authenticated principal rather than the raw session ID. That matters for `tasks/list`, `tasks/get`, `tasks/cancel`, and `tasks/result`.

## Practical Layout

- keep token maps or authn setup in `config.py`
- keep JSON authz policies in a separate file
- pass `authn`, `authz`, and `require_authn` into `create_app()`
- use capability and tool filtering if clients should not even discover restricted functionality

## Scope Boundary

`pymcp-kit` provides HTTP authentication hooks, authorization hooks, and OAuth protected-resource metadata discovery for MCP resource servers.

It does not implement a full authorization server, a full OAuth client, or token issuance flows. Those belong in your deployment architecture, not in this server toolkit.
