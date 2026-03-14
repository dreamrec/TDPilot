"""Tests for the 8 knowledge tool handlers (tools 64-71)."""

import asyncio

import td_mcp.server as server


KNOWLEDGE_TOOLS = {
    "td_search_official_docs",
    "td_get_operator_doc",
    "td_get_param_help",
    "td_lookup_snippets",
    "td_lookup_palette_component",
    "td_get_release_delta",
    "td_get_build_compatibility",
    "td_describe_surface",
}


def test_knowledge_tools_registered():
    """All 8 knowledge tool names are present on the mcp instance."""
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    missing = KNOWLEDGE_TOOLS - names
    assert not missing, f"Missing knowledge tools: {sorted(missing)}"


def test_total_tool_count_at_least_71():
    """Total tool count should be >= 71 after knowledge tools are added."""
    tools = asyncio.run(server.mcp.list_tools())
    assert len(tools) >= 71, f"Expected >= 71 tools, got {len(tools)}"
