"""Config-driven authentication and authorization helpers."""

from __future__ import annotations

import asyncio
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import requests
from fastapi import Request

from ..protocol.json_types import JSONObject, JSONValue
from .authn import AuthenticationError, Principal, get_bearer_token
from .authz import AuthorizationError, AuthzRequest


def _as_json_value(value: object) -> JSONValue:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_as_json_value(v) for v in value]
    if isinstance(value, dict):
        out: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON objects must use string keys")
            out[key] = _as_json_value(item)
        return out
    raise ValueError(f"Unsupported JSON value type: {type(value).__name__}")


def load_json_config(path: str | Path) -> JSONObject:
    config_path = Path(path)
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    value = _as_json_value(raw)
    if not isinstance(value, dict):
        raise ValueError("config must be a JSON object")
    return value


def _as_list(value: JSONValue | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(entry) for entry in value if isinstance(entry, (str, int)) and str(entry)]
    return []


def _as_scope_list(value: JSONValue | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [scope for scope in value.split() if scope]
    return _as_list(value)


def _matches_any(patterns: Sequence[str], value: str) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


class TokenMapAuthenticator:  # pylint: disable=too-few-public-methods
    """Authenticator that maps Bearer tokens to static Principal definitions."""

    def __init__(self, token_map: Mapping[str, Mapping[str, JSONValue]]):
        self._token_map = dict(token_map)

    async def authenticate(self, request: Request) -> Principal | None:
        token = get_bearer_token(request)
        if not token:
            return None
        entry = self._token_map.get(token)
        if not entry:
            raise AuthenticationError("Invalid Bearer token")

        subject = entry.get("subject")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("Invalid token principal: missing subject")

        display_name = entry.get("display_name")
        if display_name is not None and not isinstance(display_name, str):
            display_name = None

        claims: dict[str, JSONValue] = {}
        raw_claims = entry.get("claims")
        if isinstance(raw_claims, Mapping):
            for key, item in raw_claims.items():
                if isinstance(key, str) and key:
                    claims[key] = item

        roles = set(_as_list(entry.get("roles")))
        scopes = set(_as_list(entry.get("scopes")))
        return Principal(
            subject=subject,
            display_name=display_name,
            roles=roles,
            scopes=scopes,
            claims=claims,
        )


class TokenIntrospectionAuthenticator:  # pylint: disable=too-few-public-methods
    """Authenticator that validates Bearer tokens through an introspection endpoint."""

    def __init__(
        self,
        introspection_url: str,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout: float = 5.0,
        token_type_hint: str = "access_token",
        subject_claim: str = "sub",
        display_name_claim: str | None = "name",
        scopes_claim: str = "scope",
        roles_claim: str | None = "roles",
        expected_audience: str | None = None,
        expected_resource: str | None = None,
        expected_issuer: str | None = None,
        verify_tls: bool = True,
        extra_params: Mapping[str, JSONValue] | None = None,
    ):
        if not introspection_url.strip():
            raise ValueError("introspection_url must not be empty")
        self._introspection_url = introspection_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._token_type_hint = token_type_hint
        self._subject_claim = subject_claim
        self._display_name_claim = display_name_claim
        self._scopes_claim = scopes_claim
        self._roles_claim = roles_claim
        self._expected_audience = expected_audience
        self._expected_resource = expected_resource
        self._expected_issuer = expected_issuer
        self._verify_tls = verify_tls
        self._extra_params = dict(extra_params or {})

    def _request_auth(self):
        if self._client_id is None:
            return None
        return (self._client_id, self._client_secret or "")

    @staticmethod
    def _extract_string(value: object) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None

    def _validate_claims(self, claims: Mapping[str, JSONValue]) -> None:
        active = claims.get("active")
        if active is not True:
            raise AuthenticationError("Invalid Bearer token")

        if self._expected_issuer is not None:
            issuer = self._extract_string(claims.get("iss"))
            if issuer != self._expected_issuer:
                raise AuthenticationError("Invalid token issuer")

        if self._expected_audience is not None:
            audience_values = _as_list(claims.get("aud"))
            if self._expected_audience not in audience_values:
                raise AuthenticationError("Invalid token audience")

        if self._expected_resource is not None:
            resource_values = _as_list(claims.get("resource"))
            if self._expected_resource not in resource_values:
                raise AuthenticationError("Invalid token resource")

    async def authenticate(self, request: Request) -> Principal | None:
        token = get_bearer_token(request)
        if not token:
            return None

        payload: dict[str, JSONValue] = {"token": token}
        if self._token_type_hint:
            payload["token_type_hint"] = self._token_type_hint
        payload.update(self._extra_params)

        try:
            response = await asyncio.to_thread(
                requests.post,
                self._introspection_url,
                data=payload,
                timeout=self._timeout,
                auth=self._request_auth(),
                verify=self._verify_tls,
                headers={"Accept": "application/json"},
            )
        except requests.RequestException as exc:
            raise AuthenticationError("Token introspection failed") from exc

        if response.status_code >= 400:
            raise AuthenticationError("Token introspection failed")

        try:
            raw_claims = response.json()
        except ValueError as exc:
            raise AuthenticationError("Token introspection returned invalid JSON") from exc

        if not isinstance(raw_claims, Mapping):
            raise AuthenticationError("Token introspection returned invalid JSON")

        claims: dict[str, JSONValue] = {}
        for key, value in raw_claims.items():
            if isinstance(key, str) and key:
                claims[key] = value  # requests already decodes JSON into JSON-compatible values

        self._validate_claims(claims)

        subject = self._extract_string(claims.get(self._subject_claim))
        if subject is None:
            raise AuthenticationError("Invalid token principal: missing subject")

        display_name = None
        if self._display_name_claim is not None:
            display_name = self._extract_string(claims.get(self._display_name_claim))

        roles = set(_as_list(claims.get(self._roles_claim))) if self._roles_claim is not None else set()
        scopes = set(_as_scope_list(claims.get(self._scopes_claim)))
        return Principal(
            subject=subject,
            display_name=display_name,
            roles=roles,
            scopes=scopes,
            claims=claims,
        )


@dataclass(frozen=True)
class Rule:
    methods: list[str]
    tool: str | None
    effect: str
    allow_anonymous: bool
    allow_subjects: list[str]
    allow_roles: list[str]
    allow_scopes: list[str]
    message: str | None

    @staticmethod
    def from_dict(data: Mapping[str, JSONValue]) -> "Rule":
        methods = _as_list(data.get("rpc_method") or data.get("methods"))
        if not methods:
            raise ValueError("rule missing rpc_method")
        tool_value = data.get("tool")
        tool = str(tool_value) if isinstance(tool_value, (str, int)) and str(tool_value) else None
        effect = str(data.get("effect") or "allow").lower()
        if effect not in {"allow", "deny"}:
            raise ValueError(f"invalid rule effect: {effect}")
        allow_anonymous = bool(data.get("allow_anonymous") or data.get("allowAnonymous"))
        allow_subjects = _as_list(data.get("allow_subjects") or data.get("allowSubjects"))
        allow_roles = _as_list(data.get("allow_roles") or data.get("allowRoles"))
        allow_scopes = _as_list(data.get("allow_scopes") or data.get("allowScopes"))
        message_value = data.get("message")
        message = (
            str(message_value)
            if isinstance(message_value, (str, int)) and str(message_value)
            else None
        )
        return Rule(
            methods=methods,
            tool=tool,
            effect=effect,
            allow_anonymous=allow_anonymous,
            allow_subjects=allow_subjects,
            allow_roles=allow_roles,
            allow_scopes=allow_scopes,
            message=message,
        )


class RuleBasedAuthorizer:  # pylint: disable=too-few-public-methods
    """Config-driven authorizer using ordered allow/deny rules."""

    def __init__(self, config: Mapping[str, JSONValue]):
        default_effect = str(config.get("default_effect") or config.get("defaultEffect") or "deny").lower()
        if default_effect not in {"allow", "deny"}:
            raise ValueError(f"invalid default_effect: {default_effect}")
        self._default_effect = default_effect
        self._hide_caps = bool(
            config.get("hide_unauthorized_capabilities") or config.get("hideUnauthorizedCapabilities")
        )
        self._hide_tools = bool(config.get("hide_unauthorized_tools") or config.get("hideUnauthorizedTools"))

        raw_rules = config.get("rules") or []
        if not isinstance(raw_rules, list):
            raise ValueError("authz.rules must be a list")
        rules: list[Rule] = []
        for rule in raw_rules:
            if not isinstance(rule, Mapping):
                raise ValueError("authz.rules entries must be objects")
            rules.append(Rule.from_dict(rule))
        self._rules = rules

        self._groups_claim = str(config.get("groups_claim") or config.get("groupsClaim") or "groups")
        group_map = config.get("groups_to_roles") or config.get("groupsToRoles") or {}
        self._groups_to_roles: dict[str, str] = {}
        if isinstance(group_map, Mapping):
            for key, value in group_map.items():
                if isinstance(key, (str, int)) and str(key) and isinstance(value, (str, int)) and str(value):
                    self._groups_to_roles[str(key)] = str(value)

    def _effective_roles(self, principal: Principal | None) -> set[str]:
        if not principal:
            return set()
        roles = set(principal.roles or set())
        claims = principal.claims
        if not isinstance(claims, Mapping) or not self._groups_to_roles:
            return roles
        groups = claims.get(self._groups_claim)
        if isinstance(groups, (str, int)):
            group_list = [str(groups)]
        elif isinstance(groups, list):
            group_list = [str(group) for group in groups if isinstance(group, (str, int)) and str(group)]
        else:
            group_list = []
        for group in group_list:
            for pattern, role in self._groups_to_roles.items():
                if fnmatch.fnmatch(group, pattern):
                    roles.add(role)
        return roles

    def _effective_scopes(self, principal: Principal | None) -> set[str]:
        if not principal:
            return set()
        return set(principal.scopes or set())

    def _rule_matches_request(self, rule: Rule, request: AuthzRequest) -> bool:
        rpc_method = request.rpc_method or ""
        tool_name = request.tool_name

        if not _matches_any(rule.methods, rpc_method):
            return False
        if rule.tool is not None:
            if tool_name is None:
                return False
            if not fnmatch.fnmatch(str(tool_name), rule.tool):
                return False
        return True

    def _evaluate(self, principal: Principal | None, request: AuthzRequest) -> Rule | None:
        for rule in self._rules:
            if not self._rule_matches_request(rule, request):
                continue

            has_allow_conditions = bool(rule.allow_subjects or rule.allow_roles or rule.allow_scopes)
            if principal is None:
                if rule.allow_anonymous or not has_allow_conditions:
                    return rule
                continue

            subject = principal.subject
            roles = self._effective_roles(principal)
            scopes = self._effective_scopes(principal)

            if not has_allow_conditions:
                return rule
            if rule.allow_subjects and subject in rule.allow_subjects:
                return rule
            if rule.allow_roles and set(rule.allow_roles) & roles:
                return rule
            if rule.allow_scopes and any(
                fnmatch.fnmatch(scope, allowed)
                for allowed in rule.allow_scopes
                for scope in scopes
            ):
                return rule

        return None

    def required_scopes_for(self, principal: Principal | None, request: AuthzRequest) -> tuple[str, ...]:
        """Return scopes from matching allow rules that the principal does not have."""

        current_scopes = self._effective_scopes(principal)
        required: list[str] = []

        for rule in self._rules:
            if not self._rule_matches_request(rule, request):
                continue
            if rule.effect == "deny":
                return ()
            if rule.effect != "allow" or not rule.allow_scopes:
                continue
            for scope in rule.allow_scopes:
                if scope not in required:
                    required.append(scope)

        missing = [
            scope
            for scope in required
            if not any(fnmatch.fnmatch(current_scope, scope) for current_scope in current_scopes)
        ]
        return tuple(missing)

    def _missing_scope_message(self, principal: Principal | None, request: AuthzRequest) -> str | None:
        current_scopes = self._effective_scopes(principal)
        for rule in self._rules:
            if not self._rule_matches_request(rule, request):
                continue
            if rule.effect == "deny":
                return None
            if rule.effect != "allow" or not rule.allow_scopes or not rule.message:
                continue
            if not any(
                fnmatch.fnmatch(current_scope, required_scope)
                for required_scope in rule.allow_scopes
                for current_scope in current_scopes
            ):
                return rule.message
        return None

    def _is_allowed(self, principal: Principal | None, request: AuthzRequest) -> bool:
        rule = self._evaluate(principal, request)
        if rule is None:
            return self._default_effect == "allow"
        return rule.effect == "allow"

    def authorize(self, principal: Principal | None, request: AuthzRequest) -> None:
        if request.rpc_method is None:
            return
        if self._is_allowed(principal, request):
            return
        rule = self._evaluate(principal, request)
        required_scopes = self.required_scopes_for(principal, request)
        raise AuthorizationError(
            (rule.message if rule and rule.message else None)
            or self._missing_scope_message(principal, request)
            or "Forbidden",
            required_scopes=required_scopes,
        )

    def filter_capabilities(self, principal: Principal | None, capabilities: JSONObject) -> JSONObject:
        if not self._hide_caps:
            return dict(capabilities)

        caps = dict(capabilities)
        tools_visible = self._is_allowed(principal, AuthzRequest(rpc_method="tools/list")) or self._is_allowed(
            principal,
            AuthzRequest(rpc_method="tools/call", tool_name="*"),
        )
        if not tools_visible:
            caps.pop("tools", None)
        return caps

    def filter_tools(self, principal: Principal | None, tools: Sequence[JSONObject]) -> list[JSONObject]:
        if not self._hide_tools:
            return list(tools)
        visible: list[JSONObject] = []
        for tool in tools:
            name = tool.get("name")
            tool_name = name if isinstance(name, str) else None
            if tool_name and self._is_allowed(principal, AuthzRequest(rpc_method="tools/call", tool_name=tool_name)):
                visible.append(tool)
        return visible

    def filter_prompts(self, principal: Principal | None, prompts: Sequence[JSONObject]) -> list[JSONObject]:
        _ = principal
        return list(prompts)

    def filter_resources(self, principal: Principal | None, resources: Sequence[JSONObject]) -> list[JSONObject]:
        _ = principal
        return list(resources)

    def filter_resource_templates(
        self,
        principal: Principal | None,
        templates: Sequence[JSONObject],
    ) -> list[JSONObject]:
        _ = principal
        return list(templates)


__all__ = [
    "RuleBasedAuthorizer",
    "TokenIntrospectionAuthenticator",
    "TokenMapAuthenticator",
    "load_json_config",
]
