"""Tests for planning and validation tools 72-75."""

import asyncio

from _constants import EXPECTED_MIN_TOOL_COUNT

import td_mcp.server as server

PLANNING_TOOLS = {
    "td_plan_patch",
    "td_preflight_patch",
    "td_validate_recipe",
    "td_audit_project",
}


def test_planning_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    missing = PLANNING_TOOLS - names
    assert not missing, f"Missing planning tools: {sorted(missing)}"


def test_total_tool_count_meets_baseline():
    tools = asyncio.run(server.mcp.list_tools())
    assert len(tools) >= EXPECTED_MIN_TOOL_COUNT, (
        f"Expected >= {EXPECTED_MIN_TOOL_COUNT} tools, got {len(tools)}"
    )
