"""Hint pack runtime for ``td_get_hints`` and the v1.6.0 hint-injection layer.

A *hint* is a short, source-cited rule that surfaces at the moment of risk
— either explicitly via ``td_get_hints``, or auto-injected into the
response of a high-risk tool (eg. creating a feedbackTOP returns hints
about its canonical chain).

Packs are YAML files under ``packs/topics/`` (broad: ``feedback``,
``glsl``, ``render_pipeline`` …) or ``packs/op_types/`` (narrow:
``feedbackTOP``, ``geometryCOMP``). They ship with the plugin and are
loaded once at server startup.
"""

from td_mcp.hints.loader import (
    ALLOWED_SURFACES,
    PACK_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    Hint,
    HintMatch,
    HintPack,
    HintRegistry,
    default_registry,
)
from td_mcp.hints.orchestrator import (
    AUTO_INJECT_RULES,
    TOOL_SURFACES,
    auto_inject_hints,
    query_hints,
)

__all__ = [
    "ALLOWED_SURFACES",
    "AUTO_INJECT_RULES",
    "Hint",
    "HintMatch",
    "HintPack",
    "HintRegistry",
    "PACK_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "TOOL_SURFACES",
    "auto_inject_hints",
    "default_registry",
    "query_hints",
]
