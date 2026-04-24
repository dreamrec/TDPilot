"""Tests for TD 2025 native system tools 78-83."""

import asyncio

import td_mcp.server as server

TD2025_TOOLS = {
    "td_python_env_status",
    "td_threading_status",
    "td_logger_status",
    "td_tdresources_inspect",
    "td_component_standardize",
    "td_color_pipeline",
}


def test_td2025_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}
    missing = TD2025_TOOLS - names
    assert not missing, f"Missing TD 2025 tools: {sorted(missing)}"
