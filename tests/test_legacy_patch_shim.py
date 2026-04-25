"""Ensures td_plan_patch / td_preflight_patch return the pre-v1.5.0
dict shape after the Phase 3 shim refactor.
"""

from __future__ import annotations

import pytest

import td_mcp.tool_registry as _registry
from td_mcp.registry import tools_planning


def _patch_services(monkeypatch, td_client):
    """Monkeypatch _get_client and _get_technique_store on the registry module
    so tools_planning can call them without a real TDClient or TechniqueStore."""
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: td_client)
    monkeypatch.setattr(_registry, "_get_technique_store", lambda _ctx: None)


@pytest.mark.asyncio
async def test_td_plan_patch_legacy_shape(mcp_ctx, td_client, monkeypatch):
    """Verify dict shape: success + plan.{intent, target_path, steps, note, ...}"""
    _patch_services(monkeypatch, td_client)
    td_client.responses = {"nodes": {"nodes": []}}
    result = await tools_planning.td_plan_patch(mcp_ctx, intent="feedback trail", target_path="/project1")
    assert result["success"] is True
    plan = result["plan"]
    assert "intent" in plan
    assert "target_path" in plan
    assert "steps" in plan
    assert "note" in plan
    assert "current_node_count" in plan
    assert "existing_names" in plan


@pytest.mark.asyncio
async def test_td_plan_patch_legacy_values(mcp_ctx, td_client, monkeypatch):
    """Verify the concrete values in the legacy plan dict."""
    _patch_services(monkeypatch, td_client)
    td_client.responses = {"nodes": {"nodes": []}}
    result = await tools_planning.td_plan_patch(mcp_ctx, intent="feedback trail", target_path="/project1")
    assert result["success"] is True
    plan = result["plan"]
    assert plan["intent"] == "feedback trail"
    assert plan["target_path"] == "/project1"
    assert plan["current_node_count"] == 0
    assert plan["existing_names"] == []
    # intent=feedback trail should produce macro suggestion
    assert len(plan["steps"]) > 0
    step = plan["steps"][0]
    assert step["op"] == "create_macro"
    assert step["macro_type"] == "feedback_loop"
    assert "note" in plan
    assert "mutate" in plan["note"].lower()


@pytest.mark.asyncio
async def test_td_plan_patch_empty_steps_has_next_actions(mcp_ctx, td_client, monkeypatch):
    """Verify next_actions appears when no steps are generated (no match)."""
    _patch_services(monkeypatch, td_client)
    td_client.responses = {"nodes": {"nodes": []}}
    result = await tools_planning.td_plan_patch(
        mcp_ctx, intent="xyzzy unrecognized intent that wont match", target_path="/project1"
    )
    assert result["success"] is True
    plan = result["plan"]
    assert plan["steps"] == []
    assert "next_actions" in plan
    assert len(plan["next_actions"]) > 0


@pytest.mark.asyncio
async def test_td_plan_patch_probes_live_nodes(mcp_ctx, td_client, monkeypatch):
    """Verify node probe fills current_node_count and existing_names."""
    _patch_services(monkeypatch, td_client)
    td_client.responses = {
        "nodes": {
            "nodes": [
                {"name": "noise1", "path": "/project1/noise1"},
                {"name": "level1", "path": "/project1/level1"},
            ]
        }
    }
    result = await tools_planning.td_plan_patch(mcp_ctx, intent="feedback trail", target_path="/project1")
    assert result["success"] is True
    plan = result["plan"]
    assert plan["current_node_count"] == 2
    assert "noise1" in plan["existing_names"]
    assert "level1" in plan["existing_names"]
