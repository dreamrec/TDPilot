"""Tests for official recommendation tools 84-86."""

import asyncio
from pathlib import Path

from _constants import EXPECTED_MIN_TOOL_COUNT

import td_mcp.server as server
import td_mcp.tool_registry as tool_registry
from td_mcp.knowledge.card_index import CardIndex

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


def test_find_official_example_returns_structured_op_snippet_examples(mcp_ctx, service_container):
    """Official example lookup should expose concrete OP Snippets metadata.

    A broad snippet-card hit is not enough for POP/GLSL workflows: callers need
    an actionable example target and source URL that can be opened from
    TouchDesigner's Help > Operator Snippets browser.
    """
    cards_dir = Path(__file__).resolve().parent.parent / "src" / "td_mcp" / "knowledge" / "cards"
    service_container.card_index = CardIndex(cards_dir)
    service_container.td_build = "2025.32460"

    result = asyncio.run(
        tool_registry.td_find_official_example(
            mcp_ctx,
            "GLSL POP attribute shader",
            family="POP",
        )
    )

    examples = result["examples"]
    structured = [item for item in examples if item["type"] == "official_snippet_example"]

    assert structured
    glsl_pop = next(item for item in structured if item["id"] == "op_snippets_glsl_pop_attribute_compute")
    assert glsl_pop["source_url"] == "https://docs.derivative.ca/OP_Snippets"
    assert "https://docs.derivative.ca/Write_a_GLSL_POP" in glsl_pop["supporting_urls"]
    assert "glslPOP" in glsl_pop["operators"]
    assert "TDIndex" in " ".join(glsl_pop["topics"])
    assert "Help > Operator Snippets" in glsl_pop["access_path"]
