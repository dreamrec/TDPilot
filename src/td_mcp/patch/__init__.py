"""Patch Session internal business logic.

This package is intentionally MCP-free. All functions here accept a
td_client-like object and (where needed) an UndoBlockSentinel, and
return typed models from td_mcp.models.patch. See
docs/superpowers/specs/2026-04-24-v1.5.0-phase-3-patch-session-design.md
for the authoritative design.
"""

from __future__ import annotations

from td_mcp.patch.undo_sentinel import UndoBlockSentinel

__all__ = ["UndoBlockSentinel"]
