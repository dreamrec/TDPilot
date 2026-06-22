"""Deterministic validation repair planning for failed brain transactions."""

from __future__ import annotations

from td_mcp.models.brain import ValidationReportV2
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan

_VISUAL_OUTPUT_REPAIR_CODES = {
    "profile_probe_runtime_empty_visual_output",
    "profile_probe_runtime_black_feedback_output",
    "profile_probe_runtime_trivial_top_output",
}


def build_validation_repair_plan(
    original_plan: PatchPlan,
    validation_report: ValidationReportV2,
) -> PatchPlan | None:
    """Build a minimal corrective PatchPlan for known validation failures."""
    if not any(issue.code in _VISUAL_OUTPUT_REPAIR_CODES for issue in validation_report.issues):
        return None
    output_path = _first_created_null_top_path(original_plan)
    if not output_path:
        return None
    parent, _name = output_path.rsplit("/", 1)
    parent = parent or "/"
    repair_name = "tdpilot_repair_visual_constant"
    repair_path = f"{parent.rstrip('/')}/{repair_name}".replace("//", "/")
    return PatchPlan(
        intent="Auto-repair empty visual TOP output with a visible constant source",
        target_root=original_plan.target_root,
        source="operations",
        operations=[
            PatchOperation(
                kind="create_node",
                target=parent,
                args={"op_type": "constantTOP", "name": repair_name},
            ),
            PatchOperation(
                kind="set_params",
                target=repair_path,
                args={"params": {"color": [0.18, 0.22, 0.3, 1.0]}},
            ),
            PatchOperation(
                kind="connect",
                target=parent,
                args={"from": repair_path, "to": output_path, "from_output": 0, "to_input": 0},
            ),
        ],
        required_ops=["constantTOP", "nullTOP"],
        risk_flags=["auto-repair:visual-output-sample"],
        undo_label="td brain auto-repair: visual output sample",
        validation_plan=ValidationPlan(target_root=original_plan.target_root),
    )


def _first_created_null_top_path(plan: PatchPlan) -> str | None:
    paths: list[tuple[str, str]] = []
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        if str(operation.args.get("op_type") or "") != "nullTOP":
            continue
        name = str(operation.args.get("name") or "")
        if not name:
            continue
        parent = operation.target or plan.target_root
        paths.append((name, f"{parent.rstrip('/')}/{name}".replace("//", "/")))
    for name, path in paths:
        if name == "out1":
            return path
    return paths[0][1] if paths else None


__all__ = ["build_validation_repair_plan"]
