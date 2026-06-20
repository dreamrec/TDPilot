"""Transactional PatchPlan execution for model-directed TD edits."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from td_mcp import patch
from td_mcp.brain.validators import build_validation_report_v2, validate_reference_params_for_plan
from td_mcp.models.brain import TransactionOptions, TransactionResult, ValidationIssue, ValidationReportV2
from td_mcp.models.patch import PatchPlan, PatchPreview
from td_mcp.patch.undo_sentinel import UndoBlockSentinel

SnapshotCallback = Callable[[str], Awaitable[str | None]]
RestoreCallback = Callable[[str], Awaitable[dict[str, Any] | None]]


async def apply_transaction(
    td_client,
    plan: PatchPlan,
    *,
    options: TransactionOptions | None = None,
    sentinel: UndoBlockSentinel,
    concept_profile: str | None = None,
    macro_engine=None,
    create_snapshot: SnapshotCallback | None = None,
    restore_snapshot: RestoreCallback | None = None,
) -> TransactionResult:
    """Apply a PatchPlan with preflight, snapshot, validation, and rollback."""
    opts = options or TransactionOptions()
    result = TransactionResult(plan_id=plan.id, status="blocked", options=opts)

    if len(plan.operations) > opts.max_ops:
        result.failed_reason = f"plan has {len(plan.operations)} operations; max_ops is {opts.max_ops}"
        return result

    if opts.preflight:
        reference_issues = validate_reference_params_for_plan(plan)
        if reference_issues:
            result.failed_reason = "; ".join(issue.message for issue in reference_issues)
            result.validation_failed = True
            result.validation_report = _reference_param_report(
                target_root=plan.target_root,
                concept_profile=concept_profile,
                issues=reference_issues,
            )
            return result

        preview_dict = await patch.preview_plan(td_client, plan)
        result.preview = PatchPreview(**preview_dict)
        target_missing = [
            flag for flag in result.preview.live_risk_flags if flag.startswith("target-missing:")
        ]
        if target_missing:
            result.failed_reason = "; ".join(target_missing)
            return result

    if opts.dry_run:
        result.status = "dry_run"
        return result

    if opts.snapshot_before and create_snapshot is not None:
        try:
            result.before_snapshot_id = await create_snapshot(plan.target_root)
        except Exception as exc:  # noqa: BLE001
            result.failed_reason = f"snapshot_before failed: {exc}"
            return result

    try:
        apply_result = await patch.apply_plan(
            td_client,
            plan,
            sentinel=sentinel,
            auto_validate=True,
            macro_engine=macro_engine,
        )
    except patch.NestedBlockError as exc:
        result.failed_reason = str(exc)
        return result

    result.apply_result = apply_result
    result.failed_op = apply_result.failed_op
    result.failed_reason = apply_result.failed_reason

    validation_report = build_validation_report_v2(
        target_root=plan.target_root,
        profile=opts.validation_profile,
        concept_profile=concept_profile,
        patch_result=apply_result,
    )
    result.validation_report = validation_report
    result.validation_failed = not validation_report.ok

    should_rollback = (
        apply_result.status == "broken"
        and opts.rollback_on_apply_failure
        or result.validation_failed
        and opts.rollback_on_validation_failure
    )
    if should_rollback:
        await _rollback(td_client, result, restore_snapshot=restore_snapshot)
        result.status = "rolled_back" if result.rollback_performed else "broken"
        return result

    result.status = apply_result.status
    return result


async def _rollback(
    td_client,
    result: TransactionResult,
    *,
    restore_snapshot: RestoreCallback | None,
) -> None:
    try:
        await td_client.request("project/lifecycle", {"action": "undo"})
        result.rollback_performed = True
        return
    except Exception as exc:  # noqa: BLE001
        result.rollback_error = str(exc)

    if result.before_snapshot_id and restore_snapshot is not None:
        try:
            restored = await restore_snapshot(result.before_snapshot_id)
            failures = []
            if isinstance(restored, dict):
                failures = restored.get("failures", [])
            if not failures:
                result.rollback_performed = True
                result.rollback_error = None
                return
        except Exception as exc:  # noqa: BLE001
            result.rollback_error = str(exc)

    result.needs_manual_recovery = True


def _reference_param_report(
    *,
    target_root: str,
    concept_profile: str | None,
    issues: list[ValidationIssue],
) -> ValidationReportV2:
    severity_counts: dict[str, int] = {}
    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
    return ValidationReportV2(
        profile="structural_visual_safe",
        concept_profile=concept_profile,
        target_root=target_root,
        ok=False,
        checks=["reference_params"],
        issues=issues,
        severity_counts=severity_counts,
        cheap_metrics={},
        summary=f"{len(issues)} reference parameter issue(s)",
    )
