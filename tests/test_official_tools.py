"""Tests for official recommendation tools 84-86."""
import asyncio
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
    assert not missing, "Missing official tools: {}".format(sorted(missing))


def test_total_tool_count_at_least_86():
    """Total tool count should be >= 90 after official recommendation tools."""
    tools = asyncio.run(server.mcp.list_tools())
    assert len(tools) >= 90, "Expected >= 90 tools, got {}".format(len(tools))
