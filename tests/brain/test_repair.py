from __future__ import annotations

import pytest

from td_mcp.brain.repair import build_validation_repair_plan
from td_mcp.models.brain import ValidationIssue, ValidationReportV2
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan


def _plan(operations: list[PatchOperation]) -> PatchPlan:
    return PatchPlan(
        target_root="/project1",
        source="operations",
        operations=operations,
        required_ops=[],
        undo_label="repair test",
        validation_plan=ValidationPlan(target_root="/project1", capture_frames=["/project1/out1"]),
    )


def _report(code: str, *, path: str | None = None, message: str = "validation failed") -> ValidationReportV2:
    return ValidationReportV2(
        target_root="/project1",
        ok=False,
        checks=["task-specific-contract"],
        issues=[
            ValidationIssue(
                severity="error",
                code=code,
                message=message,
                path=path,
            )
        ],
    )


def test_black_feedback_repair_resets_state_without_inventing_visual_content():
    original = _plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "feedbackTOP", "name": "feedback1"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "levelTOP", "name": "decay1"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/decay1",
                args={"params": {"opacity": 0.0}},
            ),
        ]
    )

    repair = build_validation_repair_plan(original, _report("black_feedback_output"))

    assert repair is not None
    assert repair.risk_flags == ["auto-repair:black-feedback"]
    assert repair.required_ops == ["feedbackTOP"]
    assert [operation.kind for operation in repair.operations] == ["set_params", "set_params"]
    assert repair.operations[0].target == "/project1/feedback1"
    assert repair.operations[0].args == {"params": {"reset": True}}
    assert repair.operations[1].args == {"params": {"opacity": 0.94}}
    assert all(operation.args.get("op_type") != "constantTOP" for operation in repair.operations)


def test_empty_output_without_feedback_has_no_fake_constant_repair():
    original = _plan(
        [PatchOperation(kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"})]
    )

    assert (
        build_validation_repair_plan(
            original,
            _report("profile_probe_runtime_empty_visual_output"),
        )
        is None
    )


def test_binding_repair_reapplies_exact_compiler_authored_expression():
    expression = "op('/project1/audio_out')['low']"
    original = _plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "levelTOP", "name": "visual_level"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/visual_level",
                args={"params": {"opacity": {"expr": expression}, "brightness1": 1.0}},
            ),
        ]
    )

    repair = build_validation_repair_plan(
        original,
        _report("static_or_missing_binding", path="/project1/visual_level"),
    )

    assert repair is not None
    assert repair.risk_flags == ["auto-repair:binding-readback"]
    assert repair.operations == [
        PatchOperation(
            kind="set_params",
            target="/project1/visual_level",
            args={"params": {"opacity": {"expr": expression}}},
        )
    ]


def test_missing_connection_repair_replays_only_matching_validated_edge():
    original = _plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "noiseTOP", "name": "source"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "out1"},
            ),
            PatchOperation(
                kind="connect",
                target="/project1",
                args={
                    "from": "/project1/source",
                    "to": "/project1/out1",
                    "from_output": 0,
                    "to_input": 0,
                },
            ),
        ]
    )

    repair = build_validation_repair_plan(
        original,
        _report("missing_connection_or_reference", path="/project1/out1"),
    )

    assert repair is not None
    assert repair.risk_flags == ["auto-repair:connection-reference"]
    assert repair.operations == [original.operations[-1]]
    assert repair.required_ops == ["noiseTOP", "nullTOP"]


@pytest.mark.parametrize(
    ("code", "message", "expected"),
    [
        ("resolution_mismatch", "expected 1280x720 but observed 3840x2160", (1280, 720)),
        ("excessive_cook_cost", "cook budget exceeded", (1920, 1080)),
    ],
)
def test_resolution_and_cook_repairs_are_bounded(
    code: str,
    message: str,
    expected: tuple[int, int],
):
    original = _plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "resolutionTOP", "name": "normalize_resolution"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/normalize_resolution",
                args={
                    "params": {
                        "outputresolution": "custom",
                        "resolutionw": 3840,
                        "resolutionh": 2160,
                    }
                },
            ),
        ]
    )

    repair = build_validation_repair_plan(original, _report(code, message=message))

    assert repair is not None
    params = repair.operations[0].args["params"]
    assert (params["resolutionw"], params["resolutionh"]) == expected
    assert repair.operations[0].target == "/project1/normalize_resolution"


def test_repair_plan_builder_returns_none_for_unhandled_issues():
    original = _plan(
        [PatchOperation(kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"})]
    )

    assert build_validation_repair_plan(original, _report("unknown_validation_issue")) is None
