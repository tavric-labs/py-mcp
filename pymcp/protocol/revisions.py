"""Protocol revision registry and settings helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .extensions import MCP_TASKS


ProtocolMode = Literal["stable", "draft", "dual"]
ProtocolStatus = Literal["stable", "draft", "deprecated"]

LATEST_DRAFT_PROTOCOL_VERSION = "2026-07-28"
LATEST_STABLE_PROTOCOL_VERSION = "2025-11-25"

STABLE_PROTOCOL_VERSIONS = (
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)

DEFAULT_PROTOCOL_MODE: ProtocolMode = "stable"


@dataclass(frozen=True, slots=True)
class Extension:
    name: str
    feature: str


@dataclass(frozen=True, slots=True)
class ProtocolRevision:
    version: str
    status: ProtocolStatus
    stateless: bool
    requires_request_metadata: bool
    supports_initialization: bool
    supports_discovery: bool
    requires_result_type: bool
    features: frozenset[str]
    extensions: tuple[Extension, ...] = ()


_DRAFT_FEATURES = frozenset(
    {
        "tools",
        "prompts",
        "resources",
        "completions",
        "tasks",
        "subscriptions",
        "mrtr",
    }
)

_DRAFT_EXTENSIONS = (
    Extension(MCP_TASKS, "tasks"),
)

_LEGACY_FEATURES = frozenset(
    {
        "tools",
        "prompts",
        "resources",
        "logging",
        "completions",
        "tasks",
        "roots",
        "sampling",
        "elicitation",
        "ping",
    }
)

REVISION_2026_07_28 = ProtocolRevision(
    version=LATEST_DRAFT_PROTOCOL_VERSION,
    status="draft",
    stateless=True,
    requires_request_metadata=True,
    supports_initialization=False,
    supports_discovery=True,
    requires_result_type=True,
    features=_DRAFT_FEATURES,
    extensions=_DRAFT_EXTENSIONS,
)

_REVISION_BY_VERSION: dict[str, ProtocolRevision] = {
    REVISION_2026_07_28.version: REVISION_2026_07_28,
    **{
        version: ProtocolRevision(
            version=version,
            status="stable" if version == LATEST_STABLE_PROTOCOL_VERSION else "deprecated",
            stateless=False,
            requires_request_metadata=False,
            supports_initialization=True,
            supports_discovery=False,
            requires_result_type=False,
            features=_LEGACY_FEATURES,
        )
        for version in STABLE_PROTOCOL_VERSIONS
    },
}


def protocol_versions_for_mode(mode: ProtocolMode) -> tuple[str, ...]:
    if mode == "stable":
        return STABLE_PROTOCOL_VERSIONS
    if mode == "draft":
        return (LATEST_DRAFT_PROTOCOL_VERSION,)
    if mode == "dual":
        return (LATEST_DRAFT_PROTOCOL_VERSION, *STABLE_PROTOCOL_VERSIONS)
    raise ValueError("protocol_mode must be one of: stable, draft, dual")


def get_protocol_revision(version: str | None) -> ProtocolRevision | None:
    if version is None:
        return None
    return _REVISION_BY_VERSION.get(version)


def known_protocol_versions() -> tuple[str, ...]:
    return tuple(_REVISION_BY_VERSION)


def enabled_protocol_revisions(versions: tuple[str, ...]) -> tuple[ProtocolRevision, ...]:
    revisions: list[ProtocolRevision] = []
    for version in versions:
        revision = get_protocol_revision(version)
        if revision is None:
            raise ValueError(f"Unsupported protocol version configured: {version}")
        revisions.append(revision)
    return tuple(revisions)


def is_draft_protocol(version: str | None) -> bool:
    revision = get_protocol_revision(version)
    return bool(revision and revision.status == "draft")


def is_stateless_protocol(version: str | None) -> bool:
    revision = get_protocol_revision(version)
    return bool(revision and revision.stateless)


def extension_for_feature(revision: ProtocolRevision | None, feature: str) -> Extension | None:
    if revision is None:
        return None
    for extension in revision.extensions:
        if extension.feature == feature:
            return extension
    return None


__all__ = [
    "DEFAULT_PROTOCOL_MODE",
    "LATEST_DRAFT_PROTOCOL_VERSION",
    "LATEST_STABLE_PROTOCOL_VERSION",
    "Extension",
    "ProtocolMode",
    "ProtocolRevision",
    "STABLE_PROTOCOL_VERSIONS",
    "enabled_protocol_revisions",
    "extension_for_feature",
    "get_protocol_revision",
    "is_draft_protocol",
    "is_stateless_protocol",
    "known_protocol_versions",
    "protocol_versions_for_mode",
]
