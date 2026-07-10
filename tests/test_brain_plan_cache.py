from __future__ import annotations

import td_mcp.server as server  # noqa: F401 - initialize the registry before importing tool module
from td_mcp.models.brain import BrainPlan, ConceptGraph, VisualTaskSpec
from td_mcp.models.patch import PatchPlan, ValidationPlan
from td_mcp.registry import tools_brain


def _legacy_plan(plan_id: str) -> BrainPlan:
    task = VisualTaskSpec(intent=f"cache plan {plan_id}")
    return BrainPlan(
        id=plan_id,
        task=task,
        concept_graph=ConceptGraph(task=task),
        patch_plan=PatchPlan(
            intent=task.intent,
            target_root=task.target_root,
            source="operations",
            operations=[],
            undo_label="cache test",
            validation_plan=ValidationPlan(target_root=task.target_root),
        ),
    )


def test_brain_plan_cache_keeps_sixteen_recent_plans_and_latest_resource():
    tools_brain._BRAIN_PLANS.clear()
    for index in range(17):
        tools_brain._cache_brain_plan(_legacy_plan(f"plan-{index}"))

    assert len(tools_brain._BRAIN_PLANS) == 16
    assert tools_brain._get_cached_brain_plan("plan-0") is None
    assert tools_brain._get_cached_brain_plan("plan-1") is not None
    assert tools_brain._get_cached_brain_plan("plan-16")["id"] == "plan-16"

    latest = tools_brain.get_cached_resource("td://project/state")
    assert latest["latest_brain_plan"]["id"] == "plan-16"
