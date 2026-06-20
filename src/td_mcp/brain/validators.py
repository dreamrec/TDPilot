"""Concept profiles and validation helpers for the TDPilot brain."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

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

CONCEPT_CHECKS: dict[str, tuple[str, ...]] = {
    "feedback": ("feedback_cycle", "decay_control", "feedback_static_warning_review"),
    "audio_reactive": ("audio_source_present", "analysis_stage", "range_mapping", "visual_or_chop_target"),
    "pop": ("pop_source_present", "pop_output_attached", "finite_pop_bounds", "attribute_sample_available"),
    "glsl": ("shader_source_present", "compile_state", "sampler_uniforms", "nonblack_output"),
    "glsl_material": (
        "shader_source_present",
        "material_assigned",
        "vertex_position_transform",
        "compile_state",
        "render_top_output",
    ),
    "glsl_pop": (
        "shader_source_present",
        "pop_attribute_class",
        "compile_state",
        "finite_pop_bounds",
        "attribute_sample_available",
    ),
    "render_pipeline": ("camera_present", "geometry_present", "material_or_default", "render_top_output"),
    "panel_ui": ("panel_components_present", "panel_state_reader", "callbacks_or_exports", "control_output"),
    "control_rig": ("custom_parameters_present", "bounds_or_ranges", "mapping_output", "target_bindings"),
    "generic": ("output_node_present",),
}

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
}


def classify_intent_profile(intent: str, preferred_domains: Iterable[str] | None = None) -> str:
    """Return the best-known concept profile for an intent."""
    text = (intent or "").lower()
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
    checks: list[str] = []
    if validation_profile in {"auto", "structural_visual_safe"}:
        checks.extend(STRUCTURAL_CHECKS)
    else:
        checks.append(validation_profile)
    if concept_profile:
        checks.extend(CONCEPT_CHECKS.get(concept_profile, ()))
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
    patch_result: PatchResult | None,
    cheap_metrics: dict[str, Any] | None = None,
) -> ValidationReportV2:
    """Build a profile-aware report from a PatchResult's validation payload."""
    raw_errors: list[dict[str, Any]] = []
    if patch_result and patch_result.validation:
        raw_errors = list(patch_result.validation.errors)
    issues = classify_validation_issues(raw_errors)
    severity_counts: dict[str, int] = {}
    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
    ok = not any(issue.severity in {"error", "critical"} for issue in issues)
    summary = "clean" if ok else f"{len(issues)} validation issue(s)"
    return ValidationReportV2(
        profile=profile,
        concept_profile=concept_profile,
        target_root=target_root,
        ok=ok,
        checks=checks_for_profile(profile, concept_profile),
        issues=issues,
        severity_counts=severity_counts,
        cheap_metrics=cheap_metrics or {},
        summary=summary,
    )
