"""OAuth/OIDC discovery helpers for HTTP MCP transports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence
from urllib.parse import quote, urlparse

from fastapi import Request

from ..protocol.json_types import JSONObject, JSONValue


def _json_object(value: dict[str, JSONValue]) -> JSONObject:
    return dict(value)


def _validate_absolute_url(value: str, *, field_name: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc or parsed.fragment:
        raise ValueError(f"{field_name} must be an absolute URL")
    return value


def _metadata_url_from_resource_uri(resource_uri: str) -> str:
    parsed = urlparse(_validate_absolute_url(resource_uri, field_name="resource"))
    suffix = "/.well-known/oauth-protected-resource"
    path = parsed.path.lstrip("/")
    if path:
        suffix = f"{suffix}/{path}"
    return f"{parsed.scheme}://{parsed.netloc}{suffix}"


@dataclass(frozen=True, slots=True)
class OAuthProtectedResourceConfig:
    """Configuration for RFC 9728 protected resource metadata."""

    authorization_servers: Sequence[str]
    resource: str | None = None
    resource_metadata_url: str | None = None
    scopes_supported: Sequence[str] = field(default_factory=tuple)
    bearer_methods_supported: Sequence[str] = ("header",)
    resource_name: str | None = None
    documentation_uri: str | None = None
    extra_metadata: JSONObject = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.authorization_servers, str) or not self.authorization_servers:
            raise ValueError("authorization_servers must not be empty")

        validated_servers = tuple(
            _validate_absolute_url(server, field_name="authorization_servers")
            for server in self.authorization_servers
        )
        object.__setattr__(self, "authorization_servers", validated_servers)

        if self.resource is not None:
            object.__setattr__(
                self,
                "resource",
                _validate_absolute_url(self.resource, field_name="resource"),
            )

        if self.resource_metadata_url is not None:
            object.__setattr__(
                self,
                "resource_metadata_url",
                _validate_absolute_url(self.resource_metadata_url, field_name="resource_metadata_url"),
            )

    def resolved_metadata_url(self, request: Request) -> str:
        if self.resource_metadata_url is not None:
            return self.resource_metadata_url
        if self.resource is not None:
            return _metadata_url_from_resource_uri(self.resource)
        return protected_resource_metadata_url(request)

    def metadata(self, *, resource: str) -> JSONObject:
        payload: dict[str, JSONValue] = {
            "resource": self.resource or resource,
            "authorization_servers": list(self.authorization_servers),
        }
        if self.scopes_supported:
            payload["scopes_supported"] = list(self.scopes_supported)
        if self.bearer_methods_supported:
            payload["bearer_methods_supported"] = list(self.bearer_methods_supported)
        if self.resource_name:
            payload["resource_name"] = self.resource_name
        if self.documentation_uri:
            payload["resource_documentation"] = self.documentation_uri
        payload.update(self.extra_metadata)
        return _json_object(payload)


def canonical_resource_uri(request: Request, *, path: str = "/mcp") -> str:
    """Build a canonical MCP resource URI from the inbound HTTP request."""

    base = str(request.base_url).rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def protected_resource_metadata_url(request: Request, *, path: str | None = None) -> str:
    base = str(request.base_url).rstrip("/")
    suffix = "/.well-known/oauth-protected-resource"
    if path:
        normalized = path if path.startswith("/") else f"/{path}"
        suffix = f"{suffix}{normalized}"
    return f"{base}{suffix}"


def _quote_auth_param(value: str) -> str:
    return quote(value, safe=":/._~!$&'()*+,;=- ")


def build_www_authenticate(
    request: Request,
    *,
    scopes: Sequence[str] | None = None,
    error: str | None = None,
    error_description: str | None = None,
    metadata_url: str | None = None,
) -> str:
    """Build a Bearer challenge with MCP protected resource discovery."""

    params: list[tuple[str, str]] = [
        ("resource_metadata", metadata_url or protected_resource_metadata_url(request)),
    ]
    if error:
        params.append(("error", error))
    if scopes:
        params.append(("scope", " ".join(dict.fromkeys(scopes))))
    if error_description:
        params.append(("error_description", error_description))
    rendered = ", ".join(f'{key}="{_quote_auth_param(value)}"' for key, value in params)
    return f"Bearer {rendered}"


__all__ = [
    "OAuthProtectedResourceConfig",
    "build_www_authenticate",
    "canonical_resource_uri",
    "protected_resource_metadata_url",
]
