"""Client capability detection for adaptive feature behavior."""

from __future__ import annotations

import importlib.metadata
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from td_mcp import normalize_transport


@dataclass(frozen=True)
class CapabilitySet:
    """Capability flags inferred from MCP request context and runtime config."""

    supports_resources: bool = False
    supports_subscriptions: bool = False
    supports_sampling: bool = False
    supports_sampling_tool_calls: bool = False
    supports_streamable_http: bool = False
    supports_tasks: bool = False
    supports_elicitation: bool = False
    transport_type: str = "stdio"
    mcp_sdk_version: str = ""
    td_build: str = ""

    def to_dict(self) -> dict[str, Any]:
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


def detect_capabilities(
    ctx: Any | None = None,
    *,
    td_build: str = "",
) -> CapabilitySet:
    """Infer client capability support from context and environment.

    The exact shape of context capability payloads differs between clients.
    This function intentionally uses permissive probing with safe defaults.
    """

    transport_raw = normalize_transport(os.environ.get("TD_MCP_TRANSPORT", "stdio"))
    supports_streamable_http = transport_raw == "streamable-http"

    try:
        mcp_sdk_version = importlib.metadata.version("mcp")
    except Exception:
        mcp_sdk_version = ""

    if ctx is None:
        return CapabilitySet(
            supports_streamable_http=supports_streamable_http,
            transport_type=transport_raw,
            mcp_sdk_version=mcp_sdk_version,
            td_build=td_build,
        )

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
        supports_tasks=bool(caps.get("tasks")),
        supports_elicitation=bool(caps.get("elicitation")),
        transport_type=transport_raw,
        mcp_sdk_version=mcp_sdk_version,
        td_build=td_build,
    )
