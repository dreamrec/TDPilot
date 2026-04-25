"""Patch Session internal business logic.

This package is intentionally MCP-free. All functions here accept a
td_client-like object and (where needed) an UndoBlockSentinel, and
return typed models from td_mcp.models.patch. See
docs/superpowers/specs/2026-04-24-v1.5.0-phase-3-patch-session-design.md
for the authoritative design.
"""

from __future__ import annotations

from td_mcp.patch.applier import (
    NestedBlockError,
    PatchOperationArgsError,
    apply_plan,
)
from td_mcp.patch.planner import build_plan, preview_plan
from td_mcp.patch.undo_sentinel import UndoBlockSentinel
from td_mcp.patch.validator import validate_target
from td_mcp.patch.variants import generate_variants

__all__ = [
    "NestedBlockError",
    "PatchOperationArgsError",
    "UndoBlockSentinel",
    "apply_plan",
    "build_plan",
    "generate_variants",
    "preview_plan",
    "validate_target",
]
