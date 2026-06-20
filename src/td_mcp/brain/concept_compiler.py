"""Deterministic Phase 1 concept compiler for selected multi-domain prompts."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from td_mcp.brain.patterns import docs_evidence_for_patterns, load_pattern_registry, patterns_by_id
from td_mcp.models.brain import (
    BrainPattern,
    CandidateConceptGraph,
    CompiledVisualTaskSpec,
    ConceptEdge,
    DataDomain,
)

_DOMAIN_ORDER: tuple[DataDomain, ...] = ("CHOP", "TOP", "COMP", "DAT", "SOP", "POP", "MAT", "ANY")
_PROFILE_ORDER = ("audio_reactive", "feedback", "panel_ui")
_PHASE_ONE_PATTERN_IDS = (
    "audio_analysis_chop_chain",
    "feedback_top_loop",
    "panel_control_output",
    "debug_output_conventions",
)


def compile_visual_task(
    intent: str,
    *,
    target_root: str = "/project1",
    output_top: str | None = None,
    constraints: dict[str, Any] | None = None,
    preferred_domains: list[str] | None = None,
    validation_profile: str = "auto",
    card_index=None,
) -> CompiledVisualTaskSpec:
    """Compile a prompt into a narrow, deterministic Phase 1 task spec."""
    text = (intent or "").strip()
    normalized = text.lower()
    constraints = constraints or {}
    preferred_domains = preferred_domains or []

    domains: list[DataDomain] = []
    motifs: list[str] = []
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    capabilities: list[str] = []
    profiles: list[str] = []
    families: list[DataDomain] = []
    validation_needs: list[str] = []
    risk_flags: list[str] = []

    if _has_audio(normalized):
        domains.append("CHOP")
        families.append("CHOP")
        motifs.append("audio-reactive")
        inputs.append({"kind": "audio", "domain": "CHOP", "source": "file_or_live_audio"})
        capabilities.append("audio_analysis")
        profiles.append("audio_reactive")
        validation_needs.extend(["audio_source_present", "analysis_stage", "range_mapping"])

    if _has_feedback(normalized):
        domains.append("TOP")
        families.append("TOP")
        motifs.append("feedback")
        outputs.append({"kind": "stable_output", "domain": "TOP", "path": output_top})
        capabilities.append("feedback_loop")
        profiles.append("feedback")
        validation_needs.extend(["feedback_cycle", "decay_control", "cheap_visual_metrics"])
        risk_flags.append("validate-feedback-decay")

    if _has_panel(normalized):
        domains.extend(["COMP", "CHOP"])
        families.extend(["COMP", "CHOP"])
        motifs.append("control-panel")
        outputs.append({"kind": "control_output", "domain": "CHOP"})
        capabilities.append("panel_controls")
        profiles.append("panel_ui")
        validation_needs.extend(["panel_components_present", "panel_state_reader", "control_output"])

    if _has_debug(normalized):
        domains.append("DAT")
        families.append("DAT")
        motifs.append("debug-output")
        outputs.append({"kind": "debug_output", "domain": "DAT"})
        capabilities.append("debug_output")
        validation_needs.append("output_node_present")

    for domain in preferred_domains:
        upper = str(domain).upper()
        if upper in _DOMAIN_ORDER:
            domains.append(upper)  # type: ignore[arg-type]
            families.append(upper)  # type: ignore[arg-type]

    blocked_questions: list[str] = []
    if not capabilities and _intent_is_under_specified(normalized, preferred_domains):
        blocked_questions.append(
            "What visual system should TDPilot build: feedback, audio-reactive, POP, GLSL, render pipeline, panel UI, or a specific operator chain?"
        )

    if text and not blocked_questions and not _is_supported_phase_one_route(profiles, capabilities):
        risk_flags.append("compiler-route-not-selected")

    seed_ops = _seed_ops_for_features(profiles, capabilities)
    grounding = ["compiler:deterministic-v1"]
    grounding.extend(_docs_evidence_from_card_index(seed_ops, card_index))

    return CompiledVisualTaskSpec(
        id=_compiled_task_id(text, target_root, output_top),
        intent=text,
        target_root=target_root,
        output_top=output_top,
        domains=_ordered_domains(domains),
        motifs=list(dict.fromkeys(motifs)),
        inputs=inputs,
        outputs=outputs,
        constraints={**constraints, "validation_profile": validation_profile},
        required_capabilities=list(dict.fromkeys(capabilities)),
        candidate_profiles=[profile for profile in _PROFILE_ORDER if profile in profiles],
        candidate_operator_families=_ordered_domains(families),
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(dict.fromkeys(grounding)),
        blocked_questions=blocked_questions,
    )


def build_candidate_graphs(
    compiled: CompiledVisualTaskSpec,
    *,
    patterns: list[BrainPattern] | None = None,
) -> list[CandidateConceptGraph]:
    """Resolve supported compiler output into ranked candidate graphs."""
    if compiled.blocked_questions:
        return []
    if not _is_supported_phase_one_route(compiled.candidate_profiles, compiled.required_capabilities):
        return []

    registry = patterns_by_id(patterns or load_pattern_registry())
    selected = [registry[pattern_id] for pattern_id in _PHASE_ONE_PATTERN_IDS if pattern_id in registry]
    if len(selected) != len(_PHASE_ONE_PATTERN_IDS):
        return []

    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    for pattern in selected:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)

    edges.extend(
        [
            ConceptEdge(source="audio_out", target="feedback_decay", kind="control"),
            ConceptEdge(source="panel_out", target="feedback_decay", kind="control"),
            ConceptEdge(source="stable_output", target="debug_notes", kind="reference"),
        ]
    )

    required_ops = sorted(set(required_ops))
    pattern_evidence = docs_evidence_for_patterns(selected)

    return [
        CandidateConceptGraph(
            id=f"candidate:{compiled.id}:audio-feedback-panel-debug",
            compiled_task_id=compiled.id,
            label="Audio-reactive feedback visual with panel controls and debug output",
            profiles=["audio_reactive", "feedback", "panel_ui"],
            pattern_ids=[pattern.pattern_id for pattern in selected],
            concepts=concepts,
            edges=edges,
            required_ops=required_ops,
            optional_ops=sorted(set(optional_ops)),
            expected_outputs=[
                item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")
            ],
            validation_needs=list(dict.fromkeys(validation_needs)),
            risk_flags=list(dict.fromkeys(risk_flags)),
            grounding_evidence=list(dict.fromkeys([*compiled.grounding_evidence, *pattern_evidence])),
            score=0.95,
            explanation=(
                "Composes audio analysis, feedback, panel control, and debug-output patterns "
                "for the selected Phase 1 multi-domain prompt."
            ),
        )
    ]


def is_supported_compiler_route(compiled: CompiledVisualTaskSpec) -> bool:
    """Return True when Phase 1 should use the compiler/pattern path."""
    return not compiled.blocked_questions and _is_supported_phase_one_route(
        compiled.candidate_profiles, compiled.required_capabilities
    )


def _has_audio(text: str) -> bool:
    return any(token in text for token in ("audio", "music", "sound", "beat", "spectrum"))


def _has_feedback(text: str) -> bool:
    return any(token in text for token in ("feedback", "trail", "echo", "recursion"))


def _has_panel(text: str) -> bool:
    if any(token in text for token in ("control panel", "panel", "slider", "button")):
        return True
    # "ui" must match as a whole word — a bare substring also matches "build",
    # "fluid", "guide", etc., which would spuriously flag panel UI intent.
    return bool(re.search(r"\bui\b", text))


def _has_debug(text: str) -> bool:
    return any(token in text for token in ("debug", "diagnostic", "inspect"))


def _intent_is_under_specified(text: str, preferred_domains: list[str]) -> bool:
    if preferred_domains:
        return False
    if len(text.split()) <= 3:
        return True
    vague_tokens = ("better", "cool", "nice", "awesome", "improve", "enhance")
    return any(token in text for token in vague_tokens)


def _is_supported_phase_one_route(profiles: list[str], capabilities: list[str]) -> bool:
    profile_set = set(profiles)
    capability_set = set(capabilities)
    return {"audio_reactive", "feedback", "panel_ui"}.issubset(profile_set) and {
        "audio_analysis",
        "feedback_loop",
        "panel_controls",
        "debug_output",
    }.issubset(capability_set)


def _seed_ops_for_features(profiles: list[str], capabilities: list[str]) -> list[str]:
    ops: list[str] = []
    if "audio_reactive" in profiles:
        ops.extend(["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"])
    if "feedback" in profiles:
        ops.extend(["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"])
    if "panel_ui" in profiles:
        ops.extend(["containerCOMP", "sliderCOMP", "buttonCOMP", "panelCHOP", "nullCHOP"])
    if "debug_output" in capabilities:
        ops.append("textDAT")
    return sorted(set(ops))


def _docs_evidence_from_card_index(op_types: list[str], card_index) -> list[str]:
    if card_index is None:
        return []
    evidence: list[str] = []
    for op_type in op_types:
        try:
            card = card_index.get_operator(op_type)
        except Exception:
            card = None
        if card is not None:
            evidence.append(f"docs:{op_type}")
    return evidence


def _ordered_domains(domains: list[DataDomain]) -> list[DataDomain]:
    seen = set(domains)
    return [domain for domain in _DOMAIN_ORDER if domain in seen]


def _compiled_task_id(intent: str, target_root: str, output_top: str | None) -> str:
    payload = "\n".join([intent.strip().lower(), target_root, output_top or ""])
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"compiled:{digest}"


__all__ = ["build_candidate_graphs", "compile_visual_task", "is_supported_compiler_route"]
