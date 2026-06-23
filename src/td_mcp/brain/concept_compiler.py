"""Deterministic Phase 1 concept compiler for selected multi-domain prompts."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from td_mcp.brain.patterns import load_pattern_registry
from td_mcp.models.brain import (
    BrainPattern,
    CandidateConceptGraph,
    CompiledVisualTaskSpec,
    DataDomain,
)

_DOMAIN_ORDER: tuple[DataDomain, ...] = ("CHOP", "TOP", "COMP", "DAT", "SOP", "POP", "MAT", "ANY")
_PROFILE_ORDER = (
    "audio_reactive",
    "feedback",
    "render_pipeline",
    "glsl_material",
    "glsl",
    "pop",
    "panel_ui",
    "midi_control",
    "dat_protocol",
    "video_io",
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
    routing_text = _primary_intent_text(normalized)
    deprecated_glsl_create_pop = _has_deprecated_glsl_create_pop(normalized)
    constraints = constraints or {}
    preferred_domains = preferred_domains or []

    domains: list[DataDomain] = []
    motifs: list[str] = []
    time_behavior: list[str] = []
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    capabilities: list[str] = []
    profiles: list[str] = []
    families: list[DataDomain] = []
    validation_needs: list[str] = []
    risk_flags: list[str] = []

    if _has_audio(routing_text):
        domains.append("CHOP")
        families.append("CHOP")
        motifs.append("audio-reactive")
        time_behavior.append("beat_or_amplitude_modulation")
        inputs.append({"kind": "audio", "domain": "CHOP", "source": "file_or_live_audio"})
        capabilities.append("audio_analysis")
        profiles.append("audio_reactive")
        validation_needs.extend(
            ["audio_source_present", "analysis_stage", "range_mapping", "audio_signal_activity"]
        )

    if _has_midi(routing_text):
        domains.append("CHOP")
        families.append("CHOP")
        motifs.append("midi-control")
        time_behavior.extend(["live_device_stream", "event_driven_control"])
        inputs.append({"kind": "midi", "domain": "CHOP", "source": "midi_device"})
        outputs.append({"kind": "control_output", "domain": "CHOP"})
        capabilities.append("midi_control")
        profiles.append("midi_control")
        validation_needs.extend(["midi_source_present", "range_mapping", "control_output"])
        risk_flags.append("device-source-required")

    if _has_serial_protocol(routing_text):
        domains.append("DAT")
        families.append("DAT")
        motifs.append("serial-protocol")
        time_behavior.append("streaming_input")
        inputs.append({"kind": "serial", "domain": "DAT", "source": "serial_device"})
        outputs.append({"kind": "protocol_table", "domain": "DAT"})
        capabilities.append("serial_dat_protocol")
        profiles.append("dat_protocol")
        validation_needs.extend(["serial_source_present", "protocol_table_output"])
        risk_flags.append("device-source-required")

    if _has_osc_protocol(routing_text):
        domains.append("DAT")
        families.append("DAT")
        motifs.append("osc-protocol")
        time_behavior.append("streaming_input")
        inputs.append({"kind": "osc", "domain": "DAT", "source": "osc_source"})
        outputs.append({"kind": "protocol_table", "domain": "DAT"})
        capabilities.append("osc_dat_protocol")
        profiles.append("dat_protocol")
        validation_needs.extend(["osc_source_present", "protocol_table_output"])
        risk_flags.append("device-source-required")

    if _has_websocket_protocol(routing_text):
        domains.append("DAT")
        families.append("DAT")
        motifs.append("websocket-protocol")
        time_behavior.append("streaming_input")
        inputs.append({"kind": "websocket", "domain": "DAT", "source": "websocket_endpoint"})
        outputs.append({"kind": "protocol_table", "domain": "DAT"})
        capabilities.append("websocket_dat_protocol")
        profiles.append("dat_protocol")
        validation_needs.extend(["websocket_source_present", "protocol_table_output"])
        risk_flags.append("device-source-required")

    if _has_mqtt_protocol(routing_text):
        domains.append("DAT")
        families.append("DAT")
        motifs.append("mqtt-protocol")
        time_behavior.append("streaming_input")
        inputs.append({"kind": "mqtt", "domain": "DAT", "source": "mqtt_broker"})
        outputs.append({"kind": "protocol_table", "domain": "DAT"})
        capabilities.append("mqtt_dat_protocol")
        profiles.append("dat_protocol")
        validation_needs.extend(["mqtt_source_present", "protocol_table_output"])
        risk_flags.append("device-source-required")

    if _has_udp_protocol(routing_text):
        domains.append("DAT")
        families.append("DAT")
        motifs.append("udp-protocol")
        time_behavior.append("streaming_input")
        inputs.append({"kind": "udp", "domain": "DAT", "source": "udp_source"})
        outputs.append({"kind": "protocol_table", "domain": "DAT"})
        capabilities.append("udp_dat_protocol")
        profiles.append("dat_protocol")
        validation_needs.extend(["udp_source_present", "protocol_table_output"])
        risk_flags.append("device-source-required")

    if _has_dat_table_render_switch(normalized):
        domains.extend(["TOP", "DAT"])
        families.extend(["TOP", "DAT"])
        motifs.append("dat-table-render-switch")
        time_behavior.append("table_driven_switching")
        inputs.append({"kind": "switch_table", "domain": "DAT", "source": "generated_table"})
        outputs.append({"kind": "stable_output", "domain": "TOP", "path": output_top})
        capabilities.append("dat_table_render_switch")
        profiles.append("dat_protocol")
        validation_needs.extend(
            [
                "render_switch_table_present",
                "render_switch_index_binding",
                "render_switch_output_present",
            ]
        )

    if _has_dat_execute_callback(normalized):
        domains.append("DAT")
        families.append("DAT")
        motifs.append("dat-table-callback")
        time_behavior.append("event_driven_callback")
        inputs.append({"kind": "table_dat", "domain": "DAT", "source": "generated_table"})
        outputs.append({"kind": "callback_dat", "domain": "DAT"})
        capabilities.append("dat_execute_callback")
        profiles.append("dat_protocol")
        validation_needs.extend(
            ["protocol_table_output", "dat_execute_callback_present", "callback_guard_present"]
        )
        risk_flags.append("validate-python-callback")

    if _has_ndi(routing_text):
        domains.append("TOP")
        families.append("TOP")
        motifs.append("ndi-video-input")
        time_behavior.append("streaming_input")
        inputs.append({"kind": "ndi", "domain": "TOP", "source": "ndi_network_source"})
        capabilities.append("ndi_input")
        profiles.append("video_io")
        validation_needs.append("ndi_source_present")
        risk_flags.append("device-source-required")
        if _has_post_fx(normalized) or _has_stable_top_output(normalized):
            outputs.append({"kind": "stable_output", "domain": "TOP", "path": output_top})
            capabilities.append("post_fx_output")
            validation_needs.extend(["post_fx_stage", "top_output_present"])

    if _has_glsl_top_shader(normalized):
        domains.extend(["TOP", "DAT"])
        families.extend(["TOP", "DAT"])
        motifs.append("glsl-top-shader")
        time_behavior.append("shader_frame_cook")
        if any(token in normalized for token in ("texture", "image", "fragment", "effect")):
            motifs.append("texture-effect")
        outputs.append({"kind": "stable_output", "domain": "TOP", "path": output_top})
        capabilities.append("glsl_top_shader")
        profiles.append("glsl")
        validation_needs.extend(["shader_source_present", "compile_state", "sampler_uniforms"])
        risk_flags.append("validate-glsl-compile-state")

    if _has_pop_particle_preview(normalized):
        domains.extend(["POP", "TOP"])
        families.extend(["POP", "TOP"])
        motifs.extend(["pop-particle-field", "preview"])
        time_behavior.append("continuous_animation")
        outputs.append({"kind": "stable_output", "domain": "POP"})
        outputs.append({"kind": "stable_output", "domain": "TOP", "path": output_top})
        capabilities.append("pop_particle_field_preview")
        profiles.append("pop")
        validation_needs.extend(
            ["pop_source_present", "pop_output_attached", "finite_pop_bounds", "attribute_sample_available"]
        )
        risk_flags.extend(["validate-finite-pop-bounds", "validate-pop-render-preview"])

    if _has_glsl_advanced_pop_topology(normalized):
        domains.extend(["POP", "TOP", "DAT"])
        families.extend(["POP", "TOP", "DAT"])
        motifs.extend(["glsl-advanced-pop", "topology-changing", "preview"])
        time_behavior.extend(["gpu_compute_dispatch", "continuous_animation"])
        if deprecated_glsl_create_pop:
            motifs.append("deprecated-glsl-create-pop")
        outputs.append({"kind": "stable_output", "domain": "POP"})
        outputs.append({"kind": "stable_output", "domain": "TOP", "path": output_top})
        capabilities.append("glsl_advanced_pop_topology")
        profiles.extend(["pop", "glsl"])
        validation_needs.extend(
            [
                "shader_source_present",
                "compile_state",
                "topology_capacity",
                "pop_output_attached",
                "finite_pop_bounds",
                "attribute_sample_available",
            ]
        )
        risk_flags.extend(["validate-glsl-compile-state", "validate-finite-pop-bounds"])
        if deprecated_glsl_create_pop:
            risk_flags.append("deprecated-op:glslcreatePOP")

    if _has_sop_terrain(normalized):
        domains.append("SOP")
        families.append("SOP")
        motifs.append("terrain-surface")
        time_behavior.append("continuous_animation")
        outputs.append({"kind": "stable_output", "domain": "SOP"})
        capabilities.append("terrain_surface")
        validation_needs.append("output_node_present")

    if _has_render_3d(normalized):
        domains.extend(["TOP", "COMP"])
        families.extend(["TOP", "COMP"])
        motifs.append("rendered-3d")
        time_behavior.append("continuous_animation")
        outputs.append({"kind": "stable_output", "domain": "TOP", "path": output_top})
        capabilities.append("render_pipeline")
        profiles.append("render_pipeline")
        validation_needs.extend(
            ["camera_present", "geometry_present", "camera_frustum_coverage", "render_top_output"]
        )

    if _has_material(normalized):
        domains.extend(["MAT", "DAT"])
        families.extend(["MAT", "DAT"])
        motifs.append("material-modulation")
        time_behavior.append("shader_frame_cook")
        capabilities.append("material_modulation")
        profiles.append("glsl_material")
        validation_needs.extend(["shader_source_present", "material_assigned", "compile_state"])

    if _has_feedback(normalized):
        domains.append("TOP")
        families.append("TOP")
        motifs.append("feedback")
        time_behavior.append("continuous_feedback")
        outputs.append({"kind": "stable_output", "domain": "TOP", "path": output_top})
        capabilities.append("feedback_loop")
        profiles.append("feedback")
        validation_needs.extend(
            ["feedback_cycle", "decay_control", "feedback_output_readback", "cheap_visual_metrics"]
        )
        risk_flags.append("validate-feedback-decay")

    if _has_panel(normalized):
        domains.extend(["COMP", "CHOP"])
        families.extend(["COMP", "CHOP"])
        motifs.append("control-panel")
        time_behavior.append("event_driven_control")
        outputs.append({"kind": "control_output", "domain": "CHOP"})
        capabilities.append("panel_controls")
        profiles.append("panel_ui")
        validation_needs.extend(
            ["panel_components_present", "panel_state_reader", "panel_state_readback", "control_output"]
        )

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

    seed_ops = _seed_ops_for_features(profiles, capabilities, risk_flags)
    grounding = ["compiler:deterministic-v1"]
    grounding.extend(_docs_evidence_from_card_index(seed_ops, card_index))

    return CompiledVisualTaskSpec(
        id=_compiled_task_id(text, target_root, output_top),
        intent=text,
        target_root=target_root,
        output_top=output_top,
        domains=_ordered_domains(domains),
        motifs=list(dict.fromkeys(motifs)),
        time_behavior=list(dict.fromkeys(time_behavior)),
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
    available_ops: set[str] | None = None,
    availability_matrix=None,
    device_sources: set[str] | None = None,
) -> list[CandidateConceptGraph]:
    """Resolve supported compiler output into ranked candidate graphs."""
    from td_mcp.brain.pattern_resolver import resolve_candidate_graphs

    return resolve_candidate_graphs(
        compiled,
        patterns=patterns or load_pattern_registry(),
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )


def is_supported_compiler_route(compiled: CompiledVisualTaskSpec) -> bool:
    """Return True when Phase 1 should use the compiler/pattern path."""
    return not compiled.blocked_questions and _is_supported_phase_one_route(
        compiled.candidate_profiles, compiled.required_capabilities
    )


def _primary_intent_text(text: str) -> str:
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


def _has_audio(text: str) -> bool:
    return any(token in text for token in ("audio", "music", "sound", "beat", "spectrum"))


def _has_midi(text: str) -> bool:
    return bool(re.search(r"\bmidi\b", text))


def _has_serial_protocol(text: str) -> bool:
    return bool(re.search(r"\bserial\b|\brs-?232\b", text))


def _has_osc_protocol(text: str) -> bool:
    return bool(re.search(r"\bosc\b", text)) and bool(re.search(r"\bdat\b|\bprotocol\b|\bbridge\b", text))


def _has_websocket_protocol(text: str) -> bool:
    return bool(re.search(r"\bweb[-\s]?socket\b", text)) and bool(
        re.search(r"\bdat\b|\bprotocol\b|\bbridge\b", text)
    )


def _has_mqtt_protocol(text: str) -> bool:
    return bool(re.search(r"\bmqtt\b", text)) and bool(re.search(r"\bdat\b|\bprotocol\b|\bbridge\b", text))


def _has_udp_protocol(text: str) -> bool:
    return bool(re.search(r"\budp\b", text)) and bool(re.search(r"\bdat\b|\bprotocol\b|\bbridge\b", text))


def _has_dat_table_render_switch(text: str) -> bool:
    return (
        bool(re.search(r"\bdat\b", text))
        and bool(re.search(r"\btable\b", text))
        and bool(re.search(r"\bswitch\b", text))
        and bool(re.search(r"\brender\b|\btop\b|\bvisual\b", text))
    )


def _has_dat_execute_callback(text: str) -> bool:
    has_dat_execute = bool(re.search(r"\bdat\s+execute\b|\bdatexecute\b", text))
    has_table_callback = (
        bool(re.search(r"\btable[-\s]+change\b", text))
        and "callback" in text
        and bool(re.search(r"\bdat\b", text))
    )
    return has_dat_execute or has_table_callback


def _has_ndi(text: str) -> bool:
    return bool(re.search(r"\bndi\b", text))


def _has_post_fx(text: str) -> bool:
    return bool(re.search(r"\bpost[-\s]*(?:fx|effect|effects)\b", text)) or any(
        token in text for token in ("color correction", "color grade", "post process", "post-processing")
    )


def _has_stable_top_output(text: str) -> bool:
    return bool(re.search(r"\bstable\s+top\s+output\b|\btop\s+output\b", text))


def _has_glsl_top_shader(text: str) -> bool:
    is_pop_shader = bool(re.search(r"\bpop\b|\bparticles?\b", text))
    return (
        not is_pop_shader
        and bool(re.search(r"\bglsl\b", text))
        and bool(re.search(r"\bglsl\s+top\b|\btop\s+shader\b|\bfragment\b|\btexture effect\b", text))
    )


def _has_pop_particle_preview(text: str) -> bool:
    has_pop_or_particle = bool(re.search(r"\bpop\b|\bparticles?\b", text))
    has_field = bool(re.search(r"\bfield\b|\bemitter\b|\bparticles?\b", text))
    has_preview = bool(
        re.search(r"\bpreview\b|\brendered\s+top\b|\bstable\s+top\s+output\b|\btop\s+output\b", text)
    )
    return has_pop_or_particle and has_field and has_preview


def _has_glsl_advanced_pop_topology(text: str) -> bool:
    has_glsl_pop = bool(re.search(r"\bglsl\b", text)) and bool(re.search(r"\bpop\b|\bparticles?\b", text))
    changes_topology = bool(
        re.search(
            r"\btopolog(?:y|ies)\b|\bpoint\s+counts?\b|\boutput\s+counts?\b|"
            r"\bprimitive\s+counts?\b|\bvertex\s+counts?\b|\bindex\s+buffers?\b",
            text,
        )
    )
    return has_glsl_pop and changes_topology


def _has_deprecated_glsl_create_pop(text: str) -> bool:
    return bool(re.search(r"\bglsl\s+create\s*pop\b|\bglslcreate\s*pop\b", text))


def _has_sop_terrain(text: str) -> bool:
    return bool(re.search(r"\bterrain\b|\blandscape\b|\bheightfield\b|\bheight[-\s]*field\b", text))


def _has_feedback(text: str) -> bool:
    return any(token in text for token in ("feedback", "trail", "echo", "recursion"))


def _has_render_3d(text: str) -> bool:
    if _has_dat_table_render_switch(text):
        return False
    return any(token in text for token in ("3d", "render", "camera", "geometry", "terrain", "landscape"))


def _has_material(text: str) -> bool:
    return any(token in text for token in ("material", "glass", "surface"))


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
    return (
        _supports_audio_feedback_panel(profiles, capabilities)
        or _supports_audio_terrain_material(profiles, capabilities)
        or _supports_audio_render_material(profiles, capabilities)
        or _supports_midi_control(profiles, capabilities)
        or _supports_serial_dat_protocol(profiles, capabilities)
        or _supports_osc_dat_protocol(profiles, capabilities)
        or _supports_websocket_dat_protocol(profiles, capabilities)
        or _supports_mqtt_dat_protocol(profiles, capabilities)
        or _supports_udp_dat_protocol(profiles, capabilities)
        or _supports_dat_table_render_switch(profiles, capabilities)
        or _supports_dat_execute_callback(profiles, capabilities)
        or _supports_ndi_post_fx(profiles, capabilities)
        or _supports_glsl_top_shader(profiles, capabilities)
        or _supports_pop_particle_preview(profiles, capabilities)
        or _supports_glsl_advanced_pop_topology(profiles, capabilities)
    )


def _supports_audio_feedback_panel(profiles: list[str], capabilities: list[str]) -> bool:
    profile_set = set(profiles)
    capability_set = set(capabilities)
    return {"audio_reactive", "feedback", "panel_ui"}.issubset(profile_set) and {
        "audio_analysis",
        "feedback_loop",
        "panel_controls",
        "debug_output",
    }.issubset(capability_set)


def _supports_audio_render_material(profiles: list[str], capabilities: list[str]) -> bool:
    profile_set = set(profiles)
    capability_set = set(capabilities)
    return {"audio_reactive", "render_pipeline", "glsl_material"}.issubset(profile_set) and {
        "audio_analysis",
        "render_pipeline",
        "material_modulation",
    }.issubset(capability_set)


def _supports_audio_terrain_material(profiles: list[str], capabilities: list[str]) -> bool:
    return _supports_audio_render_material(profiles, capabilities) and "terrain_surface" in set(capabilities)


def _supports_midi_control(profiles: list[str], capabilities: list[str]) -> bool:
    return "midi_control" in set(profiles) and "midi_control" in set(capabilities)


def _supports_serial_dat_protocol(profiles: list[str], capabilities: list[str]) -> bool:
    return "dat_protocol" in set(profiles) and "serial_dat_protocol" in set(capabilities)


def _supports_osc_dat_protocol(profiles: list[str], capabilities: list[str]) -> bool:
    return "dat_protocol" in set(profiles) and "osc_dat_protocol" in set(capabilities)


def _supports_websocket_dat_protocol(profiles: list[str], capabilities: list[str]) -> bool:
    return "dat_protocol" in set(profiles) and "websocket_dat_protocol" in set(capabilities)


def _supports_mqtt_dat_protocol(profiles: list[str], capabilities: list[str]) -> bool:
    return "dat_protocol" in set(profiles) and "mqtt_dat_protocol" in set(capabilities)


def _supports_udp_dat_protocol(profiles: list[str], capabilities: list[str]) -> bool:
    return "dat_protocol" in set(profiles) and "udp_dat_protocol" in set(capabilities)


def _supports_dat_table_render_switch(profiles: list[str], capabilities: list[str]) -> bool:
    return "dat_protocol" in set(profiles) and "dat_table_render_switch" in set(capabilities)


def _supports_dat_execute_callback(profiles: list[str], capabilities: list[str]) -> bool:
    return "dat_protocol" in set(profiles) and "dat_execute_callback" in set(capabilities)


def _supports_ndi_post_fx(profiles: list[str], capabilities: list[str]) -> bool:
    capability_set = set(capabilities)
    return "video_io" in set(profiles) and {"ndi_input", "post_fx_output"}.issubset(capability_set)


def _supports_glsl_top_shader(profiles: list[str], capabilities: list[str]) -> bool:
    capability_set = set(capabilities)
    return "glsl" in set(profiles) and {"glsl_top_shader", "debug_output"}.issubset(capability_set)


def _supports_pop_particle_preview(profiles: list[str], capabilities: list[str]) -> bool:
    capability_set = set(capabilities)
    return "pop" in set(profiles) and {"pop_particle_field_preview", "debug_output"}.issubset(capability_set)


def _supports_glsl_advanced_pop_topology(profiles: list[str], capabilities: list[str]) -> bool:
    profile_set = set(profiles)
    return {"glsl", "pop"}.issubset(profile_set) and "glsl_advanced_pop_topology" in set(capabilities)


def _seed_ops_for_features(profiles: list[str], capabilities: list[str], risk_flags: list[str]) -> list[str]:
    ops: list[str] = []
    if "audio_reactive" in profiles:
        ops.extend(["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"])
    if "render_pipeline" in profiles:
        ops.extend(["geometryCOMP", "cameraCOMP", "renderTOP", "nullTOP"])
    if "glsl_material" in profiles:
        ops.extend(["glslMAT", "textDAT"])
    if "glsl" in profiles:
        ops.extend(["constantTOP", "glslTOP", "textDAT", "nullTOP"])
    if "feedback" in profiles:
        ops.extend(["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"])
    if "panel_ui" in profiles:
        ops.extend(["containerCOMP", "sliderCOMP", "buttonCOMP", "panelCHOP", "nullCHOP"])
    if "pop" in profiles:
        ops.extend(["circlePOP", "noisePOP", "mathmixPOP", "nullPOP", "rendersimpleTOP", "nullTOP"])
    if "glsl_advanced_pop_topology" in capabilities:
        ops.extend(
            [
                "circlePOP",
                "glsladvancedPOP",
                "topologyPOP",
                "textDAT",
                "nullPOP",
                "rendersimpleTOP",
                "nullTOP",
            ]
        )
    if "deprecated-op:glslcreatePOP" in risk_flags:
        ops.append("glslcreatePOP")
    if "terrain_surface" in capabilities:
        ops.extend(["gridSOP", "noiseSOP", "nullSOP"])
    if "midi_control" in profiles:
        ops.extend(["midiinCHOP", "mathCHOP", "nullCHOP"])
    if "serial_dat_protocol" in capabilities:
        ops.extend(["serialDAT", "tableDAT", "nullDAT"])
    if "osc_dat_protocol" in capabilities:
        ops.extend(["oscinDAT", "tableDAT", "nullDAT"])
    if "websocket_dat_protocol" in capabilities:
        ops.extend(["websocketDAT", "tableDAT", "nullDAT"])
    if "mqtt_dat_protocol" in capabilities:
        ops.extend(["mqttclientDAT", "tableDAT", "nullDAT"])
    if "udp_dat_protocol" in capabilities:
        ops.extend(["udpinDAT", "tableDAT", "nullDAT"])
    if "dat_table_render_switch" in capabilities:
        ops.extend(["tableDAT", "constantTOP", "noiseTOP", "switchTOP", "nullTOP"])
    if "dat_execute_callback" in capabilities:
        ops.extend(["datexecuteDAT", "tableDAT", "textDAT", "nullDAT"])
    if "video_io" in profiles and "ndi_input" in capabilities:
        ops.append("ndiinTOP")
    if "post_fx_output" in capabilities:
        ops.extend(["levelTOP", "nullTOP"])
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
