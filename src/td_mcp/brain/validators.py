"""Concept profiles and validation helpers for the TDPilot brain."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from td_mcp.models.brain import ValidationIssue, ValidationReportV2
from td_mcp.models.patch import PatchResult

PROFILE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "feedback": ("feedback", "trail", "echo", "recursion", "displacement"),
    "audio_reactive": ("audio", "beat", "sound", "music", "spectrum", "reactive"),
    "pop": ("pop", "particle", "particles", "gpu particle", "simulation"),
    "glsl": ("glsl", "shader", "fragment", "pixel shader"),
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
    "render_pipeline": ("camera_present", "geometry_present", "material_or_default", "render_top_output"),
    "panel_ui": ("panel_components_present", "panel_state_reader", "callbacks_or_exports", "control_output"),
    "control_rig": ("custom_parameters_present", "bounds_or_ranges", "mapping_output", "target_bindings"),
    "generic": ("output_node_present",),
}


def classify_intent_profile(intent: str, preferred_domains: Iterable[str] | None = None) -> str:
    """Return the best-known concept profile for an intent."""
    text = (intent or "").lower()
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
