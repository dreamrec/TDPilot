"""Tests for official recommendation tools 84-86."""

import asyncio

from _constants import EXPECTED_MIN_TOOL_COUNT

import td_mcp.server as server

OFFICIAL_TOOLS = {
    "td_recommend_official_component",
    "td_find_official_example",
    "td_explain_better_way",
}


def test_official_tools_registered():
    """All 3 official recommendation tool names are present on the mcp instance."""
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    missing = OFFICIAL_TOOLS - names
    assert not missing, f"Missing official tools: {sorted(missing)}"


def test_total_tool_count_meets_baseline():
    """Total tool count meets the shared baseline (see tests/_constants.py)."""
    tools = asyncio.run(server.mcp.list_tools())
    assert len(tools) >= EXPECTED_MIN_TOOL_COUNT, (
        f"Expected >= {EXPECTED_MIN_TOOL_COUNT} tools, got {len(tools)}"
    )
