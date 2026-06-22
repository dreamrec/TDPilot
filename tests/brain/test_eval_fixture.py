from __future__ import annotations

import json
from pathlib import Path

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain.planner import build_brain_plan

EVAL_PATH = Path(__file__).resolve().parent.parent / "evals" / "td_brain_golden.jsonl"


def _eval_cases() -> list[dict]:
    return [json.loads(line) for line in EVAL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _families_for(expected_ops: list[str]) -> dict[str, list[str]]:
    families: dict[str, list[str]] = {}
    for op_type in expected_ops:
        for suffix in ("TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT"):
            if op_type.endswith(suffix):
                families.setdefault(suffix, []).append(op_type)
                break
    return families


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _eval_cases(), ids=lambda case: case["id"])
async def test_golden_eval_case_maps_to_expected_profile_and_ops(case: dict):
    client = FakeTDClient(
        scripted={
            "families": {"families": _families_for(case["expected_ops"])},
            "nodes": {"nodes": case.get("existing_nodes") or []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=case["intent"],
        target_root=case["target_root"],
        constraints=case.get("constraints") if isinstance(case.get("constraints"), dict) else None,
    )

    if case.get("expected_blocked") is True:
        assert plan.blocked_questions
        assert plan.patch_plan.operations == []
        assert set(plan.concept_graph.operators) == set()
    else:
        assert plan.blocked_questions == []
        assert plan.concept_graph.profile == case["expected_profile"]
        assert set(case["expected_ops"]).issubset(set(plan.concept_graph.operators))
