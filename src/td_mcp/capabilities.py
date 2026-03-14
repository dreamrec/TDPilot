"""Client capability detection for adaptive feature behavior."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from td_mcp import normalize_transport
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class CapabilitySet:
    """Capability flags inferred from MCP request context and runtime config."""

    supports_resources: bool = False
    supports_subscriptions: bool = False
    supports_sampling: bool = False
    supports_sampling_tool_calls: bool = False
    supports_streamable_http: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    """Best-effort conversion to mapping."""
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(exclude_none=True)
        if isinstance(dumped, Mapping):
            return dumped
    if hasattr(value, "__dict__"):
        attrs = vars(value)
        if isinstance(attrs, Mapping):
            return attrs
    return {}


def detect_capabilities(ctx: Optional[Any] = None) -> CapabilitySet:
    """Infer client capability support from context and environment.

    The exact shape of context capability payloads differs between clients.
    This function intentionally uses permissive probing with safe defaults.
    """

    supports_streamable_http = normalize_transport(
        os.environ.get("TD_MCP_TRANSPORT", "stdio")
    ) == "streamable-http"
    if ctx is None:
        return CapabilitySet(supports_streamable_http=supports_streamable_http)

    request_ctx = getattr(ctx, "request_context", None)
    caps_source = None
    for attr in ("client_capabilities", "capabilities"):
        if hasattr(request_ctx, attr):
            caps_source = getattr(request_ctx, attr)
            break

    caps = _as_mapping(caps_source)
    resources = _as_mapping(caps.get("resources"))
    sampling = _as_mapping(caps.get("sampling"))

    return CapabilitySet(
        supports_resources=bool(resources),
        supports_subscriptions=bool(resources.get("subscribe") or resources.get("subscriptions")),
        supports_sampling=bool(sampling),
        supports_sampling_tool_calls=bool(sampling.get("toolCalls") or sampling.get("tool_calls")),
        supports_streamable_http=supports_streamable_http,
    )

