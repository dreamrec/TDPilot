"""Concept profiles and validation helpers for the TDPilot brain."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from td_mcp.brain.validation_probes import (
    probe_ids_for_profiles,
    probe_summaries_for_profile,
    probe_summaries_for_profiles,
)
from td_mcp.models.brain import ValidationIssue, ValidationReportV2
from td_mcp.models.patch import PatchPlan, PatchResult

PROFILE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "feedback": ("feedback", "trail", "echo", "recursion", "displacement"),
    "audio_reactive": ("audio", "beat", "sound", "music", "spectrum", "reactive"),
    "glsl_material": ("glsl mat", "glsl material", "custom material", "vertex shader", "geometry shader"),
    "glsl_pop": ("glsl pop", "pop shader", "compute pop", "attribute shader"),
    "glsl": ("glsl", "shader", "fragment", "pixel shader"),
    "pop": ("pop", "particle", "particles", "gpu particle", "simulation"),
    "render_pipeline": ("render", "camera", "geometry", "material", "lights"),
    "panel_ui": ("panel", "ui", "button", "slider", "container"),
    "control_rig": ("custom parameter", "control", "macro control", "preset"),
}

STRUCTURAL_CHECKS: tuple[str, ...] = (
    "graph_structure",
    "required_inputs",
    "parameter_readback",
    "td_errors",
    "cook_health",
    "cheap_visual_metrics",
)

_CREATE_TYPE_ALIASES: dict[str, str] = {
    "glsl": "glslTOP",
    "glsltop": "glslTOP",
    "glslmat": "glslMAT",
    "glslpop": "glslPOP",
    "rendersimple": "rendersimpleTOP",
    "rendersimpletop": "rendersimpleTOP",
    "render": "renderTOP",
    "rendertop": "renderTOP",
}

_REFERENCE_PARAM_RULES: dict[str, tuple[dict[str, Any], ...]] = {
    "glslTOP": (
        {
            "any_of": ("pixeldat", "computedat"),
            "expected_family": "DAT",
            "label": "shader DAT",
            "source": "GLSL TOP",
        },
    ),
    "glslMAT": (
        {"param": "vdat", "expected_family": "DAT", "label": "vertex shader DAT", "source": "GLSL MAT"},
        {"param": "pdat", "expected_family": "DAT", "label": "pixel shader DAT", "source": "GLSL MAT"},
    ),
    "glslPOP": (
        {
            "param": "computedat",
            "expected_family": "DAT",
            "label": "compute shader DAT",
            "source": "GLSL POP",
        },
    ),
    "glsladvancedPOP": (
        {
            "param": "computedat",
            "expected_family": "DAT",
            "label": "compute shader DAT",
            "source": "GLSL Advanced POP",
        },
    ),
    "rendersimpleTOP": (
        {"param": "pop", "expected_family": "POP", "label": "POP to render", "source": "Render Simple TOP"},
    ),
    "renderTOP": (
        {"param": "camera", "expected_type": "cameraCOMP", "label": "Camera COMP", "source": "Render TOP"},
        {
            "param": "geometry",
            "expected_type": "geometryCOMP",
            "label": "Geometry COMP",
            "source": "Render TOP",
        },
    ),
    "datexecuteDAT": (
        {"param": "dat", "expected_family": "DAT", "label": "Monitored DAT", "source": "DAT Execute DAT"},
    ),
}

_ALTERNATIVE_PROBE_INPUTS: dict[tuple[str, str], tuple[tuple[str, ...], ...]] = {
    ("concept_compiled", "audio_source_present"): (("audiofileinCHOP", "audiodeviceinCHOP"),),
    ("concept_compiled", "output_node_present"): (("nullTOP", "nullCHOP", "nullDAT", "nullPOP"),),
    ("audio_reactive", "audio_signal_activity"): (("audiofileinCHOP", "audiodeviceinCHOP"),),
    # CHOP-only audio-reactive plans satisfy the static gate via nullCHOP; the
    # runtime motion sampler then defers with a reason when no TOP exists.
    ("audio_reactive", "motion_delta"): (("nullTOP", "nullCHOP"),),
}
_STRUCTURAL_VALIDATION_PROFILES = {"auto", "structural_visual_safe", "structural_visual_expensive"}
_RUNTIME_READBACK_STRATEGIES = {
    "chop_channel_delta_runtime",
    "chop_channel_presence_runtime",
    "node_content_runtime",
    "node_errors_runtime",
    "pop_attribute_metadata_runtime",
    "pop_bounds_runtime",
    "render_camera_frustum_runtime",
    "top_sample_optional",
    "top_luminance_runtime",
    "top_motion_delta_runtime",
    "top_visual_cheap_runtime",
}
_RENDER_SWITCH_INDEX_EXPR = re.compile(
    r"^min\(1,\s*max\(0,\s*int\(op\('(?P<table_path>[^']+)'\)\[1,\s*'selected_index'\]\)\)\)$"
)


def classify_intent_profile(intent: str, preferred_domains: Iterable[str] | None = None) -> str:
    """Return the best-known concept profile for an intent."""
    text = _profile_request_intent_text((intent or "").lower())
    if "glsl" in text and any(
        token in text for token in ("mat", "material", "vertex shader", "geometry shader")
    ):
        return "glsl_material"
    if "glsl" in text and any(token in text for token in ("pop", "attribute", "compute")):
        return "glsl_pop"
    for profile, keywords in PROFILE_KEYWORDS.items():
        if any(_keyword_matches(text, keyword) for keyword in keywords):
            return profile
    domains = {str(item).upper() for item in (preferred_domains or [])}
    if "POP" in domains:
        return "pop"
    if "CHOP" in domains:
        return "audio_reactive"
    if "TOP" in domains:
        return "generic"
    return "generic"


def _profile_request_intent_text(text: str) -> str:
    clauses = re.split(r"(?i)(?:\bwhile\b|\bwhere\b|\bwhen\b|;|,)", text)
    kept: list[str] = []
    for clause in clauses:
        stripped = clause.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        is_card_context = (
            "distractor" in lower
            or "cards" in lower
            or "card" in lower
            or "docs" in lower
            or "also available" in lower
            or "also present" in lower
        )
        if kept and is_card_context:
            continue
        kept.append(stripped)
    return " ".join(kept) or text


def _keyword_matches(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None


def classify_validation_issues(errors: list[dict[str, Any]]) -> list[ValidationIssue]:
    """Normalize TD issue dictionaries into stable severity buckets."""
    issues: list[ValidationIssue] = []
    for item in errors:
        if not isinstance(item, dict):
            issues.append(ValidationIssue(severity="error", code="td_error", message=str(item)))
            continue
        msg = str(item.get("message") or item.get("error") or item.get("text") or item)
        msg_lower = msg.lower()
        if any(token in msg_lower for token in ("crash", "compile", "missing input", "not enough sources")):
            severity = "error"
        elif any(token in msg_lower for token in ("warning", "inactive", "bypass")):
            severity = "warning"
        else:
            severity = "error"
        issues.append(
            ValidationIssue(
                severity=severity,
                code=str(item.get("code") or "td_issue"),
                message=msg,
                path=item.get("path") or item.get("node"),
                source=str(item.get("source") or "touchdesigner"),
            )
        )
    return issues


def checks_for_profile(validation_profile: str, concept_profile: str | None = None) -> list[str]:
    """Return stable check identifiers for a validation profile/concept pair."""
    return checks_for_profiles(validation_profile, [concept_profile])


def checks_for_profiles(validation_profile: str, concept_profiles: Iterable[str | None]) -> list[str]:
    """Return stable check identifiers for one or more concept profiles."""
    checks: list[str] = []
    if validation_profile in _STRUCTURAL_VALIDATION_PROFILES:
        checks.extend(STRUCTURAL_CHECKS)
    else:
        checks.append(validation_profile)
    checks.extend(probe_ids_for_profiles(concept_profiles))
    return list(dict.fromkeys(checks))


def validate_reference_params_for_plan(plan: PatchPlan) -> list[ValidationIssue]:
    """Validate static OP-path reference params before mutating TouchDesigner.

    The check intentionally stays conservative: it proves references between
    nodes created by the same plan are present and type-compatible, while
    allowing references to pre-existing external nodes that cannot be typed
    without live TD inspection.
    """
    created_types = _created_node_types(plan)
    params_by_path = _params_by_target(plan)
    issues: list[ValidationIssue] = []

    material_required = _plan_requires_geometry_material(plan, created_types)
    for path, op_type in created_types.items():
        rules = list(_REFERENCE_PARAM_RULES.get(op_type, ()))
        if op_type == "geometryCOMP" and material_required:
            rules.append(
                {
                    "param": "material",
                    "expected_family": "MAT",
                    "label": "Material MAT",
                    "source": "Geometry COMP",
                }
            )
        if not rules:
            continue
        params = params_by_path.get(path, {})
        for rule in rules:
            issues.extend(_validate_reference_rule(path, op_type, params, rule, created_types))
    return issues


def _created_node_types(plan: PatchPlan) -> dict[str, str]:
    created: dict[str, str] = {}
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        name = operation.args.get("name")
        raw_type = operation.args.get("op_type")
        if not name or not raw_type:
            continue
        parent = operation.target or plan.target_root
        created[_join_path(parent, str(name))] = _canonical_op_type(str(raw_type))
    return created


def _params_by_target(plan: PatchPlan) -> dict[str, dict[str, Any]]:
    params: dict[str, dict[str, Any]] = {}
    for operation in plan.operations:
        if operation.kind != "set_params" or not operation.target:
            continue
        payload = operation.args.get("params")
        if not isinstance(payload, dict):
            continue
        target_params = params.setdefault(str(operation.target), {})
        target_params.update(payload)
    return params


def _validate_reference_rule(
    path: str,
    op_type: str,
    params: dict[str, Any],
    rule: dict[str, Any],
    created_types: dict[str, str],
) -> list[ValidationIssue]:
    if "any_of" in rule:
        param_names = tuple(str(item) for item in rule["any_of"])
        present = [name for name in param_names if _has_reference_value(params.get(name))]
        if not present:
            return [
                _reference_issue(
                    code="missing_reference_param",
                    message=f"{path} ({op_type}) is missing one of {', '.join(param_names)} for {rule['label']}.",
                    path=path,
                )
            ]
        return [
            issue
            for name in present
            for issue in _validate_reference_value(path, op_type, name, params.get(name), rule, created_types)
        ]

    param_name = str(rule["param"])
    if not _has_reference_value(params.get(param_name)):
        return [
            _reference_issue(
                code="missing_reference_param",
                message=f"{path} ({op_type}) is missing reference parameter {param_name} for {rule['label']}.",
                path=path,
            )
        ]
    return _validate_reference_value(path, op_type, param_name, params.get(param_name), rule, created_types)


def _validate_reference_value(
    path: str,
    op_type: str,
    param_name: str,
    value: Any,
    rule: dict[str, Any],
    created_types: dict[str, str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for ref in _reference_tokens(value):
        ref_type = created_types.get(ref)
        if ref_type is None:
            continue
        if not _reference_type_matches(ref_type, rule):
            expected = rule.get("expected_type") or f"{rule.get('expected_family')} family"
            issues.append(
                _reference_issue(
                    code="invalid_reference_param",
                    message=(
                        f"{path} ({op_type}) parameter {param_name} references {ref} "
                        f"({ref_type}), expected {expected} for {rule['label']}."
                    ),
                    path=path,
                )
            )
    return issues


def _reference_tokens(value: Any) -> list[str]:
    if isinstance(value, str):
        return [token for token in value.split() if token]
    if isinstance(value, (list, tuple, set)):
        tokens: list[str] = []
        for item in value:
            tokens.extend(_reference_tokens(item))
        return tokens
    return []


def _has_reference_value(value: Any) -> bool:
    return any(token.strip() for token in _reference_tokens(value))


def _reference_type_matches(ref_type: str, rule: dict[str, Any]) -> bool:
    expected_type = rule.get("expected_type")
    if expected_type:
        return ref_type == expected_type
    expected_family = rule.get("expected_family")
    if expected_family:
        return ref_type.endswith(str(expected_family))
    return True


def _plan_requires_geometry_material(plan: PatchPlan, created_types: dict[str, str]) -> bool:
    if any(op_type.endswith("MAT") for op_type in created_types.values()):
        return True
    return any(str(op_type).endswith("MAT") for op_type in plan.required_ops)


def _canonical_op_type(raw_type: str) -> str:
    compact = raw_type.strip()
    return _CREATE_TYPE_ALIASES.get(compact.lower(), compact)


def _reference_issue(*, code: str, message: str, path: str) -> ValidationIssue:
    return ValidationIssue(severity="error", code=code, message=message, path=path, source="tdpilot-brain")


def _join_path(parent: str, name: str) -> str:
    return f"{parent.rstrip('/')}/{name}".replace("//", "/")


def build_validation_report_v2(
    *,
    target_root: str,
    profile: str,
    concept_profile: str | None = None,
    concept_profiles: Iterable[str | None] | None = None,
    patch_result: PatchResult | None,
    cheap_metrics: dict[str, Any] | None = None,
    visual_quality_policy: str = "block",
) -> ValidationReportV2:
    """Build a profile-aware report from a PatchResult's validation payload."""
    raw_errors: list[dict[str, Any]] = []
    cook_stats: dict[str, Any] = {}
    if patch_result and patch_result.validation:
        raw_errors = list(patch_result.validation.errors)
        cook_stats = dict(patch_result.validation.cook_stats or {})
    issues = classify_validation_issues(raw_errors)
    metrics = dict(cheap_metrics or {})
    if patch_result and patch_result.validation:
        metrics.setdefault("cook_health", _cook_health_metrics(cook_stats))
    issues.extend(_cook_health_issues(cook_stats, target_root=target_root))
    selected_profiles = _report_concept_profiles(
        concept_profile=concept_profile,
        concept_profiles=concept_profiles,
    )
    if selected_profiles:
        metrics.setdefault("concept_profiles", selected_profiles)
        metrics.setdefault("profile_probes", probe_summaries_for_profiles(profile, selected_profiles))
    else:
        metrics.setdefault("profile_probes", probe_summaries_for_profile(profile, concept_profile))
    issues.extend(_profile_probe_issues(metrics, target_root=target_root))
    issues.extend(
        _visual_quality_issues(
            metrics,
            target_root=target_root,
            visual_quality_policy=visual_quality_policy,
        )
    )
    severity_counts: dict[str, int] = {}
    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
    ok = not any(issue.severity in {"error", "critical"} for issue in issues)
    summary = "clean" if ok else f"{len(issues)} validation issue(s)"
    checks = (
        checks_for_profiles(profile, selected_profiles)
        if selected_profiles
        else checks_for_profile(profile, concept_profile)
    )
    return ValidationReportV2(
        profile=profile,
        concept_profile=concept_profile,
        target_root=target_root,
        ok=ok,
        checks=checks,
        issues=issues,
        severity_counts=severity_counts,
        cheap_metrics=metrics,
        summary=summary,
    )


def static_profile_probe_metrics_for_plan(
    plan: PatchPlan,
    *,
    validation_profile: str,
    concept_profile: str | None,
) -> dict[str, Any]:
    """Return cheap profile-probe metrics derived from a PatchPlan's operator contract."""
    available_ops = _available_op_types_for_plan(plan)
    probe_results: list[dict[str, Any]] = []
    for probe in probe_summaries_for_profile(validation_profile, concept_profile):
        required_inputs = list(probe["required_inputs"])
        present, missing = _probe_input_presence(
            profile=str(probe["profile"]),
            probe_id=str(probe["probe_id"]),
            required_inputs=required_inputs,
            available_ops=available_ops,
        )
        status = "static_pass" if not missing else "static_incomplete"
        result = {
            "probe_id": probe["probe_id"],
            "profile": probe["profile"],
            "readback_strategy": probe["readback_strategy"],
            "metric_names": list(probe["metric_names"]),
            "present_required_inputs": present,
            "missing_required_inputs": missing,
            "status": status,
            "failure_message": probe["failure_message"],
        }
        if status == "static_pass":
            result.update(_static_probe_parameter_metrics(plan, probe=result))
            if result.get("missing_parameter_bindings"):
                status = "static_incomplete"
                result["status"] = status
            elif _requires_runtime_readback(str(result["readback_strategy"])):
                status = "runtime_contract_present"
                result["status"] = status
                result["runtime_required"] = True
                result["pending_metric_names"] = list(result["metric_names"])
        if status == "static_incomplete":
            if result.get("missing_parameter_bindings"):
                result["issue_code"] = "profile_probe_missing_parameter_binding"
                result["issue_message"] = _profile_probe_parameter_issue_message(result)
            else:
                result["issue_code"] = "profile_probe_missing_required_inputs"
                result["issue_message"] = _profile_probe_issue_message(result)
        probe_results.append(result)
    visual_sample = _default_visual_output_sample_result(plan, validation_profile=validation_profile)
    if visual_sample is not None:
        probe_results.append(visual_sample)
    return {"profile_probe_results": probe_results}


def _cook_health_metrics(cook_stats: dict[str, Any]) -> dict[str, Any]:
    stuck = cook_stats.get("stuck")
    if not isinstance(stuck, list):
        stuck = []
    metrics = {
        "stuck_count": len(stuck),
        "probe_error": cook_stats.get("probe_error"),
    }
    if "total_cook_ms" in cook_stats:
        metrics["total_cook_ms"] = cook_stats.get("total_cook_ms")
    if stuck:
        metrics["stuck_paths"] = [_cook_issue_path(item, fallback="") for item in stuck]
    return metrics


def _cook_health_issues(cook_stats: dict[str, Any], *, target_root: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    probe_error = cook_stats.get("probe_error")
    if probe_error:
        issues.append(
            ValidationIssue(
                severity="error",
                code="cook_health_probe_failed",
                message=f"cook_health: Cooking probe failed: {probe_error}",
                path=target_root,
                source="touchdesigner",
            )
        )

    stuck = cook_stats.get("stuck")
    if not isinstance(stuck, list):
        return issues
    for item in stuck:
        path = _cook_issue_path(item, fallback=target_root)
        duration = _cook_issue_duration(item)
        duration_text = f" after {duration:g} ms" if duration is not None else ""
        issues.append(
            ValidationIssue(
                severity="error",
                code="cook_health_stuck",
                message=f"cook_health: {path} is stuck cooking{duration_text}.",
                path=path,
                source="touchdesigner",
            )
        )
    return issues


def _cook_issue_path(item: Any, *, fallback: str) -> str:
    if isinstance(item, dict):
        raw_path = item.get("path") or item.get("node") or item.get("op")
        if raw_path:
            return str(raw_path)
    if isinstance(item, str) and item:
        return item
    return fallback


def _cook_issue_duration(item: Any) -> float | None:
    if not isinstance(item, dict):
        return None
    for key in ("cook_time_ms", "cook_ms", "duration_ms", "total_cook_ms"):
        value = item.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def static_profile_probe_metrics_for_profiles(
    plan: PatchPlan,
    *,
    validation_profile: str,
    concept_profiles: Iterable[str | None],
) -> dict[str, Any]:
    """Return deduplicated static profile-probe metrics for several profile layers."""
    profiles = [profile for profile in dict.fromkeys(concept_profiles) if profile]
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for profile in profiles:
        metrics = static_profile_probe_metrics_for_plan(
            plan,
            validation_profile=validation_profile,
            concept_profile=profile,
        )
        for result in metrics["profile_probe_results"]:
            key = (str(result["profile"]), str(result["probe_id"]))
            if key in seen:
                continue
            seen.add(key)
            results.append(result)
    return {"concept_profiles": profiles, "profile_probe_results": results}


def _report_concept_profiles(
    *,
    concept_profile: str | None,
    concept_profiles: Iterable[str | None] | None,
) -> list[str]:
    profiles = [str(profile) for profile in (concept_profiles or []) if profile]
    if concept_profile:
        profiles.append(str(concept_profile))
    return list(dict.fromkeys(profiles))


def _profile_probe_issues(metrics: dict[str, Any], *, target_root: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for result in metrics.get("profile_probe_results", []):
        if not isinstance(result, dict) or result.get("status") not in {
            "static_incomplete",
            "runtime_failed",
            "runtime_unavailable",
        }:
            continue
        probe_id = str(result.get("probe_id") or "unknown_probe")
        code = str(result.get("issue_code") or "profile_probe_missing_required_inputs")
        message = str(result.get("issue_message") or _profile_probe_issue_message(result))
        issues.append(
            ValidationIssue(
                severity="error",
                code=code,
                message=message,
                path=target_root,
                source="tdpilot-brain",
            )
        )
    return issues


def _visual_quality_issues(
    metrics: dict[str, Any],
    *,
    target_root: str,
    visual_quality_policy: str,
) -> list[ValidationIssue]:
    if visual_quality_policy == "off":
        return []
    severity = "warning" if visual_quality_policy == "warn" else "error"
    visual_quality = metrics.get("visual_quality")
    if not isinstance(visual_quality, dict):
        return []
    issues: list[ValidationIssue] = []
    for path, quality in visual_quality.items():
        if not isinstance(quality, dict) or quality.get("pass") is not False:
            continue
        fail_reasons = quality.get("fail_reasons")
        if isinstance(fail_reasons, list):
            reasons = [str(item) for item in fail_reasons if item]
        else:
            reasons = []
        reason_text = ", ".join(reasons) if reasons else "normalized visual quality did not pass"
        issues.append(
            ValidationIssue(
                severity=severity,
                code="visual_quality_failed",
                message=f"visual_quality: {path} failed normalized pixel quality: {reason_text}.",
                path=str(path) if path else target_root,
                source="tdpilot-brain",
            )
        )
    return issues


def _profile_probe_issue_message(result: dict[str, Any]) -> str:
    probe_id = str(result.get("probe_id") or "unknown_probe")
    missing = [str(item) for item in result.get("missing_required_inputs", [])]
    missing_text = ", ".join(missing) if missing else "required inputs"
    message = str(result.get("failure_message") or f"Profile probe {probe_id} is incomplete.")
    return f"{probe_id}: {message} Missing required inputs: {missing_text}."


def _profile_probe_parameter_issue_message(result: dict[str, Any]) -> str:
    probe_id = str(result.get("probe_id") or "unknown_probe")
    missing = [str(item) for item in result.get("missing_parameter_bindings", [])]
    missing_text = ", ".join(missing) if missing else "required parameter bindings"
    message = str(result.get("failure_message") or f"Profile probe {probe_id} is incomplete.")
    return f"{probe_id}: {message} Missing parameter bindings: {missing_text}."


def _static_probe_parameter_metrics(plan: PatchPlan, *, probe: dict[str, Any]) -> dict[str, list[str]]:
    if probe.get("profile") == "dat_protocol" and probe.get("probe_id") == "render_switch_index_binding":
        return _render_switch_index_binding_metrics(plan)
    return {}


def _requires_runtime_readback(readback_strategy: str) -> bool:
    return readback_strategy in _RUNTIME_READBACK_STRATEGIES


def _default_visual_output_sample_result(
    plan: PatchPlan,
    *,
    validation_profile: str,
) -> dict[str, Any] | None:
    if validation_profile not in _STRUCTURAL_VALIDATION_PROFILES:
        return None
    available_ops = _available_op_types_for_plan(plan)
    if "nullTOP" not in available_ops:
        return None
    return {
        "probe_id": "visual_output_sample",
        "profile": "visual_output",
        "readback_strategy": "top_visual_cheap_runtime",
        "metric_names": ["output_luminance", "output_alpha_coverage", "output_entropy"],
        "present_required_inputs": ["nullTOP"],
        "missing_required_inputs": [],
        "status": "runtime_contract_present",
        "runtime_required": True,
        "pending_metric_names": ["output_luminance", "output_alpha_coverage", "output_entropy"],
        "failure_message": "Visual plans must expose a sampleable TOP output with non-empty pixels.",
    }


def _render_switch_index_binding_metrics(plan: PatchPlan) -> dict[str, list[str]]:
    created_types = _created_node_types(plan)
    params_by_target = _params_by_target(plan)
    table_paths = {path for path, op_type in created_types.items() if op_type == "tableDAT"}
    switch_paths = [path for path, op_type in created_types.items() if op_type == "switchTOP"]
    for switch_path in switch_paths:
        expression = params_by_target.get(switch_path, {}).get("index")
        if not isinstance(expression, dict) or set(expression) != {"expr"}:
            continue
        expr_text = expression.get("expr")
        if not isinstance(expr_text, str):
            continue
        match = _RENDER_SWITCH_INDEX_EXPR.fullmatch(expr_text.strip())
        if match and match.group("table_path") in table_paths:
            return {
                "present_parameter_bindings": ["switchTOP.index<-tableDAT"],
                "missing_parameter_bindings": [],
            }
    return {
        "present_parameter_bindings": [],
        "missing_parameter_bindings": ["switchTOP.index<-tableDAT"],
    }


def _available_op_types_for_plan(plan: PatchPlan) -> set[str]:
    op_types = {_canonical_op_type(op_type) for op_type in plan.required_ops}
    op_types.update(_created_node_types(plan).values())
    return op_types


def _probe_input_presence(
    *,
    profile: str,
    probe_id: str,
    required_inputs: list[str],
    available_ops: set[str],
) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    grouped: set[str] = set()
    for group in _ALTERNATIVE_PROBE_INPUTS.get((profile, probe_id), ()):
        group_inputs = [op_type for op_type in required_inputs if op_type in group]
        if not group_inputs:
            continue
        grouped.update(group_inputs)
        group_present = [op_type for op_type in group_inputs if op_type in available_ops]
        if group_present:
            present.extend(group_present)
        else:
            missing.extend(group_inputs)
    for op_type in required_inputs:
        if op_type in grouped:
            continue
        if op_type in available_ops:
            present.append(op_type)
        else:
            missing.append(op_type)
    return present, missing
