"""Behavioural tests for the 5 Phase 3 MCP tools.

Uses the same MCP test harness as tests/test_tools_contract.py and
friends. Verifies envelope shapes + interaction with patch.* internals.
"""

from __future__ import annotations

import asyncio

import pytest

from td_mcp.tool_registry import mcp


def _find_tool(name: str):
    tools = asyncio.run(mcp.list_tools())
    for t in tools:
        if t.name == name:
            return t
    raise AssertionError(f"tool not registered: {name}")


def test_td_patch_plan_registered():
    t = _find_tool("td_patch_plan")
    # Schema should be flat (Bug-A discipline)
    props = t.inputSchema.get("properties", {})
    assert "target_root" in props
    assert list(props.keys()) != ["params"]


def test_td_patch_preview_registered():
    t = _find_tool("td_patch_preview")
    assert "plan" in t.inputSchema.get("properties", {})


def test_td_patch_apply_registered():
    t = _find_tool("td_patch_apply")
    props = t.inputSchema.get("properties", {})
    assert "plan" in props
    assert "auto_validate" in props


def test_td_patch_validate_registered():
    t = _find_tool("td_patch_validate")
    props = t.inputSchema.get("properties", {})
    assert "target_root" in props
    assert "capture_frames" in props
    # Flat schema — Bug A discipline
    assert list(props.keys()) != ["params"]


def test_td_patch_variations_registered():
    t = _find_tool("td_patch_variations")
    props = t.inputSchema.get("properties", {})
    assert "plan" in props
    assert "n" in props
    assert "strategies" in props
    # Flat schema
    assert list(props.keys()) != ["params"]
