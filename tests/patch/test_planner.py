"""Tests for src/td_mcp/patch/planner.py."""

from __future__ import annotations

import pytest

from patch.conftest import FakeTDClient
from td_mcp.models.patch import PatchOperation, PatchPlan
from td_mcp.patch.planner import build_plan


class StubTechniqueStore:
    def __init__(self, recipes: dict):
        self._recipes = recipes

    def get(self, recipe_id: str, scope: str = "project"):
        return self._recipes.get(recipe_id)


class StubCardIndex:
    def __init__(self, known_types: set[str]):
        self._known = known_types

    def get_operator(self, op_type: str):
        return {"type": op_type} if op_type in self._known else None


@pytest.mark.asyncio
async def test_operations_path_preserves_ops():
    client = FakeTDClient()
    plan = await build_plan(
        td_client=client,
        target_root="/p",
        operations=[{"kind": "create_node", "target": "/p", "args": {"op_type": "noise", "name": "n1"}}],
    )
    assert plan.source == "operations"
    assert len(plan.operations) == 1
    assert plan.operations[0].kind == "create_node"


@pytest.mark.asyncio
async def test_recipe_path(monkeypatch):
    store = StubTechniqueStore(
        {
            "recipe-x": {
                "technique": {
                    "recipe": {
                        "name": "Feedback",
                        "nodes": {
                            "f": {"type": "feedback", "name": "feedback1"},
                        },
                    }
                }
            },
        }
    )
    plan = await build_plan(
        td_client=FakeTDClient(),
        target_root="/p",
        recipe_id="recipe-x",
        technique_store=store,
    )
    assert plan.source == "recipe"
    assert plan.source_recipe_id == "recipe-x"
    assert plan.operations[0].kind == "create_node"


@pytest.mark.asyncio
async def test_intent_path_matches_macro():
    # Uses the existing _INTENT_MACRO_KEYWORDS table (feedback → feedback_loop)
    plan = await build_plan(
        td_client=FakeTDClient(),
        target_root="/p",
        intent="feedback trail",
    )
    assert plan.source == "intent_heuristic"
    assert len(plan.operations) == 1
    assert plan.operations[0].kind == "macro"


@pytest.mark.asyncio
async def test_precedence_operations_over_recipe_over_intent():
    store = StubTechniqueStore({"r": {"technique": {"recipe": {"nodes": {}}}}})
    plan = await build_plan(
        td_client=FakeTDClient(),
        target_root="/p",
        operations=[{"kind": "create_node", "args": {"op_type": "noise"}}],
        recipe_id="r",
        intent="feedback",
        technique_store=store,
    )
    assert plan.source == "operations"


@pytest.mark.asyncio
async def test_no_inputs_raises():
    with pytest.raises(ValueError, match="requires one of"):
        await build_plan(td_client=FakeTDClient(), target_root="/p")


@pytest.mark.asyncio
async def test_unknown_op_type_prefixed():
    idx = StubCardIndex(known_types={"noise"})
    plan = await build_plan(
        td_client=FakeTDClient(),
        target_root="/p",
        operations=[
            {"kind": "create_node", "args": {"op_type": "noise", "name": "n1"}},
            {"kind": "create_node", "args": {"op_type": "zzzz_unknown", "name": "n2"}},
        ],
        card_index=idx,
    )
    assert "noise" in plan.required_ops
    assert "unknown:zzzz_unknown" in plan.required_ops


@pytest.mark.asyncio
async def test_risk_flags_mass_and_affects_root():
    ops = [{"kind": "set_params", "target": "/p/n", "args": {"params": {"a": 1}}}] * 25
    plan = await build_plan(
        td_client=FakeTDClient(),
        target_root="/",
        operations=ops,
    )
    assert "mass-change" in plan.risk_flags
    assert "affects-root" in plan.risk_flags
