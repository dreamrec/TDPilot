"""Transactional PatchPlan execution for model-directed TD edits."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from td_mcp import patch
from td_mcp.brain.code_harness import (
    patch_plan_generated_code_runtime_contracts,
    validate_generated_code_runtime_contracts,
    validate_patch_plan_generated_code,
)
from td_mcp.brain.param_semantics import validate_patch_plan_parameter_contract
from td_mcp.brain.repair import build_validation_repair_plan
from td_mcp.brain.validation_engine import to_validation_report_v2, validate_contract
from td_mcp.brain.validators import (
    build_validation_report_v2,
    static_profile_probe_metrics_for_plan,
    static_profile_probe_metrics_for_profiles,
    validate_reference_params_for_plan,
)
from td_mcp.models.brain import TransactionOptions, TransactionResult, ValidationIssue, ValidationReportV2
from td_mcp.models.build import ValidationContract
from td_mcp.models.patch import PatchPlan, PatchPreview
from td_mcp.patch.undo_sentinel import UndoBlockSentinel

SnapshotCallback = Callable[[str], Awaitable[str | None]]
RestoreCallback = Callable[[str], Awaitable[dict[str, Any] | None]]
ParamPreflightCallback = Callable[..., Any]


async def apply_transaction(
    td_client,
    plan: PatchPlan,
    *,
    options: TransactionOptions | None = None,
    sentinel: UndoBlockSentinel,
    concept_profile: str | None = None,
    concept_profiles: Iterable[str | None] | None = None,
    macro_engine=None,
    create_snapshot: SnapshotCallback | None = None,
    restore_snapshot: RestoreCallback | None = None,
    param_preflight: ParamPreflightCallback | None = None,
    validation_contract: ValidationContract | None = None,
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

        param_semantics_issues = validate_patch_plan_parameter_contract(plan)
        if param_semantics_issues:
            result.failed_reason = "; ".join(issue.message for issue in param_semantics_issues)
            result.validation_failed = True
            result.validation_report = _param_semantics_report(
                target_root=plan.target_root,
                concept_profile=concept_profile,
                issues=param_semantics_issues,
            )
            return result

        code_issues = validate_patch_plan_generated_code(plan)
        if code_issues:
            result.failed_reason = "; ".join(issue.message for issue in code_issues)
            result.validation_failed = True
            result.validation_report = _generated_code_report(
                target_root=plan.target_root,
                concept_profile=concept_profile,
                issues=code_issues,
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
            param_preflight=param_preflight,
            param_semantics_policy=opts.param_semantics_policy,
        )
    except patch.NestedBlockError as exc:
        result.failed_reason = str(exc)
        return result

    result.apply_result = apply_result
    result.failed_op = apply_result.failed_op
    result.failed_reason = apply_result.failed_reason
    if apply_result.undo_block_opened:
        result.undo_blocks_opened += 1

    profile_layers = _transaction_concept_profiles(
        concept_profile=concept_profile,
        concept_profiles=concept_profiles,
    )
    validation_report = await _build_selected_validation_report(
        td_client,
        plan,
        apply_result,
        options=opts,
        concept_profile=concept_profile,
        concept_profiles=profile_layers,
        validation_contract=validation_contract,
    )
    result.validation_report = validation_report
    result.validation_failed = not validation_report.ok
    if result.validation_failed and opts.auto_repair and opts.max_repair_attempts > 0:
        current_report = validation_report
        for _attempt_number in range(opts.max_repair_attempts):
            repaired_report = await _attempt_validation_repair(
                td_client,
                plan,
                result,
                current_report,
                options=opts,
                sentinel=sentinel,
                concept_profile=concept_profile,
                concept_profiles=profile_layers,
                macro_engine=macro_engine,
                param_preflight=param_preflight,
                validation_contract=validation_contract,
            )
            if repaired_report is None:
                break
            current_report = repaired_report
            result.validation_report = repaired_report
            result.validation_failed = not repaired_report.ok
            if repaired_report.ok:
                break

    should_rollback = (
        apply_result.status == "broken"
        and opts.rollback_on_apply_failure
        or result.validation_failed
        and opts.rollback_on_validation_failure
    )
    if should_rollback:
        created_paths = tuple(apply_result.created_paths or _predicted_created_node_paths(plan))
        await _rollback(
            td_client,
            result,
            restore_snapshot=restore_snapshot,
            undo_block_count=result.undo_blocks_opened,
            created_node_paths=created_paths,
            changed_params=tuple(apply_result.changed_params),
            connections_made=tuple(apply_result.connections_made),
        )
        result.status = "rolled_back" if result.rollback_performed else "broken"
        return result

    result.status = apply_result.status
    return result


async def _build_transaction_validation_report(
    td_client,
    plan: PatchPlan,
    apply_result,
    *,
    options: TransactionOptions,
    concept_profile: str | None,
    concept_profiles: Iterable[str | None],
) -> ValidationReportV2:
    profile_layers = [str(profile) for profile in concept_profiles if profile]
    if len(profile_layers) > 1:
        cheap_metrics = static_profile_probe_metrics_for_profiles(
            plan,
            validation_profile=options.validation_profile,
            concept_profiles=profile_layers,
        )
    else:
        cheap_metrics = static_profile_probe_metrics_for_plan(
            plan,
            validation_profile=options.validation_profile,
            concept_profile=concept_profile,
        )
    runtime_contracts = patch_plan_generated_code_runtime_contracts(plan)
    runtime_report: dict[str, Any] | None = None
    if runtime_contracts:
        runtime_report = await validate_generated_code_runtime_contracts(td_client, runtime_contracts)
        cheap_metrics["generated_code_runtime"] = {
            "contract_count": runtime_report["contract_count"],
            "checked_contract_count": runtime_report["checked_contract_count"],
            "evidence": runtime_report["evidence"],
        }
    await _validate_runtime_profile_probes(td_client, plan, cheap_metrics)
    _collect_visual_quality_metrics(cheap_metrics)
    validation_report = build_validation_report_v2(
        target_root=plan.target_root,
        profile=options.validation_profile,
        concept_profile=concept_profile,
        concept_profiles=profile_layers,
        patch_result=apply_result,
        cheap_metrics=cheap_metrics,
        visual_quality_policy=options.visual_quality_policy,
    )
    if runtime_report is not None:
        _merge_generated_code_runtime_report(validation_report, runtime_report)
    return validation_report


async def _build_selected_validation_report(
    td_client,
    plan: PatchPlan,
    apply_result,
    *,
    options: TransactionOptions,
    concept_profile: str | None,
    concept_profiles: Iterable[str | None],
    validation_contract: ValidationContract | None,
) -> ValidationReportV2:
    if validation_contract is not None:
        contract_report = await validate_contract(td_client, validation_contract)
        return to_validation_report_v2(contract_report)
    return await _build_transaction_validation_report(
        td_client,
        plan,
        apply_result,
        options=options,
        concept_profile=concept_profile,
        concept_profiles=concept_profiles,
    )


async def _attempt_validation_repair(
    td_client,
    plan: PatchPlan,
    result: TransactionResult,
    validation_report: ValidationReportV2,
    *,
    options: TransactionOptions,
    sentinel: UndoBlockSentinel,
    concept_profile: str | None,
    concept_profiles: Iterable[str | None],
    macro_engine=None,
    param_preflight: ParamPreflightCallback | None = None,
    validation_contract: ValidationContract | None = None,
) -> ValidationReportV2 | None:
    repair_plan = build_validation_repair_plan(plan, validation_report)
    if repair_plan is None:
        return None
    attempt = {
        "status": "planned",
        "source_issue_codes": [issue.code for issue in validation_report.issues],
        "repair_plan": repair_plan.model_dump(mode="json"),
    }
    result.repair_attempts.append(attempt)
    try:
        repair_apply_result = await patch.apply_plan(
            td_client,
            repair_plan,
            sentinel=sentinel,
            auto_validate=True,
            macro_engine=macro_engine,
            param_preflight=param_preflight,
            param_semantics_policy=options.param_semantics_policy,
        )
    except patch.NestedBlockError as exc:
        attempt["status"] = "failed"
        attempt["error"] = str(exc)
        return None
    # A repair apply that got past NestedBlockError opened (and sealed) its own
    # TD undo block — even when it then fails per-op. Count it so rollback
    # reverts the repair block AND the original, not just the most recent one.
    if repair_apply_result.undo_block_opened:
        result.undo_blocks_opened += 1
    attempt["apply_result"] = repair_apply_result.model_dump(mode="json")
    if repair_apply_result.status == "broken":
        attempt["status"] = "failed"
        attempt["error"] = repair_apply_result.failed_reason or "repair apply failed"
        return None
    repaired_report = await _build_selected_validation_report(
        td_client,
        plan,
        repair_apply_result,
        options=options,
        concept_profile=concept_profile,
        concept_profiles=concept_profiles,
        validation_contract=validation_contract,
    )
    attempt["status"] = "applied" if repaired_report.ok else "validation_failed"
    attempt["validation_ok"] = repaired_report.ok
    attempt["validation_issue_codes"] = [issue.code for issue in repaired_report.issues]
    return repaired_report


def _transaction_concept_profiles(
    *,
    concept_profile: str | None,
    concept_profiles: Iterable[str | None] | None,
) -> list[str]:
    profiles = [str(profile) for profile in (concept_profiles or []) if profile]
    if concept_profile:
        profiles.append(str(concept_profile))
    return list(dict.fromkeys(profiles))


async def _validate_runtime_profile_probes(td_client, plan: PatchPlan, metrics: dict[str, Any]) -> None:
    for result in metrics.get("profile_probe_results", []):
        if not isinstance(result, dict):
            continue
        if result.get("status") != "runtime_contract_present":
            continue
        if result.get("probe_id") == "audio_signal_activity":
            await _validate_audio_signal_activity(td_client, plan, result)
        elif result.get("probe_id") == "callback_guard_present":
            await _validate_callback_guard_readback(td_client, plan, result)
        elif result.get("probe_id") == "compile_state":
            await _validate_compile_state_readback(td_client, plan, result)
        elif result.get("probe_id") == "panel_state_readback":
            await _validate_panel_state_readback(td_client, plan, result)
        elif result.get("probe_id") == "attribute_sample_available":
            await _validate_pop_attribute_metadata_readback(td_client, plan, result)
        elif result.get("probe_id") == "finite_pop_bounds":
            await _validate_pop_bounds_readback(td_client, plan, result)
        elif result.get("probe_id") == "camera_frustum_coverage":
            await _validate_render_camera_frustum_readback(td_client, plan, result)
        elif result.get("probe_id") in {"nonblack_output", "render_top_output"}:
            await _validate_optional_top_sample_readback(td_client, plan, result)
        elif result.get("probe_id") == "feedback_output_readback":
            await _validate_feedback_output_readback(td_client, plan, result)
        elif result.get("probe_id") == "motion_delta":
            await _validate_motion_delta_readback(td_client, plan, result)
        elif result.get("probe_id") == "visual_output_sample":
            await _validate_visual_output_sample_readback(td_client, plan, result)


async def _validate_audio_signal_activity(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    readback_path = _runtime_probe_chop_path(plan)
    result["runtime_required"] = True
    if not readback_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created Null CHOP output path was available for runtime readback.",
        )
        return

    result["readback_path"] = readback_path
    try:
        payload = await td_client.request("chop/data", {"path": readback_path})
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"CHOP readback failed: {exc}")
        return

    if not isinstance(payload, dict) or payload.get("error"):
        message = str(payload.get("error") if isinstance(payload, dict) else "invalid CHOP readback")
        _mark_runtime_probe_unavailable(result, message)
        return

    delta, sample_count = _chop_payload_delta(payload)
    result["runtime_metric_values"] = {
        "audio_analysis_channel_delta": delta,
        "audio_analysis_channel_samples": sample_count,
    }
    result["runtime_evidence"] = {
        "endpoint": "chop/data",
        "path": readback_path,
        "channel_count": len(payload.get("channels", {}) or {}),
    }
    if sample_count > 1 and delta > 1e-6:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_no_activity"
    result["issue_message"] = (
        "audio_signal_activity: Audio-reactive runtime validation sampled "
        f"{readback_path} but observed no channel movement."
    )


async def _validate_panel_state_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    readback_path = _runtime_probe_chop_path(plan)
    result["runtime_required"] = True
    if not readback_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created Null CHOP output path was available for panel state readback.",
        )
        return

    result["readback_path"] = readback_path
    try:
        payload = await td_client.request("chop/data", {"path": readback_path})
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"Panel CHOP readback failed: {exc}")
        return

    if not isinstance(payload, dict) or payload.get("error"):
        message = str(payload.get("error") if isinstance(payload, dict) else "invalid panel CHOP readback")
        _mark_runtime_probe_unavailable(result, message)
        return

    channel_count, sample_count = _chop_payload_presence(payload)
    result["runtime_metric_values"] = {
        "panel_state_channel_count": channel_count,
        "panel_state_sample_count": sample_count,
    }
    result["runtime_evidence"] = {
        "endpoint": "chop/data",
        "path": readback_path,
        "channel_count": channel_count,
    }
    if channel_count > 0 and sample_count > 0:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_no_panel_state"
    result["issue_message"] = (
        "panel_state_readback: Panel UI runtime validation sampled "
        f"{readback_path} but observed no panel state channels."
    )


async def _validate_feedback_output_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    readback_path = _runtime_probe_top_path(plan)
    result["runtime_required"] = True
    if not readback_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created Null TOP output path was available for feedback output readback.",
        )
        return

    result["readback_path"] = readback_path
    try:
        payload = await td_client.request("analyze_frame", {"path": readback_path, "modes": ["luminance"]})
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"TOP luminance readback failed: {exc}")
        return

    if not isinstance(payload, dict) or payload.get("error"):
        message = str(payload.get("error") if isinstance(payload, dict) else "invalid TOP luminance readback")
        _mark_runtime_probe_unavailable(result, message)
        return

    mean, max_value = _top_luminance_metrics(payload)
    result["runtime_metric_values"] = {
        "feedback_output_luminance_mean": mean,
        "feedback_output_luminance_max": max_value,
    }
    result["runtime_evidence"] = {
        "endpoint": "analyze_frame",
        "path": readback_path,
        "resolution": payload.get("resolution"),
        "channels": payload.get("channels"),
    }
    if isinstance(payload.get("quality"), dict):
        result["visual_quality"] = payload["quality"]
    if max_value > 1e-6 and mean > 1e-6:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_black_feedback_output"
    result["issue_message"] = (
        "feedback_output_readback: Feedback runtime validation sampled "
        f"{readback_path} but observed black or empty luminance."
    )


# Two analyze_frame samples this many ms apart; frames must differ above the
# epsilon or the output is considered frozen. Module-level so tests can
# monkeypatch the interval to 0.
_MOTION_PROBE_INTERVAL_MS = 120.0
_MOTION_DELTA_EPSILON = 1e-6


async def _validate_motion_delta_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    """Runtime motion probe — proves the visual output is animating.

    Samples luminance statistics from the stable TOP output twice, N ms apart.
    A frozen animation passes every single-frame visual check; this closes that
    gap for feedback / audio-reactive live validation.
    """
    readback_path = _runtime_probe_top_path(plan)
    result["runtime_required"] = True
    if not readback_path:
        # Audio-reactive plans may be CHOP-only. No TOP output means motion
        # sampling is not applicable — skip with a reason (deferred, not an
        # error), matching the visual_output_sample skip convention.
        result["status"] = "runtime_deferred"
        result["deferred_reason"] = (
            "No created TOP output was available for motion-delta sampling (CHOP-only plan)."
        )
        return

    result["readback_path"] = readback_path
    request = {"path": readback_path, "modes": ["luminance"]}
    try:
        first = await td_client.request("analyze_frame", request)
        if _MOTION_PROBE_INTERVAL_MS > 0:
            await asyncio.sleep(_MOTION_PROBE_INTERVAL_MS / 1000.0)
        second = await td_client.request("analyze_frame", request)
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"Motion-delta readback failed: {exc}")
        return

    if first == {} or second == {}:
        # Component lacks the analyze_frame endpoint — degrade gracefully.
        result["status"] = "runtime_deferred"
        result["deferred_reason"] = "analyze_frame returned no visual metrics for motion-delta sampling."
        return

    for payload in (first, second):
        if not isinstance(payload, dict) or payload.get("error"):
            message = str(
                payload.get("error") if isinstance(payload, dict) else "invalid motion-delta readback"
            )
            _mark_runtime_probe_unavailable(result, message)
            return

    first_mean, first_max, first_std = _top_luminance_stats(first)
    second_mean, second_max, second_std = _top_luminance_stats(second)
    delta = max(
        abs(second_mean - first_mean),
        abs(second_max - first_max),
        abs(second_std - first_std),
    )
    result["runtime_metric_values"] = {
        "motion_luminance_delta": delta,
        "motion_sample_interval_ms": _MOTION_PROBE_INTERVAL_MS,
    }
    result["runtime_evidence"] = {
        "endpoint": "analyze_frame",
        "path": readback_path,
        "samples": 2,
        "sample_interval_ms": _MOTION_PROBE_INTERVAL_MS,
        "first_luminance": {"mean": first_mean, "max": first_max, "std": first_std},
        "second_luminance": {"mean": second_mean, "max": second_max, "std": second_std},
    }
    if delta > _MOTION_DELTA_EPSILON:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_frozen_output"
    result["issue_message"] = (
        f"motion_delta: Motion validation sampled {readback_path} twice "
        f"{_MOTION_PROBE_INTERVAL_MS:g} ms apart but observed identical frames — "
        "the output appears frozen, not animating."
    )


async def _validate_optional_top_sample_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    readback_path = _runtime_probe_top_path(plan)
    probe_id = str(result.get("probe_id") or "top_sample_optional")
    result["runtime_required"] = True
    if not readback_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created Null TOP output path was available for optional TOP sample readback.",
        )
        return

    result["readback_path"] = readback_path
    request = {"path": readback_path, "modes": ["luminance", "alpha_coverage"]}
    try:
        payload = await td_client.request("analyze_frame", request)
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"Optional TOP analysis readback failed: {exc}")
        return

    if not isinstance(payload, dict) or payload.get("error"):
        message = str(payload.get("error") if isinstance(payload, dict) else "invalid optional TOP analysis")
        _mark_runtime_probe_unavailable(result, message)
        return

    mean, max_value, std = _top_luminance_stats(payload)
    coverage = _top_alpha_coverage(payload, fallback=1.0 if max_value > 1e-6 else 0.0)
    result["runtime_evidence"] = {
        "endpoint": "analyze_frame",
        "path": readback_path,
        "resolution": payload.get("resolution"),
        "channels": payload.get("channels"),
        "modes": ["luminance", "alpha_coverage"],
    }
    if isinstance(payload.get("quality"), dict):
        result["visual_quality"] = payload["quality"]
    if probe_id == "render_top_output":
        _record_render_top_output_result(result, mean=mean, max_value=max_value, coverage=coverage)
        return

    _record_nonblack_top_output_result(result, mean=mean, max_value=max_value, std=std)


async def _validate_visual_output_sample_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    readback_path = _runtime_probe_top_path(plan)
    result["runtime_required"] = True
    if not readback_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created Null TOP output path was available for cheap visual output sampling.",
        )
        return

    result["readback_path"] = readback_path
    request = {"path": readback_path, "modes": ["luminance", "alpha_coverage"]}
    try:
        payload = await td_client.request("analyze_frame", request)
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"Cheap TOP visual analysis failed: {exc}")
        return

    if payload == {}:
        result["status"] = "runtime_deferred"
        result["deferred_reason"] = "analyze_frame returned no visual metrics for cheap output sampling."
        return

    if not isinstance(payload, dict) or payload.get("error"):
        message = str(payload.get("error") if isinstance(payload, dict) else "invalid cheap TOP analysis")
        _mark_runtime_probe_unavailable(result, message)
        return

    mean, max_value, std = _top_luminance_stats(payload)
    coverage = _top_alpha_coverage(payload, fallback=1.0 if max_value > 1e-6 else 0.0)
    result["runtime_metric_values"] = {
        "output_luminance": mean,
        "output_alpha_coverage": coverage,
        "output_entropy": std,
    }
    result["runtime_evidence"] = {
        "endpoint": "analyze_frame",
        "path": readback_path,
        "resolution": payload.get("resolution"),
        "channels": payload.get("channels"),
        "modes": ["luminance", "alpha_coverage"],
    }
    if isinstance(payload.get("quality"), dict):
        result["visual_quality"] = payload["quality"]
    if mean > 1e-6 and max_value > 1e-6 and coverage > 1e-6:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_empty_visual_output"
    result["issue_message"] = (
        "visual_output_sample: Cheap visual validation sampled "
        f"{readback_path} but observed black, transparent, or empty output."
    )


async def _validate_render_camera_frustum_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    render_path = _runtime_probe_render_path(plan)
    camera_paths = set(_created_paths_for_op_types(plan, ("cameraCOMP",)))
    geometry_paths = set(_created_paths_for_op_types(plan, ("geometryCOMP",)))
    result["runtime_required"] = True
    if not render_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created Render TOP path was available for camera/frustum readback.",
        )
        return

    result["readback_path"] = render_path
    try:
        payload = await td_client.request(
            "node/params",
            {"path": render_path, "names": ["camera", "geometry"]},
        )
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"Render camera/frustum readback failed: {exc}")
        return

    if not isinstance(payload, dict) or payload.get("error"):
        message = str(payload.get("error") if isinstance(payload, dict) else "invalid render param readback")
        _mark_runtime_probe_unavailable(result, message)
        return

    camera_value = _param_readback_value(payload, "camera")
    geometry_value = _param_readback_value(payload, "geometry")
    camera_bound = _readback_value_matches_created_path(camera_value, camera_paths)
    geometry_bound = _readback_value_matches_created_path(geometry_value, geometry_paths)
    result["runtime_metric_values"] = {
        "render_camera_ref_bound": camera_bound,
        "render_geometry_ref_bound": geometry_bound,
    }
    result["runtime_evidence"] = {
        "endpoint": "node/params",
        "path": render_path,
        "camera": camera_value,
        "geometry": geometry_value,
    }
    if camera_bound and geometry_bound:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_render_refs_unbound"
    result["issue_message"] = (
        "camera_frustum_coverage: Render runtime validation sampled "
        f"{render_path} but did not find bound planned camera and geometry references."
    )


def _record_render_top_output_result(
    result: dict[str, Any],
    *,
    mean: float,
    max_value: float,
    coverage: float,
) -> None:
    result["runtime_metric_values"] = {
        "render_luminance": mean,
        "render_coverage": coverage,
    }
    if mean > 1e-6 and max_value > 1e-6 and coverage > 1e-6:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_invisible_render_output"
    result["issue_message"] = (
        "render_top_output: Optional render runtime validation sampled "
        f"{result.get('readback_path')} but observed invisible or empty output."
    )


def _collect_visual_quality_metrics(metrics: dict[str, Any]) -> None:
    visual_quality: dict[str, Any] = {}
    for result in metrics.get("profile_probe_results", []):
        if not isinstance(result, dict):
            continue
        quality = result.get("visual_quality")
        if not isinstance(quality, dict):
            continue
        path = result.get("readback_path")
        if not path:
            evidence = result.get("runtime_evidence")
            if isinstance(evidence, dict):
                path = evidence.get("path")
        if path:
            visual_quality[str(path)] = quality
    if visual_quality:
        metrics["visual_quality"] = visual_quality


def _record_nonblack_top_output_result(
    result: dict[str, Any],
    *,
    mean: float,
    max_value: float,
    std: float,
) -> None:
    result["runtime_metric_values"] = {
        "output_luminance": mean,
        "output_entropy": std,
    }
    if mean > 1e-6 and max_value > 1e-6 and std > 1e-6:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_trivial_top_output"
    result["issue_message"] = (
        "nonblack_output: Optional TOP runtime validation sampled "
        f"{result.get('readback_path')} but observed black or trivially constant output."
    )


async def _validate_compile_state_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    readback_path = _runtime_probe_shader_path(plan, result)
    metric_name = _first_metric_name(result, fallback="shader_compile_clean")
    result["runtime_required"] = True
    if not readback_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created GLSL operator path was available for compile-state readback.",
        )
        return

    result["readback_path"] = readback_path
    try:
        payload = await td_client.request("node/errors", {"path": readback_path})
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"GLSL compile-state readback failed: {exc}")
        return

    if not isinstance(payload, dict) or payload.get("error"):
        message = str(payload.get("error") if isinstance(payload, dict) else "invalid node/errors readback")
        _mark_runtime_probe_unavailable(result, message)
        return

    issues = payload.get("issues")
    issue_count = len(issues) if isinstance(issues, list) else 0
    clean = issue_count == 0
    result["runtime_metric_values"] = {metric_name: clean}
    result["runtime_evidence"] = {
        "endpoint": "node/errors",
        "path": readback_path,
        "issue_count": issue_count,
    }
    if clean:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_compile_state_error"
    result["issue_message"] = (
        "compile_state: GLSL runtime validation sampled "
        f"{readback_path} and found {issue_count} compile/error issue(s): {_first_runtime_issue_message(issues)}"
    )


async def _validate_callback_guard_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    readback_path = _runtime_probe_dat_execute_path(plan)
    metric_name = _first_metric_name(result, fallback="modern_table_change_callback_present")
    result["runtime_required"] = True
    if not readback_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created DAT Execute DAT path was available for callback guard readback.",
        )
        return

    result["readback_path"] = readback_path
    try:
        payload = await td_client.request("node/content", {"path": readback_path})
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"DAT Execute callback content readback failed: {exc}")
        return

    callback_text = _content_text(payload)
    ok = _has_callback_guard_contract(callback_text)
    result["runtime_metric_values"] = {metric_name: ok}
    result["runtime_evidence"] = {
        "endpoint": "node/content",
        "path": readback_path,
    }
    if ok:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_callback_guard_missing"
    result["issue_message"] = (
        "callback_guard_present: DAT Execute runtime validation sampled "
        f"{readback_path} but did not find a guarded onTableChange callback."
    )


async def _validate_pop_bounds_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    readback_path = _runtime_probe_pop_path(plan)
    result["runtime_required"] = True
    if not readback_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created Null POP output path was available for POP bounds readback.",
        )
        return

    result["readback_path"] = readback_path
    try:
        payload = await td_client.request("pop/bounds", {"path": readback_path})
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"POP bounds readback failed: {exc}")
        return

    if not isinstance(payload, dict) or payload.get("error"):
        message = str(payload.get("error") if isinstance(payload, dict) else "invalid POP bounds readback")
        _mark_runtime_probe_unavailable(result, message)
        return

    finite = _pop_bounds_are_finite(payload)
    result["runtime_metric_values"] = {"pop_bounds_finite": finite}
    result["runtime_evidence"] = {
        "endpoint": "pop/bounds",
        "path": readback_path,
    }
    if finite:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_nonfinite_pop_bounds"
    result["issue_message"] = (
        "finite_pop_bounds: POP runtime validation sampled "
        f"{readback_path} but observed missing or non-finite bounds."
    )


async def _validate_pop_attribute_metadata_readback(
    td_client,
    plan: PatchPlan,
    result: dict[str, Any],
) -> None:
    readback_path = _runtime_probe_pop_path(plan)
    metric_name = _first_metric_name(result, fallback="pop_attribute_count_present")
    result["runtime_required"] = True
    if not readback_path:
        _mark_runtime_probe_unavailable(
            result,
            "No created Null POP output path was available for POP attribute metadata readback.",
        )
        return

    result["readback_path"] = readback_path
    request = {
        "path": readback_path,
        "include_bounds": False,
        "include_attributes": True,
        "point_attributes": ["P"],
        "prim_attributes": [],
        "vert_attributes": [],
        "start": 0,
        "count": 8,
        "delayed": True,
    }
    try:
        payload = await td_client.request("pop/inspect", request)
    except Exception as exc:  # noqa: BLE001
        _mark_runtime_probe_unavailable(result, f"POP attribute metadata readback failed: {exc}")
        return

    if not isinstance(payload, dict) or payload.get("error"):
        message = str(payload.get("error") if isinstance(payload, dict) else "invalid POP inspect readback")
        _mark_runtime_probe_unavailable(result, message)
        return

    attribute_count = _pop_attribute_metadata_count(payload)
    present = attribute_count > 0
    result["runtime_metric_values"] = {metric_name: present}
    result["runtime_evidence"] = {
        "endpoint": "pop/inspect",
        "path": readback_path,
        "attribute_count": attribute_count,
    }
    if present:
        result["status"] = "runtime_pass"
        result.pop("pending_metric_names", None)
        return

    result["status"] = "runtime_failed"
    result["issue_code"] = "profile_probe_runtime_missing_pop_attributes"
    result["issue_message"] = (
        "attribute_sample_available: POP runtime validation sampled "
        f"{readback_path} but found no point, primitive, or vertex attribute metadata."
    )


def _runtime_probe_chop_path(plan: PatchPlan) -> str | None:
    created: list[tuple[str, str]] = []
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        op_type = str(operation.args.get("op_type") or "")
        if op_type != "nullCHOP":
            continue
        name = str(operation.args.get("name") or "")
        parent = operation.target or plan.target_root
        path = f"{parent.rstrip('/')}/{name}".replace("//", "/")
        created.append((name, path))
    for name, path in created:
        if name == "out_chop":
            return path
    return created[0][1] if created else None


def _runtime_probe_top_path(plan: PatchPlan) -> str | None:
    created: list[tuple[str, str]] = []
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        op_type = str(operation.args.get("op_type") or "")
        if op_type != "nullTOP":
            continue
        name = str(operation.args.get("name") or "")
        parent = operation.target or plan.target_root
        path = f"{parent.rstrip('/')}/{name}".replace("//", "/")
        created.append((name, path))
    for name, path in created:
        if name == "out1":
            return path
    return created[0][1] if created else None


def _runtime_probe_shader_path(plan: PatchPlan, result: dict[str, Any]) -> str | None:
    profile = str(result.get("profile") or "")
    if profile == "glsl_material":
        op_types = ("glslMAT",)
    elif profile == "glsl_pop":
        op_types = ("glslPOP", "glsladvancedPOP")
    else:
        op_types = ("glslTOP",)
    paths = _created_paths_for_op_types(plan, op_types)
    return paths[0] if paths else None


def _runtime_probe_render_path(plan: PatchPlan) -> str | None:
    paths = _created_paths_for_op_types(plan, ("renderTOP",))
    return paths[0] if paths else None


def _runtime_probe_dat_execute_path(plan: PatchPlan) -> str | None:
    paths = _created_paths_for_op_types(plan, ("datexecuteDAT",))
    return paths[0] if paths else None


def _runtime_probe_pop_path(plan: PatchPlan) -> str | None:
    created: list[tuple[str, str]] = []
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        op_type = str(operation.args.get("op_type") or "")
        if op_type != "nullPOP":
            continue
        name = str(operation.args.get("name") or "")
        parent = operation.target or plan.target_root
        path = f"{parent.rstrip('/')}/{name}".replace("//", "/")
        created.append((name, path))
    for name, path in created:
        if name == "out_pop":
            return path
    return created[0][1] if created else None


def _created_paths_for_op_types(plan: PatchPlan, op_types: tuple[str, ...]) -> list[str]:
    wanted = set(op_types)
    paths: list[str] = []
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        op_type = str(operation.args.get("op_type") or "")
        if op_type not in wanted:
            continue
        name = str(operation.args.get("name") or "")
        parent = operation.target or plan.target_root
        paths.append(f"{parent.rstrip('/')}/{name}".replace("//", "/"))
    return paths


def _predicted_created_node_paths(plan: PatchPlan) -> list[str]:
    paths: list[str] = []
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        name = str(operation.args.get("name") or "").strip()
        if not name:
            continue
        parent = operation.target or plan.target_root
        paths.append(f"{parent.rstrip('/')}/{name}".replace("//", "/"))
    return paths


def _chop_payload_delta(payload: dict[str, Any]) -> tuple[float, int]:
    values: list[float] = []
    channels = payload.get("channels")
    if isinstance(channels, dict):
        for channel in channels.values():
            if not isinstance(channel, dict):
                continue
            raw_values = channel.get("values")
            if not isinstance(raw_values, list):
                continue
            for value in raw_values:
                if isinstance(value, bool):
                    continue
                if isinstance(value, (int, float)):
                    values.append(float(value))
                    continue
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    continue
    if not values:
        return 0.0, 0
    return max(values) - min(values), len(values)


def _chop_payload_presence(payload: dict[str, Any]) -> tuple[int, int]:
    channels = payload.get("channels")
    if not isinstance(channels, dict):
        return 0, 0
    sample_count = 0
    channel_count = 0
    for channel in channels.values():
        if not isinstance(channel, dict):
            continue
        raw_values = channel.get("values")
        if not isinstance(raw_values, list) or not raw_values:
            continue
        channel_count += 1
        sample_count += len(raw_values)
    return channel_count, sample_count


def _param_readback_value(payload: dict[str, Any], name: str) -> Any:
    params = payload.get("parameters")
    if isinstance(params, dict):
        entry = params.get(name)
        if isinstance(entry, dict):
            return entry.get("value")
        if entry is not None:
            return entry
    return payload.get(name)


def _readback_value_matches_created_path(value: Any, created_paths: set[str]) -> bool:
    if not created_paths:
        return False
    tokens = _path_tokens(value)
    return any(token in created_paths for token in tokens)


def _path_tokens(value: Any) -> set[str]:
    if isinstance(value, str):
        return {token for token in value.split() if token}
    if isinstance(value, (list, tuple, set)):
        tokens: set[str] = set()
        for item in value:
            tokens.update(_path_tokens(item))
        return tokens
    return set()


def _top_luminance_metrics(payload: dict[str, Any]) -> tuple[float, float]:
    mean, max_value, _std = _top_luminance_stats(payload)
    return mean, max_value


def _top_luminance_stats(payload: dict[str, Any]) -> tuple[float, float, float]:
    modes = payload.get("modes")
    luminance = modes.get("luminance") if isinstance(modes, dict) else payload.get("luminance")
    if not isinstance(luminance, dict) or luminance.get("error"):
        return 0.0, 0.0, 0.0
    return (
        _coerce_float(luminance.get("mean")),
        _coerce_float(luminance.get("max")),
        _coerce_float(luminance.get("std")),
    )


def _top_alpha_coverage(payload: dict[str, Any], *, fallback: float) -> float:
    modes = payload.get("modes")
    alpha = modes.get("alpha_coverage") if isinstance(modes, dict) else payload.get("alpha_coverage")
    if not isinstance(alpha, dict) or alpha.get("error"):
        return fallback
    return _coerce_float(alpha.get("opaque_fraction"))


def _pop_bounds_are_finite(payload: dict[str, Any]) -> bool:
    bounds = payload.get("bounds")
    if not isinstance(bounds, dict):
        return False
    values: list[float] = []
    for key in ("min", "max"):
        raw = bounds.get(key)
        if not isinstance(raw, list | tuple) or not raw:
            return False
        for item in raw:
            value = _coerce_float(item)
            if not isinstance(item, (int, float)) or isinstance(item, bool):
                return False
            values.append(value)
    return bool(values) and all(math.isfinite(value) for value in values)


def _pop_attribute_metadata_count(payload: dict[str, Any]) -> int:
    attributes = payload.get("attributes")
    if not isinstance(attributes, dict):
        return 0
    count = 0
    for key in ("point", "prim", "vert"):
        descriptors = attributes.get(key)
        if isinstance(descriptors, list):
            count += len([item for item in descriptors if item])
    return count


def _first_metric_name(result: dict[str, Any], *, fallback: str) -> str:
    metric_names = result.get("metric_names")
    if isinstance(metric_names, list) and metric_names:
        return str(metric_names[0])
    return fallback


def _first_runtime_issue_message(issues: Any) -> str:
    if not isinstance(issues, list) or not issues:
        return "unknown issue"
    first = issues[0]
    if isinstance(first, dict):
        return str(first.get("message") or first.get("error") or first)
    return str(first)


def _rows_to_text(rows: list) -> str:
    return "\n".join(
        "\t".join(str(cell) for cell in row) if isinstance(row, list | tuple) else str(row) for row in rows
    )


def _content_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("text", "content", "data"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        rows = payload.get("rows")
        if isinstance(rows, list):
            return _rows_to_text(rows)
    # A table-shaped `set_dat_content` op stores its value as a bare list-of-rows
    # (applier records op.args["table"] directly). Render it the same tab/newline
    # form as the readback so rollback verification compares string-to-string
    # instead of str == list (which is always False and silently fails open).
    if isinstance(payload, list):
        return _rows_to_text(payload)
    return ""


def _has_callback_guard_contract(text: str) -> bool:
    lowered = text.lower()
    return (
        "def ontablechange" in lowered
        and "tdpilot_callback_guard" in lowered
        and "try:" in text
        and "finally:" in text
    )


def _coerce_float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _mark_runtime_probe_unavailable(result: dict[str, Any], message: str) -> None:
    result["status"] = "runtime_unavailable"
    result["issue_code"] = "profile_probe_runtime_unavailable"
    result["issue_message"] = f"{result.get('probe_id', 'runtime_probe')}: {message}"


async def _verify_rollback_readback(
    td_client,
    *,
    created_node_paths: tuple[str, ...],
    changed_params: tuple[dict[str, Any], ...],
    connections_made: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    verification: dict[str, Any] = {
        "ok": True,
        "created_paths": {"checked": [], "remaining": [], "unverified": []},
        "changed_params": {"checked": [], "still_changed": [], "unverified": []},
        "connections": {"checked": [], "remaining": [], "unverified": []},
    }
    await _verify_created_paths_removed(td_client, verification, created_node_paths)
    await _verify_changed_params_reverted(
        td_client,
        verification,
        changed_params,
        created_node_paths=created_node_paths,
    )
    await _verify_connections_removed(td_client, verification, connections_made)
    verification["ok"] = not (
        verification["created_paths"]["remaining"]
        or verification["created_paths"]["unverified"]
        or verification["changed_params"]["still_changed"]
        or verification["changed_params"]["unverified"]
        or verification["connections"]["remaining"]
        or verification["connections"]["unverified"]
    )
    return verification


async def _verify_created_paths_removed(
    td_client,
    verification: dict[str, Any],
    created_node_paths: tuple[str, ...],
) -> None:
    for path in dict.fromkeys(created_node_paths):
        verification["created_paths"]["checked"].append(path)
        try:
            payload = await td_client.request("node/detail", {"path": path})
        except Exception as exc:  # noqa: BLE001
            verification["created_paths"]["unverified"].append({"path": path, "error": str(exc)})
            continue
        if _node_detail_exists(payload):
            verification["created_paths"]["remaining"].append(path)


async def _verify_changed_params_reverted(
    td_client,
    verification: dict[str, Any],
    changed_params: tuple[dict[str, Any], ...],
    *,
    created_node_paths: tuple[str, ...] = (),
) -> None:
    created_path_set = set(created_node_paths)
    verification["changed_params"].setdefault("skipped_created_paths", [])
    for entry in changed_params:
        path = str(entry.get("path") or "")
        name = str(entry.get("name") or "")
        if not path or not name:
            continue
        checked = {"path": path, "name": name}
        verification["changed_params"]["checked"].append(checked)
        if path in created_path_set:
            verification["changed_params"]["skipped_created_paths"].append(checked)
            continue
        try:
            if name == "content":
                payload = await td_client.request("node/content", {"path": path})
                value = _content_text(payload)
                # Normalize the expected content (str OR table list-of-rows) to
                # the same string form as the readback so a still-live table-DAT
                # mutation is detected instead of silently passing (str != list).
                expected = _content_text(entry.get("new"))
            else:
                payload = await td_client.request("node/params", {"path": path, "names": [name]})
                value = _rollback_param_readback_value(
                    payload if isinstance(payload, dict) else {}, name, entry.get("new")
                )
                expected = entry.get("new")
        except Exception as exc:  # noqa: BLE001
            verification["changed_params"]["unverified"].append({**checked, "error": str(exc)})
            continue
        if _rollback_values_equal(value, expected):
            value_key = "expr" if isinstance(expected, dict) and "expr" in expected else "value"
            verification["changed_params"]["still_changed"].append({**checked, value_key: value})


async def _verify_connections_removed(
    td_client,
    verification: dict[str, Any],
    connections_made: tuple[tuple[str, str], ...],
) -> None:
    for source, target in dict.fromkeys(connections_made):
        checked = {"from": source, "to": target}
        verification["connections"]["checked"].append(checked)
        try:
            source_payload = await td_client.request("node/connections", {"path": source})
            target_payload = await td_client.request("node/connections", {"path": target})
        except Exception as exc:  # noqa: BLE001
            verification["connections"]["unverified"].append({**checked, "error": str(exc)})
            continue
        if _connection_still_present(source_payload, source, target) or _connection_still_present(
            target_payload, source, target
        ):
            verification["connections"]["remaining"].append(checked)


def _node_detail_exists(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get("error"):
        return False
    return any(payload.get(key) for key in ("path", "name", "type", "op_type", "node_type", "family"))


def _rollback_values_equal(left: Any, right: Any) -> bool:
    if isinstance(right, dict) and "expr" in right:
        return left == right.get("expr")
    return left == right


def _rollback_param_readback_value(payload: dict[str, Any], name: str, expected_new: Any) -> Any:
    if isinstance(expected_new, dict) and "expr" in expected_new:
        params = payload.get("parameters")
        if isinstance(params, dict):
            entry = params.get(name)
            if isinstance(entry, dict):
                return entry.get("expr")
    return _param_readback_value(payload, name)


def _connection_still_present(payload: Any, source: str, target: str) -> bool:
    if not isinstance(payload, dict) or payload.get("error"):
        return False
    outputs = payload.get("outputs")
    if isinstance(outputs, list):
        for item in outputs:
            if isinstance(item, dict) and item.get("to_path") == target:
                return True
    inputs = payload.get("inputs")
    if isinstance(inputs, list):
        for item in inputs:
            if isinstance(item, dict) and item.get("from_path") == source:
                return True
    return False


async def _rollback(
    td_client,
    result: TransactionResult,
    *,
    restore_snapshot: RestoreCallback | None,
    undo_block_count: int = 1,
    created_node_paths: tuple[str, ...] = (),
    changed_params: tuple[dict[str, Any], ...] = (),
    connections_made: tuple[tuple[str, str], ...] = (),
) -> None:
    """Revert a transaction's mutations.

    A transaction may seal more than one TD undo block (the original apply plus
    one per applied auto-repair). TD's ``undo`` reverts only the most recent
    block, so we must issue exactly ``undo_block_count`` undo actions; issuing
    one would leave the original mutation live while still reporting success.

    When undo cannot revert every block we fall back to snapshot restore — but
    that restore only re-applies parameter values, so it cannot delete nodes the
    transaction created. We therefore refuse to claim a clean rollback whenever
    the transaction created nodes, escalating to manual recovery instead.
    """
    if undo_block_count <= 0:
        # No undo block was sealed (e.g. a preflight-blocked apply that returned
        # before any mutation). Nothing was changed, so rollback is a no-op
        # success — and crucially we must NOT issue a stray undo that would
        # revert some unrelated prior action.
        result.rollback_verification = {
            "ok": True,
            "method": "noop_no_undo_block",
            "created_paths": {"checked": [], "remaining": [], "unverified": []},
            "changed_params": {"checked": [], "still_changed": [], "unverified": []},
            "connections": {"checked": [], "remaining": [], "unverified": []},
        }
        result.rollback_performed = True
        return

    undone = 0
    try:
        for _ in range(undo_block_count):
            await td_client.request("project/lifecycle", {"action": "undo"})
            undone += 1
    except Exception as exc:  # noqa: BLE001
        result.rollback_error = str(exc)

    if undone == undo_block_count and not result.rollback_error:
        result.rollback_verification = await _verify_rollback_readback(
            td_client,
            created_node_paths=created_node_paths,
            changed_params=changed_params,
            connections_made=connections_made,
        )
        if result.rollback_verification.get("ok"):
            result.rollback_performed = True
            return
        result.rollback_error = _rollback_verification_error(result.rollback_verification)
        result.needs_manual_recovery = True
        return

    if result.before_snapshot_id and restore_snapshot is not None:
        try:
            restored = await restore_snapshot(result.before_snapshot_id)
            failures = []
            if isinstance(restored, dict):
                failures = restored.get("failures", [])
            # Param-only restore cannot remove created nodes — only claim a
            # clean rollback when the transaction created none.
            if not failures and not created_node_paths:
                result.rollback_verification = await _verify_rollback_readback(
                    td_client,
                    created_node_paths=created_node_paths,
                    changed_params=changed_params,
                    connections_made=connections_made,
                )
                if result.rollback_verification.get("ok"):
                    result.rollback_performed = True
                    result.rollback_error = None
                    return
                result.rollback_error = _rollback_verification_error(result.rollback_verification)
                result.needs_manual_recovery = True
                return
        except Exception as exc:  # noqa: BLE001
            result.rollback_error = str(exc)

    result.needs_manual_recovery = True


def _rollback_verification_error(verification: dict[str, Any]) -> str:
    reasons: list[str] = []
    created = verification.get("created_paths") if isinstance(verification, dict) else None
    if isinstance(created, dict):
        if created.get("remaining"):
            reasons.append("created paths still exist")
        if created.get("unverified"):
            reasons.append("created paths could not be verified")
    params = verification.get("changed_params") if isinstance(verification, dict) else None
    if isinstance(params, dict):
        if params.get("still_changed"):
            reasons.append("changed params still hold transaction values")
        if params.get("unverified"):
            reasons.append("changed params could not be verified")
    connections = verification.get("connections") if isinstance(verification, dict) else None
    if isinstance(connections, dict):
        if connections.get("remaining"):
            reasons.append("created connections still exist")
        if connections.get("unverified"):
            reasons.append("created connections could not be verified")
    return "rollback readback verification failed: " + "; ".join(reasons or ["unknown reason"])


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


def _param_semantics_report(
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
        checks=["param_semantics"],
        issues=issues,
        severity_counts=severity_counts,
        cheap_metrics={},
        summary=f"{len(issues)} parameter semantics issue(s)",
    )


def _generated_code_report(
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
        checks=["generated_code_static_checks"],
        issues=issues,
        severity_counts=severity_counts,
        cheap_metrics={},
        summary=f"{len(issues)} generated code issue(s)",
    )


def _merge_generated_code_runtime_report(
    validation_report: ValidationReportV2,
    runtime_report: dict[str, Any],
) -> None:
    if "generated_code_runtime_checks" not in validation_report.checks:
        validation_report.checks.append("generated_code_runtime_checks")

    runtime_issues = [
        issue if isinstance(issue, ValidationIssue) else ValidationIssue.model_validate(issue)
        for issue in runtime_report.get("issues", [])
    ]
    validation_report.issues.extend(runtime_issues)
    validation_report.ok = validation_report.ok and not runtime_issues

    severity_counts: dict[str, int] = {}
    for issue in validation_report.issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
    validation_report.severity_counts = severity_counts
    validation_report.summary = (
        "clean" if validation_report.ok else f"{len(validation_report.issues)} validation issue(s)"
    )
