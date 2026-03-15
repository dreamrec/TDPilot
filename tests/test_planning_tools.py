"""Tests for planning and validation tools 72-75."""

import asyncio
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
    assert not missing, "Missing planning tools: {}".format(sorted(missing))


def test_total_tool_count_at_least_86():
    tools = asyncio.run(server.mcp.list_tools())
    assert len(tools) >= 90, "Expected >= 90 tools, got {}".format(len(tools))
