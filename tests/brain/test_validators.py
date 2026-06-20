from __future__ import annotations

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain.transaction import apply_transaction
from td_mcp.brain.validators import (
    checks_for_profile,
    classify_intent_profile,
    validate_reference_params_for_plan,
)
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.undo_sentinel import UndoBlockSentinel


def _patch_plan(operations: list[PatchOperation], *, required_ops: list[str] | None = None) -> PatchPlan:
    return PatchPlan(
        intent="test reference params",
        target_root="/project1",
        source="operations",
        operations=operations,
        required_ops=required_ops or [],
        undo_label="test reference params",
        validation_plan=ValidationPlan(target_root="/project1"),
    )


def test_checks_for_profile_combines_structural_and_concept_checks():
    checks = checks_for_profile("structural_visual_safe", "glsl")

    assert "graph_structure" in checks
    assert "td_errors" in checks
    assert "shader_source_present" in checks
    assert "compile_state" in checks


def test_profile_classifier_does_not_match_ui_inside_build():
    profile = classify_intent_profile("Build a custom parameter control rig with default values")

    assert profile == "control_rig"


def test_profile_classifier_splits_glsl_material_from_top_shader():
    assert classify_intent_profile("build a GLSL material with vertex shader") == "glsl_material"
    assert classify_intent_profile("write a GLSL POP attribute shader") == "glsl_pop"
    assert classify_intent_profile("write a GLSL fragment shader TOP") == "glsl"


def test_reference_param_validator_accepts_shader_render_and_material_refs():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "pixel"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "vertex"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslMAT", "name": "mat"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/mat",
                args={"params": {"vdat": "/project1/vertex", "pdat": "/project1/pixel"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="set_params", target="/project1/geo", args={"params": {"material": "/project1/mat"}}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "cam"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/cam", "geometry": "/project1/geo"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "circlePOP", "name": "pop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimple", "name": "preview"}
            ),
            PatchOperation(
                kind="set_params", target="/project1/preview", args={"params": {"pop": "/project1/pop"}}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glsl", "name": "top_shader"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/top_shader",
                args={"params": {"pixeldat": "/project1/pixel"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslPOP", "name": "pop_shader"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/pop_shader",
                args={"params": {"computedat": "/project1/pixel"}},
            ),
        ],
        required_ops=[
            "glslMAT",
            "geometryCOMP",
            "cameraCOMP",
            "renderTOP",
            "rendersimpleTOP",
            "glslTOP",
            "glslPOP",
        ],
    )

    assert validate_reference_params_for_plan(plan) == []


def test_reference_param_validator_rejects_missing_required_refs():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslMAT", "name": "mat"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimpleTOP", "name": "preview"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslPOP", "name": "pop_shader"}
            ),
        ],
        required_ops=["glslMAT", "geometryCOMP", "renderTOP", "rendersimpleTOP", "glslPOP"],
    )

    issues = validate_reference_params_for_plan(plan)
    messages = "\n".join(issue.message for issue in issues)

    assert all(issue.code == "missing_reference_param" for issue in issues)
    assert "/project1/mat" in messages
    assert "vdat" in messages and "pdat" in messages
    assert "/project1/geo" in messages and "material" in messages
    assert "/project1/render" in messages and "camera" in messages and "geometry" in messages
    assert "/project1/preview" in messages and "pop" in messages
    assert "/project1/pop_shader" in messages and "computedat" in messages


def test_reference_param_validator_rejects_wrong_created_target_type():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "cam"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/geo", "geometry": "/project1/cam"}},
            ),
        ],
        required_ops=["geometryCOMP", "cameraCOMP", "renderTOP"],
    )

    issues = validate_reference_params_for_plan(plan)

    assert {issue.code for issue in issues} == {"invalid_reference_param"}
    assert any("camera" in issue.message and "cameraCOMP" in issue.message for issue in issues)
    assert any("geometry" in issue.message and "geometryCOMP" in issue.message for issue in issues)


@pytest.mark.asyncio
async def test_transaction_preflight_blocks_invalid_reference_params_before_apply():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glsl", "name": "shader"}
            ),
        ],
        required_ops=["glslTOP"],
    )
    client = FakeTDClient(scripted={"project/lifecycle": {"snapshot_id": "unused"}})

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="glsl",
    )

    assert result.status == "blocked"
    assert result.failed_reason
    assert "pixeldat" in result.failed_reason
    assert result.apply_result is None
    assert result.validation_report is not None
    assert result.validation_report.ok is False
    assert result.validation_report.checks == ["reference_params"]
