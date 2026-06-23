"""Live operator availability sampling for atlas gap review."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from td_mcp.models.brain import (
    AvailabilitySubstitutionExplanation,
    OperatorAvailabilityMatrix,
    OperatorSubstitutionRule,
)

_REQUIRED_SUBSTITUTION_RULES: dict[str, tuple[str, ...]] = {
    "audiofileinCHOP": ("audiodeviceinCHOP",),
    "glslcreatePOP": ("glsladvancedPOP", "topologyPOP"),
    "bandeqCHOP": ("audiobandeqCHOP",),
    "etherdreamCHOP": ("laserdeviceCHOP",),
    "heliosdacCHOP": ("laserdeviceCHOP",),
    "parametriceqCHOP": ("audioparaeqCHOP",),
    "realsenseCHOP": ("realsenseTOP",),
    "fieldCOMP": ("textCOMP",),
    "webDAT": ("webclientDAT",),
    "svgTOP": ("webrenderTOP",),
    "scanCHOP": ("laserCHOP",),
    "fontSOP": ("textSOP",),
}


def load_operator_substitution_rules() -> list[OperatorSubstitutionRule]:
    """Return official-docs-backed Phase 2 seed substitution rules."""
    return [
        OperatorSubstitutionRule(
            missing_op="audiofileinCHOP",
            replacement_ops=["audiodeviceinCHOP"],
            replacement_pattern="audio_device_to_analysis_chop",
            confidence="medium",
            tradeoffs=["uses a live audio input device instead of a deterministic audio file"],
            official_sources=[
                "https://docs.derivative.ca/Audio_File_In_CHOP",
                "https://docs.derivative.ca/Audio_Device_In_CHOP",
            ],
            requires_user_approval=True,
        ),
        OperatorSubstitutionRule(
            missing_op="bandeqCHOP",
            replacement_ops=["audiobandeqCHOP"],
            replacement_pattern=None,
            confidence="high",
            tradeoffs=["uses the newer audio band equalizer operator with better-quality filters"],
            official_sources=[
                "https://docs.derivative.ca/Band_EQ_CHOP",
                "https://docs.derivative.ca/Audio_Band_EQ_CHOP",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="parametriceqCHOP",
            replacement_ops=["audioparaeqCHOP"],
            replacement_pattern=None,
            confidence="high",
            tradeoffs=["uses the newer audio parametric equalizer with the current audio EQ parameter model"],
            official_sources=[
                "https://docs.derivative.ca/Parametric_EQ_CHOP",
                "https://docs.derivative.ca/Audio_Para_EQ_CHOP",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="fieldCOMP",
            replacement_ops=["textCOMP"],
            replacement_pattern=None,
            confidence="high",
            tradeoffs=["uses the modern Text COMP panel instead of the deprecated Field COMP control"],
            official_sources=[
                "https://docs.derivative.ca/Field_COMP",
                "https://docs.derivative.ca/Text_COMP",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="etherdreamCHOP",
            replacement_ops=["laserdeviceCHOP"],
            replacement_pattern=None,
            confidence="high",
            tradeoffs=["uses the unified Laser Device CHOP route for EtherDream laser output"],
            official_sources=[
                "https://docs.derivative.ca/EtherDream_CHOP",
                "https://docs.derivative.ca/Laser_Device_CHOP",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="heliosdacCHOP",
            replacement_ops=["laserdeviceCHOP"],
            replacement_pattern=None,
            confidence="high",
            tradeoffs=["uses the unified Laser Device CHOP route for Helios laser output"],
            official_sources=[
                "https://docs.derivative.ca/Helios_DAC_CHOP",
                "https://docs.derivative.ca/Laser_Device_CHOP",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="webDAT",
            replacement_ops=["webclientDAT"],
            replacement_pattern=None,
            confidence="high",
            tradeoffs=["uses the modern Web Client DAT request workflow instead of the deprecated Web DAT"],
            official_sources=[
                "https://docs.derivative.ca/Web_DAT",
                "https://docs.derivative.ca/Web_Client_DAT",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="glslcreatePOP",
            replacement_ops=["glsladvancedPOP", "topologyPOP"],
            replacement_pattern=None,
            confidence="high",
            tradeoffs=[
                "requires the newer GLSL Advanced POP workflow and explicit topology when output counts change"
            ],
            official_sources=[
                "https://docs.derivative.ca/GLSL_Create_POP",
                "https://docs.derivative.ca/GLSL_Advanced_POP",
                "https://docs.derivative.ca/Topology_POP",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="svgTOP",
            replacement_ops=["webrenderTOP"],
            replacement_pattern=None,
            confidence="medium",
            tradeoffs=["requires a web-rendering route instead of the deprecated nonfunctional SVG TOP"],
            official_sources=[
                "https://docs.derivative.ca/SVG_TOP",
                "https://docs.derivative.ca/Web_Render_TOP",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="scanCHOP",
            replacement_ops=["laserCHOP"],
            replacement_pattern=None,
            confidence="high",
            tradeoffs=["uses the current Laser CHOP point-generation route instead of the legacy Scan CHOP"],
            official_sources=[
                "https://docs.derivative.ca/Scan_CHOP",
                "https://docs.derivative.ca/Laser_CHOP",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="fontSOP",
            replacement_ops=["textSOP"],
            replacement_pattern=None,
            confidence="high",
            tradeoffs=[
                "uses the current Text SOP TrueType/OpenType geometry path instead of the legacy Font SOP"
            ],
            official_sources=[
                "https://docs.derivative.ca/Font_SOP",
                "https://docs.derivative.ca/Text_SOP",
            ],
            requires_user_approval=False,
        ),
        OperatorSubstitutionRule(
            missing_op="realsenseCHOP",
            replacement_ops=["realsenseTOP"],
            replacement_pattern=None,
            confidence="low",
            tradeoffs=[
                "only preserves RealSense camera streams; it does not replace deprecated skeleton tracking behavior"
            ],
            official_sources=[
                "https://docs.derivative.ca/RealSense_CHOP",
                "https://docs.derivative.ca/RealSense_TOP",
            ],
            requires_user_approval=True,
        ),
    ]


def operator_availability_coverage_report(
    rules: list[OperatorSubstitutionRule] | None = None,
) -> dict[str, Any]:
    """Report release-gate coverage for docs-grounded substitution rules."""
    records = rules if rules is not None else load_operator_substitution_rules()
    by_missing = {rule.missing_op: rule for rule in records}

    missing_required: list[str] = []
    replacement_mismatches: list[dict[str, Any]] = []
    invalid_sources: list[dict[str, str]] = []
    missing_tradeoffs: list[str] = []

    for missing_op, expected_replacements in _REQUIRED_SUBSTITUTION_RULES.items():
        rule = by_missing.get(missing_op)
        if rule is None:
            missing_required.append(missing_op)
            continue
        actual = set(rule.replacement_ops)
        expected = set(expected_replacements)
        if not expected.issubset(actual):
            replacement_mismatches.append(
                {
                    "missing_op": missing_op,
                    "expected_replacement_ops": sorted(expected),
                    "actual_replacement_ops": sorted(actual),
                }
            )

    for rule in records:
        if not rule.tradeoffs:
            missing_tradeoffs.append(rule.missing_op)
        for source in rule.official_sources:
            if not source.startswith("https://docs.derivative.ca/"):
                invalid_sources.append({"missing_op": rule.missing_op, "official_source": source})

    covered_required = sorted(
        missing_op
        for missing_op in _REQUIRED_SUBSTITUTION_RULES
        if missing_op in by_missing
        and not any(item["missing_op"] == missing_op for item in replacement_mismatches)
    )
    return {
        "schema_version": 1,
        "ok": not missing_required
        and not replacement_mismatches
        and not invalid_sources
        and not missing_tradeoffs,
        "rule_count": len(records),
        "required_rule_count": len(_REQUIRED_SUBSTITUTION_RULES),
        "covered_required_rule_count": len(covered_required),
        "covered_required_missing_ops": covered_required,
        "missing_required_rule_count": len(missing_required),
        "missing_required_rules": missing_required,
        "replacement_mismatch_count": len(replacement_mismatches),
        "replacement_mismatches": replacement_mismatches,
        "invalid_source_count": len(invalid_sources),
        "invalid_sources": invalid_sources,
        "missing_tradeoff_count": len(missing_tradeoffs),
        "missing_tradeoff_rules": sorted(missing_tradeoffs),
    }


def substitution_explanations_from_evidence(
    evidence: list[str],
    availability_matrix: OperatorAvailabilityMatrix | None = None,
) -> list[AvailabilitySubstitutionExplanation]:
    """Translate internal substitution evidence into stable user-facing records."""
    if not evidence:
        return []

    rules = load_operator_substitution_rules()
    rules_by_target = {
        (rule.missing_op, rule.replacement_pattern or "+".join(rule.replacement_ops)): rule for rule in rules
    }
    rules_by_missing = {rule.missing_op: rule for rule in rules}
    marker_rules = {
        marker_rule["missing_op"]: marker_rule
        for item in evidence
        if (marker_rule := _parse_substitution_rule_marker(item)) is not None
    }
    explanations: list[AvailabilitySubstitutionExplanation] = []
    seen: set[tuple[str, str]] = set()

    for item in evidence:
        event = _parse_substitution_event_marker(item)
        if event is None:
            continue

        missing_op = event["missing_op"]
        replacement_target = event["replacement_target"]
        key = (missing_op, replacement_target)
        if key in seen:
            continue
        seen.add(key)

        rule = rules_by_target.get(key) or rules_by_missing.get(missing_op)
        marker_rule = marker_rules.get(missing_op, {})
        replacement_ops = list(
            rule.replacement_ops
            if rule is not None
            else marker_rule.get("replacement_ops") or _replacement_ops_from_target(replacement_target)
        )
        confidence = str(rule.confidence if rule is not None else marker_rule.get("confidence") or "low")
        if confidence not in {"low", "medium", "high"}:
            confidence = "low"
        requires_approval = bool(
            rule.requires_user_approval if rule is not None else marker_rule.get("requires_approval")
        )
        approval_evidence = _substitution_approval_evidence(event, evidence)
        if requires_approval:
            approval_state = "pending" if event["pending_approval"] or not approval_evidence else "approved"
        else:
            approval_state = "not_required"
        availability_reason = _availability_reason_for(missing_op, availability_matrix)
        tradeoffs = list(rule.tradeoffs if rule is not None else [])
        official_sources = list(rule.official_sources if rule is not None else [])

        explanations.append(
            AvailabilitySubstitutionExplanation(
                missing_op=missing_op,
                replacement_target=replacement_target,
                replacement_ops=replacement_ops,
                confidence=confidence,  # type: ignore[arg-type]
                requires_approval=requires_approval,
                approval_state=approval_state,
                approval_evidence=approval_evidence,
                availability_reason=availability_reason,
                tradeoffs=tradeoffs,
                official_sources=official_sources,
                summary=_substitution_summary(
                    missing_op=missing_op,
                    replacement_target=replacement_target,
                    replacement_ops=replacement_ops,
                    availability_reason=availability_reason,
                    tradeoffs=tradeoffs,
                    approval_state=approval_state,
                ),
            )
        )

    return explanations


def build_operator_availability_matrix(
    available_ops: set[str],
    *,
    required_ops: list[str] | None = None,
    td_build: str = "unknown",
    platform: str = "unknown",
    installed_addons: list[str] | None = None,
) -> OperatorAvailabilityMatrix:
    """Build a typed availability matrix from inspected operator names."""
    requested = set(required_ops or [])
    all_ops = sorted(set(available_ops) | requested)
    operators: dict[str, dict[str, Any]] = {}
    family_aliases: dict[str, list[str]] = {}
    unavailable_reasons: dict[str, str] = {}

    for op_type in all_ops:
        family = _family_for_op(op_type)
        available = op_type in available_ops
        operators[op_type] = {"family": family, "available": available}
        family_aliases.setdefault(family, []).append(op_type)
        if not available:
            unavailable_reasons[op_type] = "missing from live family list"

    return OperatorAvailabilityMatrix(
        td_build=td_build,
        platform=platform,
        generated_at=datetime.now(timezone.utc).isoformat(),
        installed_addons=installed_addons or [],
        operators=operators,
        family_aliases={family: sorted(values) for family, values in family_aliases.items()},
        unavailable_reasons=unavailable_reasons,
    )


def availability_report_store_path(report: dict[str, Any], *, root: str | Path) -> Path:
    """Return the canonical per-build path for an operator availability report."""
    matrix = _availability_matrix_from_report(report)
    addon_slug = "_".join(sorted(_slug(addon) for addon in matrix.installed_addons)) or "no-addons"
    return (
        Path(root)
        / _slug(matrix.td_build, default="unknown-build")
        / _slug(matrix.platform, default="unknown-platform")
        / addon_slug
        / "operator_availability.json"
    )


def save_operator_availability_report(report: dict[str, Any], *, root: str | Path) -> Path:
    """Persist a sampled operator availability report by build, platform, and add-ons."""
    _availability_matrix_from_report(report)
    path = availability_report_store_path(report, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_operator_availability_report(path: str | Path) -> dict[str, Any]:
    """Load and validate a persisted operator availability report."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("operator availability report must be a JSON object")
    _availability_matrix_from_report(payload)
    return payload


def build_availability_targets(atlas_report: dict[str, Any]) -> list[dict[str, Any]]:
    """Build deprecated-gap and replacement-op sampling targets from atlas audit output."""
    coverage = atlas_report.get("docsbrain_operator_coverage", {})
    deprecated_gaps = coverage.get("deprecated_missing_operator_cards", [])
    if not isinstance(deprecated_gaps, list):
        return []

    targets: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()

    for gap in sorted(deprecated_gaps, key=lambda item: str(item.get("op_type") or "")):
        if not isinstance(gap, dict):
            continue
        op_type = str(gap.get("op_type") or "").strip()
        if not op_type:
            continue

        gap_target = {
            "op_type": op_type,
            "family": gap.get("family"),
            "role": "deprecated_gap",
            "gap_status": gap.get("gap_status"),
            "replacement_for": None,
        }
        _append_unique_target(targets, seen, gap_target)

        replacements = gap.get("replacement_op_types") or []
        if not isinstance(replacements, list):
            continue
        for replacement in sorted({str(item).strip() for item in replacements if str(item).strip()}):
            _append_unique_target(
                targets,
                seen,
                {
                    "op_type": replacement,
                    "family": None,
                    "role": "replacement",
                    "gap_status": None,
                    "replacement_for": op_type,
                },
            )

    return targets


async def sample_operator_availability(
    td_client: Any,
    targets: list[dict[str, Any]],
    *,
    parent_path: str = "/project1",
    scratch_name: str = "tdpilot_availability_probe",
) -> dict[str, Any]:
    """Create each target in a scratch COMP and report whether TD accepts it."""
    scratch_path = f"{parent_path.rstrip('/')}/{scratch_name}"
    results: list[dict[str, Any]] = []
    cleanup_ok = False
    cleanup_error = ""

    try:
        health = await td_client.health_check()
        health = await _health_with_info_fallback(td_client, health)
        await td_client.request(
            "node/create",
            {
                "parent_path": parent_path,
                "node_type": "baseCOMP",
                "name": scratch_name,
            },
        )

        for index, target in enumerate(targets):
            op_type = str(target.get("op_type") or "").strip()
            result = {
                "op_type": op_type,
                "family": target.get("family"),
                "role": target.get("role"),
                "gap_status": target.get("gap_status"),
                "replacement_for": target.get("replacement_for"),
                "available": False,
                "created_path": "",
                "error": "",
            }
            if not op_type:
                result["error"] = "missing op_type"
                results.append(result)
                continue

            try:
                create_response = await td_client.request(
                    "node/create",
                    {
                        "parent_path": scratch_path,
                        "node_type": op_type,
                        "name": _sample_node_name(op_type, index),
                    },
                )
                created_path = _created_path(create_response)
                result["available"] = bool(created_path)
                result["created_path"] = created_path
                if not created_path:
                    result["error"] = "node/create returned no path"
            except Exception as exc:  # noqa: BLE001 - report live TD rejection text.
                result["error"] = str(exc)
            results.append(result)

    finally:
        try:
            await td_client.request("node/delete", {"path": scratch_path})
            cleanup_ok = True
        except Exception as exc:  # noqa: BLE001 - cleanup status belongs in report.
            cleanup_error = str(exc)
        close = getattr(td_client, "close", None)
        if close is not None:
            await close()

    available_count = sum(1 for item in results if item["available"])
    report_ok = cleanup_ok and len(results) == len(targets)
    availability_matrix = _sample_results_availability_matrix(
        results, health if "health" in locals() else None
    )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": report_ok,
        "parent_path": parent_path,
        "scratch_name": scratch_name,
        "scratch_path": scratch_path,
        "td_health": health if "health" in locals() else None,
        "target_count": len(targets),
        "available_count": available_count,
        "unavailable_count": len(results) - available_count,
        "cleanup_ok": cleanup_ok,
        "cleanup_error": cleanup_error,
        "availability_matrix": availability_matrix.model_dump(),
        "results": results,
    }


async def _health_with_info_fallback(td_client: Any, health: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(health or {})
    if _has_known_build_and_platform(payload):
        return payload
    try:
        info = await td_client.request("info")
    except Exception:  # noqa: BLE001 - availability can still sample without metadata.
        return payload
    if not isinstance(info, dict):
        return payload
    if not payload.get("td_build") and not payload.get("build"):
        build = info.get("td_build") or info.get("build")
        if build:
            payload["td_build"] = build
    if not payload.get("platform"):
        platform = info.get("platform") or info.get("osName")
        if platform:
            payload["platform"] = platform
    if not payload.get("installed_addons") and isinstance(info.get("installed_addons"), list):
        payload["installed_addons"] = info["installed_addons"]
    return payload


def _has_known_build_and_platform(payload: dict[str, Any]) -> bool:
    build = str(payload.get("td_build") or payload.get("build") or "").strip().lower()
    platform = str(payload.get("platform") or "").strip().lower()
    return build not in {"", "unknown", "--"} and platform not in {"", "unknown", "--"}


def _append_unique_target(
    targets: list[dict[str, Any]],
    seen: set[tuple[str, str, str | None]],
    target: dict[str, Any],
) -> None:
    key = (
        str(target.get("op_type") or ""),
        str(target.get("role") or ""),
        target.get("replacement_for"),
    )
    if key in seen:
        return
    seen.add(key)
    targets.append(target)


def _sample_node_name(op_type: str, index: int) -> str:
    stem = re.sub(r"[^A-Za-z0-9_]+", "_", op_type).strip("_").lower() or "op"
    return f"probe_{index:02d}_{stem[:32]}"


def _created_path(response: Any) -> str:
    if not isinstance(response, dict):
        return ""
    node = response.get("node")
    if isinstance(node, dict) and node.get("path"):
        return str(node["path"])
    if response.get("path"):
        return str(response["path"])
    return ""


def _sample_results_availability_matrix(
    results: list[dict[str, Any]],
    health: dict[str, Any] | None,
) -> OperatorAvailabilityMatrix:
    operators: dict[str, dict[str, Any]] = {}
    family_aliases: dict[str, list[str]] = {}
    unavailable_reasons: dict[str, str] = {}

    for result in results:
        op_type = str(result.get("op_type") or "").strip()
        if not op_type:
            continue
        family = _matrix_family(result.get("family"), op_type)
        available = bool(result.get("available"))
        operators[op_type] = {"family": family, "available": available}
        family_aliases.setdefault(family, []).append(op_type)
        if not available:
            unavailable_reasons[op_type] = str(result.get("error") or "operator unavailable").strip()

    health = health or {}
    installed_addons = health.get("installed_addons")
    if not isinstance(installed_addons, list):
        installed_addons = []

    return OperatorAvailabilityMatrix(
        td_build=str(health.get("td_build") or health.get("build") or "unknown"),
        platform=str(health.get("platform") or "unknown"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        installed_addons=[str(addon) for addon in installed_addons],
        operators=operators,
        family_aliases={family: sorted(values) for family, values in family_aliases.items()},
        unavailable_reasons=unavailable_reasons,
    )


def _availability_matrix_from_report(report: dict[str, Any]) -> OperatorAvailabilityMatrix:
    raw = report.get("availability_matrix") if isinstance(report, dict) else None
    if not isinstance(raw, dict):
        raise ValueError("operator availability report requires availability_matrix")
    return OperatorAvailabilityMatrix.model_validate(raw)


def _availability_reason_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _parse_substitution_event_marker(evidence: str) -> dict[str, Any] | None:
    if not evidence.startswith("substitution:") or evidence.startswith("substitution-rule:"):
        return None
    payload = evidence.removeprefix("substitution:")
    parts = payload.split(":")
    mapping = parts[0]
    if "->" not in mapping:
        return None
    missing_op, replacement_target = mapping.split("->", 1)
    if not missing_op or not replacement_target:
        return None
    return {
        "missing_op": missing_op,
        "replacement_target": replacement_target,
        "pending_approval": "pending-approval" in parts[1:],
    }


def _parse_substitution_rule_marker(evidence: str) -> dict[str, Any] | None:
    if not evidence.startswith("substitution-rule:"):
        return None
    payload = evidence.removeprefix("substitution-rule:")
    parts = payload.split(":")
    if len(parts) < 2 or "->" not in parts[0]:
        return None
    missing_op, replacement_expr = parts[0].split("->", 1)
    return {
        "missing_op": missing_op,
        "replacement_ops": [item for item in replacement_expr.split("+") if item],
        "confidence": parts[1],
        "requires_approval": "requires-approval" in parts[2:],
    }


def _substitution_approval_evidence(event: dict[str, Any], evidence: list[str]) -> list[str]:
    expected_by_target = {
        "audio_device_to_analysis_chop": "device-source-declared:audio_device",
    }
    expected = expected_by_target.get(str(event.get("replacement_target") or ""))
    if expected is not None:
        return [item for item in evidence if item == expected]
    return [item for item in evidence if item.startswith("device-source-declared:")]


def _availability_reason_for(
    missing_op: str,
    availability_matrix: OperatorAvailabilityMatrix | None,
) -> str:
    if availability_matrix is None:
        return "operator unavailable in this TouchDesigner environment"
    reason = _availability_reason_text(availability_matrix.unavailable_reasons.get(missing_op))
    return reason or "operator unavailable in this TouchDesigner environment"


def _replacement_ops_from_target(replacement_target: str) -> list[str]:
    return [item for item in replacement_target.split("+") if item] or [replacement_target]


def _substitution_summary(
    *,
    missing_op: str,
    replacement_target: str,
    replacement_ops: list[str],
    availability_reason: str,
    tradeoffs: list[str],
    approval_state: str,
) -> str:
    clean_reason = _summary_availability_reason(availability_reason)
    summary = (
        f"{missing_op} is unavailable in this TouchDesigner environment ({clean_reason}), "
        f"so TDPilot selected {replacement_target} using {', '.join(replacement_ops)}."
    )
    if tradeoffs:
        summary = f"{summary} Tradeoff: {tradeoffs[0]}."
    if approval_state == "pending":
        summary = f"{summary} Approval is still pending before mutation."
    return summary


def _summary_availability_reason(reason: str) -> str:
    text = _availability_reason_text(reason)
    if not text:
        return "operator unavailable"
    noisy_fragments = ("traceback", "exception", "td command failed", "invalid arguments")
    if any(fragment in text.lower() for fragment in noisy_fragments):
        return "TouchDesigner rejected this operator during availability sampling"
    return text


def _slug(value: Any, *, default: str = "unknown") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-._")
    return text or default


def _matrix_family(value: Any, op_type: str) -> str:
    family = str(value or "").strip().upper()
    if family in {"CHOP", "TOP", "SOP", "POP", "DAT", "COMP", "MAT", "ANY"}:
        return family
    return _family_for_op(op_type)


def _family_for_op(op_type: str) -> str:
    upper = op_type.upper()
    for suffix in ("CHOP", "TOP", "SOP", "POP", "DAT", "COMP", "MAT"):
        if upper.endswith(suffix):
            return suffix
    return "ANY"
