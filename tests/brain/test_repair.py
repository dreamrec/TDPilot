from __future__ import annotations

from td_mcp.brain.repair import build_validation_repair_plan
from td_mcp.models.brain import ValidationIssue, ValidationReportV2
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan


def _plan(operations: list[PatchOperation]) -> PatchPlan:
    return PatchPlan(
        target_root="/project1",
        source="operations",
        operations=operations,
        required_ops=["nullTOP"],
        undo_label="repair test",
        validation_plan=ValidationPlan(target_root="/project1"),
    )


def test_builds_minimal_visual_output_repair_plan_from_validation_issue():
    original = _plan(
        [PatchOperation(kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"})]
    )
    report = ValidationReportV2(
        target_root="/project1",
        ok=False,
        checks=["cheap_visual_metrics"],
        issues=[
            ValidationIssue(
                severity="error",
                code="profile_probe_runtime_empty_visual_output",
                message="visual output empty",
                path="/project1",
            )
        ],
    )

    repair = build_validation_repair_plan(original, report)

    assert repair is not None
    assert repair.source == "operations"
    assert repair.required_ops == ["constantTOP", "nullTOP"]
    assert repair.risk_flags == ["auto-repair:visual-output-sample"]
    assert [operation.kind for operation in repair.operations] == ["create_node", "set_params", "connect"]
    assert repair.operations[0].args["op_type"] == "constantTOP"
    assert repair.operations[-1].args["to"] == "/project1/out1"


def test_repair_plan_builder_returns_none_for_unhandled_issues():
    original = _plan(
        [PatchOperation(kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"})]
    )
    report = ValidationReportV2(
        target_root="/project1",
        ok=False,
        checks=["td_errors"],
        issues=[
            ValidationIssue(
                severity="error",
                code="unknown_validation_issue",
                message="not repairable",
                path="/project1",
            )
        ],
    )

    assert build_validation_repair_plan(original, report) is None
