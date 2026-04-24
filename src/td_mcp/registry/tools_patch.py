"""Patch Session MCP tools (Phase 3, v1.5.0).

Tools in this module (5):
    td_patch_plan        — build typed PatchPlan from intent/recipe/operations
    td_patch_preview     — human-readable + live_risk_flags (no mutation)
    td_patch_apply       — execute one undo block; returns PatchResult
    td_patch_validate    — composite errors + cook + frame checks on a subtree
    td_patch_variations  — derive N variants from a base PatchPlan

Thin delegators to src/td_mcp/patch/. The patch package is MCP-free;
this module adapts MCP Context + envelopes to the patch/* async API.

See docs/superpowers/specs/2026-04-24-v1.5.0-phase-3-patch-session-design.md
§5 for tool signatures.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field, ValidationError

from td_mcp import patch
from td_mcp import tool_registry as _tr  # intentional cycle — see registry/__init__.py
from td_mcp.errors import format_tool_error
from td_mcp.models.patch import PatchPlan, PatchPreview, ValidationPlan
from td_mcp.tool_registry import mcp
