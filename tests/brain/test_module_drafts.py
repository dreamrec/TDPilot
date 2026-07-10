from __future__ import annotations

from td_mcp.brain.concept_compiler import compile_visual_task
from td_mcp.brain.module_drafts import review_module_draft
from td_mcp.models.brain import VisualTaskSpec


def _draft() -> dict:
    return {
        "build_intent": {"mode": "production", "operation": "create"},
        "module_graph": {
            "target_root": "/project1/build",
            "modules": [
                {
                    "id": "output",
                    "role": "output",
                    "technique_id": "stable_output_null",
                    "label": "Stable output",
                    "td_family": "TOP",
                    "inputs": [{"name": "image", "domain": "TOP"}],
                    "outputs": [{"name": "image", "domain": "TOP"}],
                    "source_ref": "/project1/build/source",
                }
            ],
            "edges": [],
            "output_module_id": "output",
        },
    }


def test_module_draft_compiles_to_brain_plan_with_artifacts() -> None:
    task = VisualTaskSpec(intent="Create a stable TOP output", target_root="/project1/build")
    compiled = compile_visual_task(task.intent, target_root=task.target_root)

    review = review_module_draft(
        _draft(),
        task=task,
        compiled_task=compiled,
        grounding_id="grounding:test",
    )

    assert review.accepted is True
    assert review.plan is not None
    assert review.plan.compiler_artifacts is not None
    assert review.plan.intent_coverage is not None
    assert review.plan.intent_coverage.complete is True
    assert review.plan.route == "host_authored"


def test_module_draft_rejects_target_escape() -> None:
    task = VisualTaskSpec(intent="Create a stable TOP output", target_root="/project1/build")
    compiled = compile_visual_task(task.intent, target_root=task.target_root)
    draft = _draft()
    draft["module_graph"]["target_root"] = "/project1/foreign"

    review = review_module_draft(
        draft,
        task=task,
        compiled_task=compiled,
        grounding_id="grounding:test",
    )

    assert review.accepted is False
    assert review.rejection_reasons == ["module_graph_target_mismatch"]


def test_module_draft_rejects_unknown_technique() -> None:
    task = VisualTaskSpec(intent="Create a stable TOP output", target_root="/project1/build")
    compiled = compile_visual_task(task.intent, target_root=task.target_root)
    draft = _draft()
    draft["module_graph"]["modules"][0]["technique_id"] = "invented"

    review = review_module_draft(
        draft,
        task=task,
        compiled_task=compiled,
        grounding_id="grounding:test",
    )

    assert review.accepted is False
    assert review.rejection_reasons == ["unknown_technique:invented"]
