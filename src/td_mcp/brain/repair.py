"""Deterministic, assertion-specific validation repair planning.

Repairs in this module are deliberately conservative.  They may only restore
an operation that was already part of the validated plan, pulse a known
feedback reset, or reduce an explicitly configured pathological resolution.
The planner never invents replacement visual content to make a visual probe
green.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from td_mcp.models.brain import ValidationIssue, ValidationReportV2
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan

_BLACK_FEEDBACK_CODES = {
    "black_feedback_output",
    "profile_probe_runtime_black_feedback_output",
    "profile_probe_runtime_empty_visual_output",
    "validation_black_feedback_output",
}
_STATIC_BINDING_CODES = {
    "missing_binding",
    "profile_probe_runtime_no_activity",
    "profile_probe_runtime_static_modulation",
    "static_binding",
    "static_or_missing_binding",
    "validation_static_binding",
}
_MISSING_CONNECTION_CODES = {
    "graph_connection_missing",
    "missing_connection",
    "missing_connection_or_reference",
    "missing_reference",
    "validation_missing_connection",
    "validation_missing_reference",
}
_RESOLUTION_CODES = {
    "resolution_mismatch",
    "validation_resolution_mismatch",
}
_COOK_COST_CODES = {
    "cook_health_stuck",
    "excessive_cook_cost",
    "validation_excessive_cook_cost",
}
_REFERENCE_PARAM_NAMES = {
    "camera",
    "chop",
    "comp",
    "dat",
    "geometry",
    "instanceop",
    "lights",
    "material",
    "sop",
    "top",
}
_RESOLUTION_RE = re.compile(r"(?P<width>[1-9][0-9]{1,4})\s*[xX]\s*(?P<height>[1-9][0-9]{1,4})")


def build_validation_repair_plan(
    original_plan: PatchPlan,
    validation_report: ValidationReportV2,
) -> PatchPlan | None:
    """Build the smallest safe repair for the first supported failed assertion.

    Returning ``None`` is intentional when the failed assertion does not expose
    enough evidence for a deterministic repair.  Callers must then roll back or
    leave the last validated state according to their transaction policy.
    """

    strategies: tuple[
        tuple[
            set[str], Callable[[PatchPlan, ValidationIssue], tuple[list[PatchOperation], list[str]] | None]
        ],
        ...,
    ] = (
        (_BLACK_FEEDBACK_CODES, _repair_black_feedback),
        (_STATIC_BINDING_CODES, _repair_binding),
        (_MISSING_CONNECTION_CODES, _repair_connection_or_reference),
        (_RESOLUTION_CODES, _repair_resolution),
        (_COOK_COST_CODES, _repair_cook_cost),
    )
    for issue in validation_report.issues:
        for codes, strategy in strategies:
            if issue.code not in codes:
                continue
            repair = strategy(original_plan, issue)
            if repair is None:
                # The code is known but its cause is not safely repairable from
                # this plan.  Do not let a broader strategy guess at a fix.
                break
            operations, required_ops = repair
            return _repair_plan(
                original_plan,
                issue=issue,
                operations=operations,
                required_ops=required_ops,
            )
    return None


def _repair_plan(
    original: PatchPlan,
    *,
    issue: ValidationIssue,
    operations: list[PatchOperation],
    required_ops: list[str],
) -> PatchPlan:
    label = _repair_label(issue.code)
    return PatchPlan(
        intent=f"Assertion-specific repair for {issue.code}",
        target_root=original.target_root,
        source="operations",
        operations=operations,
        required_ops=sorted(set(required_ops)),
        risk_flags=[f"auto-repair:{label}"],
        undo_label=f"td brain auto-repair: {label}",
        validation_plan=ValidationPlan(
            target_root=original.validation_plan.target_root,
            capture_frames=list(original.validation_plan.capture_frames),
        ),
    )


def _repair_label(code: str) -> str:
    if code in _BLACK_FEEDBACK_CODES:
        return "black-feedback"
    if code in _STATIC_BINDING_CODES:
        return "binding-readback"
    if code in _MISSING_CONNECTION_CODES:
        return "connection-reference"
    if code in _RESOLUTION_CODES:
        return "resolution"
    return "cook-cost"


def _repair_black_feedback(
    plan: PatchPlan,
    issue: ValidationIssue,
) -> tuple[list[PatchOperation], list[str]] | None:
    del issue
    created = _created_nodes(plan)
    feedback_paths = sorted(path for path, op_type in created.items() if op_type == "feedbackTOP")
    if not feedback_paths:
        return None

    operations: list[PatchOperation] = []
    # A Feedback TOP can retain a dead/black buffer even after its input and
    # target reference are corrected.  Resetting that known state is the
    # smallest deterministic repair; it does not fabricate replacement pixels.
    for path in feedback_paths:
        operations.append(PatchOperation(kind="set_params", target=path, args={"params": {"reset": True}}))

    # Restore a decay value only when the original plan explicitly configured
    # a value that guarantees black output.  Do not tune an otherwise valid
    # artistic choice.
    for operation in plan.operations:
        if operation.kind != "set_params" or not operation.target:
            continue
        if created.get(operation.target) != "levelTOP":
            continue
        params = operation.args.get("params")
        if not isinstance(params, dict):
            continue
        repaired: dict[str, Any] = {}
        opacity = _static_number(params.get("opacity"))
        brightness = _static_number(params.get("brightness1"))
        if opacity is not None and opacity <= 0:
            repaired["opacity"] = 0.94
        if brightness is not None and brightness <= 0:
            repaired["brightness1"] = 1.0
        if repaired:
            operations.append(
                PatchOperation(kind="set_params", target=operation.target, args={"params": repaired})
            )
    return operations, ["feedbackTOP"]


def _repair_binding(
    plan: PatchPlan,
    issue: ValidationIssue,
) -> tuple[list[PatchOperation], list[str]] | None:
    candidates: list[PatchOperation] = []
    for operation in plan.operations:
        if operation.kind != "set_params" or not operation.target:
            continue
        params = operation.args.get("params")
        if not isinstance(params, dict):
            continue
        expression_params = {
            name: value
            for name, value in params.items()
            if isinstance(value, dict) and isinstance(value.get("expr"), str) and value["expr"].strip()
        }
        if not expression_params:
            continue
        if issue.path and operation.target != issue.path:
            continue
        candidates.append(
            PatchOperation(kind="set_params", target=operation.target, args={"params": expression_params})
        )
    if not candidates and issue.path:
        # The issue path may name the source CHOP rather than the bound target.
        return _repair_binding(plan, issue.model_copy(update={"path": None}))
    if not candidates:
        return None
    # Reapply one exact compiler-authored binding. Multiple unrelated bindings
    # are not mutated in response to one failed assertion.
    return [candidates[-1]], _required_types_for_operations(plan, [candidates[-1]])


def _repair_connection_or_reference(
    plan: PatchPlan,
    issue: ValidationIssue,
) -> tuple[list[PatchOperation], list[str]] | None:
    connections = [operation for operation in plan.operations if operation.kind == "connect"]
    if issue.path:
        matches = [
            operation
            for operation in connections
            if issue.path in {str(operation.args.get("from") or ""), str(operation.args.get("to") or "")}
        ]
        if matches:
            operation = matches[0].model_copy(deep=True)
            return [operation], _required_types_for_operations(plan, [operation])

    reference_candidates: list[PatchOperation] = []
    for operation in plan.operations:
        if operation.kind != "set_params" or not operation.target:
            continue
        params = operation.args.get("params")
        if not isinstance(params, dict):
            continue
        references = {
            name: value
            for name, value in params.items()
            if name.lower() in _REFERENCE_PARAM_NAMES and _is_explicit_reference(value)
        }
        if references and (not issue.path or operation.target == issue.path):
            reference_candidates.append(
                PatchOperation(kind="set_params", target=operation.target, args={"params": references})
            )
    if reference_candidates:
        operation = reference_candidates[0]
        return [operation], _required_types_for_operations(plan, [operation])
    if len(connections) == 1:
        operation = connections[0].model_copy(deep=True)
        return [operation], _required_types_for_operations(plan, [operation])
    return None


def _repair_resolution(
    plan: PatchPlan,
    issue: ValidationIssue,
) -> tuple[list[PatchOperation], list[str]] | None:
    created = _created_nodes(plan)
    expected = _resolution_from_message(issue.message)
    candidates: list[PatchOperation] = []
    for operation in plan.operations:
        if operation.kind != "set_params" or not operation.target:
            continue
        if created.get(operation.target) != "resolutionTOP" and "resolution" not in operation.target.lower():
            continue
        params = operation.args.get("params")
        if not isinstance(params, dict):
            continue
        width = expected[0] if expected else _static_int(params.get("resolutionw"))
        height = expected[1] if expected else _static_int(params.get("resolutionh"))
        if width is None or height is None:
            continue
        candidates.append(
            PatchOperation(
                kind="set_params",
                target=operation.target,
                args={
                    "params": {
                        "outputresolution": "custom",
                        "resolutionw": width,
                        "resolutionh": height,
                    }
                },
            )
        )
    if not candidates:
        return None
    return [candidates[0]], ["resolutionTOP"]


def _repair_cook_cost(
    plan: PatchPlan,
    issue: ValidationIssue,
) -> tuple[list[PatchOperation], list[str]] | None:
    del issue
    created = _created_nodes(plan)
    # Only reduce an explicitly configured oversized resolution.  Guessing at
    # simulation counts, GLSL work-group sizes, or cook flags could change the
    # requested behavior and is therefore not a bounded repair.
    for operation in plan.operations:
        if operation.kind != "set_params" or not operation.target:
            continue
        if created.get(operation.target) != "resolutionTOP" and "resolution" not in operation.target.lower():
            continue
        params = operation.args.get("params")
        if not isinstance(params, dict):
            continue
        width = _static_int(params.get("resolutionw"))
        height = _static_int(params.get("resolutionh"))
        if width is None or height is None or (width <= 1920 and height <= 1080):
            continue
        scale = min(1920 / width, 1080 / height)
        repaired_width = max(1, int(width * scale))
        repaired_height = max(1, int(height * scale))
        return (
            [
                PatchOperation(
                    kind="set_params",
                    target=operation.target,
                    args={
                        "params": {
                            "outputresolution": "custom",
                            "resolutionw": repaired_width,
                            "resolutionh": repaired_height,
                        }
                    },
                )
            ],
            ["resolutionTOP"],
        )
    return None


def _created_nodes(plan: PatchPlan) -> dict[str, str]:
    result: dict[str, str] = {}
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        name = str(operation.args.get("name") or "").strip()
        op_type = str(operation.args.get("op_type") or "").strip()
        if not name or not op_type:
            continue
        parent = str(operation.target or plan.target_root).rstrip("/") or "/"
        result[f"{parent}/{name}".replace("//", "/")] = op_type
    return result


def _required_types_for_operations(plan: PatchPlan, operations: list[PatchOperation]) -> list[str]:
    created = _created_nodes(plan)
    paths: set[str] = set()
    for operation in operations:
        if operation.target:
            paths.add(operation.target)
        if operation.kind == "connect":
            paths.update(str(operation.args.get(key) or "") for key in ("from", "to"))
    return sorted({created[path] for path in paths if path in created})


def _is_explicit_reference(value: Any) -> bool:
    if isinstance(value, str):
        return value.startswith("/") or value.startswith("../") or value.startswith("./")
    if isinstance(value, dict):
        raw = value.get("val")
        return isinstance(raw, str) and _is_explicit_reference(raw)
    return False


def _static_number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("val")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _static_int(value: Any) -> int | None:
    number = _static_number(value)
    return int(number) if number is not None and number > 0 else None


def _resolution_from_message(message: str) -> tuple[int, int] | None:
    match = _RESOLUTION_RE.search(message)
    if not match:
        return None
    return int(match.group("width")), int(match.group("height"))


__all__ = ["build_validation_repair_plan"]
