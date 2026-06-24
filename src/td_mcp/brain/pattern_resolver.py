"""Resolve validated BrainPattern records into ranked candidate concept graphs."""

from __future__ import annotations

from collections.abc import Iterable

from td_mcp.brain.operator_availability import load_operator_substitution_rules
from td_mcp.brain.patterns import (
    docs_evidence_for_patterns,
    load_pattern_registry,
    pattern_id_aliases,
    patterns_by_id,
)
from td_mcp.models.brain import (
    BrainPattern,
    CandidateConceptGraph,
    CompiledVisualTaskSpec,
    ConceptEdge,
    OperatorAvailabilityMatrix,
)

_FILE_AUDIO_ROUTE = (
    "audio_file_to_analysis_chop",
    "feedback_decay_top_loop",
    "panel_controls_to_chop_output",
    "debug_output_conventions",
)
_DEVICE_AUDIO_ROUTE = (
    "audio_device_to_analysis_chop",
    "feedback_decay_top_loop",
    "panel_controls_to_chop_output",
    "debug_output_conventions",
)
_FILE_AUDIO_GLSL_MATERIAL_ROUTE = (
    "audio_file_to_analysis_chop",
    "glsl_material_render_pipeline",
    "debug_output_conventions",
)
_DEVICE_AUDIO_GLSL_MATERIAL_ROUTE = (
    "audio_device_to_analysis_chop",
    "glsl_material_render_pipeline",
    "debug_output_conventions",
)
_FILE_AUDIO_GLSL_MATERIAL_PANEL_ROUTE = (
    "audio_file_to_analysis_chop",
    "glsl_material_render_pipeline",
    "panel_controls_to_chop_output",
    "debug_output_conventions",
)
_DEVICE_AUDIO_GLSL_MATERIAL_PANEL_ROUTE = (
    "audio_device_to_analysis_chop",
    "glsl_material_render_pipeline",
    "panel_controls_to_chop_output",
    "debug_output_conventions",
)
_FILE_AUDIO_TERRAIN_GLSL_MATERIAL_ROUTE = (
    "audio_file_to_analysis_chop",
    "sop_noise_terrain_surface",
    "glsl_material_render_pipeline",
    "debug_output_conventions",
)
_DEVICE_AUDIO_TERRAIN_GLSL_MATERIAL_ROUTE = (
    "audio_device_to_analysis_chop",
    "sop_noise_terrain_surface",
    "glsl_material_render_pipeline",
    "debug_output_conventions",
)
_FILE_AUDIO_TERRAIN_GLSL_MATERIAL_PANEL_ROUTE = (
    "audio_file_to_analysis_chop",
    "sop_noise_terrain_surface",
    "glsl_material_render_pipeline",
    "panel_controls_to_chop_output",
    "debug_output_conventions",
)
_DEVICE_AUDIO_TERRAIN_GLSL_MATERIAL_PANEL_ROUTE = (
    "audio_device_to_analysis_chop",
    "sop_noise_terrain_surface",
    "glsl_material_render_pipeline",
    "panel_controls_to_chop_output",
    "debug_output_conventions",
)
_MIDI_CONTROL_ROUTE = ("midi_in_to_control_chop",)
_SERIAL_DAT_PROTOCOL_ROUTE = ("serial_dat_protocol_bridge",)
_OSC_DAT_PROTOCOL_ROUTE = ("osc_in_dat_protocol_bridge",)
_WEBSOCKET_DAT_PROTOCOL_ROUTE = ("websocket_dat_protocol_bridge",)
_MQTT_DAT_PROTOCOL_ROUTE = ("mqtt_client_dat_protocol_bridge",)
_UDP_DAT_PROTOCOL_ROUTE = ("udp_in_dat_protocol_bridge",)
_DAT_TABLE_RENDER_SWITCH_ROUTE = ("dat_table_render_switch_top",)
_DAT_EXECUTE_CALLBACK_ROUTE = ("dat_execute_table_change_callback",)
_NDI_POST_FX_ROUTE = ("ndi_in_to_post_fx_output",)
_POP_PARTICLE_PREVIEW_ROUTE = ("pop_particle_field_preview", "debug_output_conventions")
_GLSL_TOP_SHADER_ROUTE = ("glsl_top_shader_with_text_dat", "debug_output_conventions")
_GLSL_ADVANCED_POP_TOPOLOGY_ROUTE = ("glsl_advanced_pop_topology_shader", "debug_output_conventions")
_PATTERN_REQUIRED_DEVICE_SOURCES = {
    "audio_device_to_analysis_chop": "audio_device",
    "midi_in_to_control_chop": "midi_device",
    "serial_dat_protocol_bridge": "serial_device",
    "osc_in_dat_protocol_bridge": "osc_source",
    "websocket_dat_protocol_bridge": "websocket_endpoint",
    "mqtt_client_dat_protocol_bridge": "mqtt_broker",
    "udp_in_dat_protocol_bridge": "udp_source",
    "ndi_in_to_post_fx_output": "ndi_source",
}
_RUNTIME_PROBE_WEIGHTS = {
    "output_node_present": 0.75,
    "audio_signal_activity": 1.1,
    "feedback_output_readback": 1.4,
    "cheap_visual_metrics": 1.15,
    "compile_state": 1.3,
    "sampler_uniforms": 1.1,
    "pop_output_attached": 1.2,
    "finite_pop_bounds": 1.35,
    "protocol_table_output": 1.05,
    "render_switch_table_present": 1.15,
}
_GENERATED_CODE_CONTRACT_WEIGHT = 1.35


def resolve_candidate_graphs(
    compiled: CompiledVisualTaskSpec,
    *,
    patterns: list[BrainPattern] | None = None,
    available_ops: set[str] | None = None,
    availability_matrix: OperatorAvailabilityMatrix | None = None,
    device_sources: set[str] | None = None,
) -> list[CandidateConceptGraph]:
    """Compose pattern routes into ranked candidates for a compiled task."""
    if compiled.blocked_questions:
        return []

    available_ops = _available_ops_from_matrix(availability_matrix) if availability_matrix else available_ops
    registry = patterns_by_id(patterns or load_pattern_registry())
    candidates: list[CandidateConceptGraph] = []
    for pattern in _promoted_trace_patterns_for_compiled(compiled, registry.values()):
        candidates.append(
            _candidate_from_promoted_trace_pattern(
                compiled,
                pattern,
                available_ops=available_ops,
                availability_matrix=availability_matrix,
                device_sources=device_sources,
            )
        )
    if _supports_phase_one_audio_feedback_panel(compiled):
        for route in (_FILE_AUDIO_ROUTE, _DEVICE_AUDIO_ROUTE):
            selected = [registry[pattern_id] for pattern_id in route if pattern_id in registry]
            if len(selected) != len(route):
                continue
            candidates.append(
                _candidate_from_audio_feedback_panel_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_audio_glsl_material(compiled):
        if _supports_phase_one_audio_glsl_material_terrain(compiled):
            routes = (
                (
                    _FILE_AUDIO_TERRAIN_GLSL_MATERIAL_PANEL_ROUTE,
                    _DEVICE_AUDIO_TERRAIN_GLSL_MATERIAL_PANEL_ROUTE,
                )
                if _supports_phase_one_audio_glsl_material_panel(compiled)
                else (_FILE_AUDIO_TERRAIN_GLSL_MATERIAL_ROUTE, _DEVICE_AUDIO_TERRAIN_GLSL_MATERIAL_ROUTE)
            )
        else:
            routes = (
                (_FILE_AUDIO_GLSL_MATERIAL_PANEL_ROUTE, _DEVICE_AUDIO_GLSL_MATERIAL_PANEL_ROUTE)
                if _supports_phase_one_audio_glsl_material_panel(compiled)
                else (_FILE_AUDIO_GLSL_MATERIAL_ROUTE, _DEVICE_AUDIO_GLSL_MATERIAL_ROUTE)
            )
        for route in routes:
            selected = [registry[pattern_id] for pattern_id in route if pattern_id in registry]
            if len(selected) != len(route):
                continue
            candidates.append(
                _candidate_from_audio_glsl_material_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_midi_control(compiled):
        selected = [registry[pattern_id] for pattern_id in _MIDI_CONTROL_ROUTE if pattern_id in registry]
        if len(selected) == len(_MIDI_CONTROL_ROUTE):
            candidates.append(
                _candidate_from_midi_control_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_serial_dat_protocol(compiled):
        selected = [
            registry[pattern_id] for pattern_id in _SERIAL_DAT_PROTOCOL_ROUTE if pattern_id in registry
        ]
        if len(selected) == len(_SERIAL_DAT_PROTOCOL_ROUTE):
            candidates.append(
                _candidate_from_serial_dat_protocol_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_osc_dat_protocol(compiled):
        selected = [registry[pattern_id] for pattern_id in _OSC_DAT_PROTOCOL_ROUTE if pattern_id in registry]
        if len(selected) == len(_OSC_DAT_PROTOCOL_ROUTE):
            candidates.append(
                _candidate_from_osc_dat_protocol_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_websocket_dat_protocol(compiled):
        selected = [
            registry[pattern_id] for pattern_id in _WEBSOCKET_DAT_PROTOCOL_ROUTE if pattern_id in registry
        ]
        if len(selected) == len(_WEBSOCKET_DAT_PROTOCOL_ROUTE):
            candidates.append(
                _candidate_from_websocket_dat_protocol_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_mqtt_dat_protocol(compiled):
        selected = [registry[pattern_id] for pattern_id in _MQTT_DAT_PROTOCOL_ROUTE if pattern_id in registry]
        if len(selected) == len(_MQTT_DAT_PROTOCOL_ROUTE):
            candidates.append(
                _candidate_from_mqtt_dat_protocol_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_udp_dat_protocol(compiled):
        selected = [registry[pattern_id] for pattern_id in _UDP_DAT_PROTOCOL_ROUTE if pattern_id in registry]
        if len(selected) == len(_UDP_DAT_PROTOCOL_ROUTE):
            candidates.append(
                _candidate_from_udp_dat_protocol_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_dat_table_render_switch(compiled):
        selected = [
            registry[pattern_id] for pattern_id in _DAT_TABLE_RENDER_SWITCH_ROUTE if pattern_id in registry
        ]
        if len(selected) == len(_DAT_TABLE_RENDER_SWITCH_ROUTE):
            candidates.append(
                _candidate_from_dat_table_render_switch_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_dat_execute_callback(compiled):
        selected = [
            registry[pattern_id] for pattern_id in _DAT_EXECUTE_CALLBACK_ROUTE if pattern_id in registry
        ]
        if len(selected) == len(_DAT_EXECUTE_CALLBACK_ROUTE):
            candidates.append(
                _candidate_from_dat_execute_callback_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_ndi_post_fx(compiled):
        selected = [registry[pattern_id] for pattern_id in _NDI_POST_FX_ROUTE if pattern_id in registry]
        if len(selected) == len(_NDI_POST_FX_ROUTE):
            candidates.append(
                _candidate_from_ndi_post_fx_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_glsl_top_shader(compiled):
        selected = [registry[pattern_id] for pattern_id in _GLSL_TOP_SHADER_ROUTE if pattern_id in registry]
        if len(selected) == len(_GLSL_TOP_SHADER_ROUTE):
            candidates.append(
                _candidate_from_glsl_top_shader_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_glsl_advanced_pop_topology(compiled):
        selected = [
            registry[pattern_id] for pattern_id in _GLSL_ADVANCED_POP_TOPOLOGY_ROUTE if pattern_id in registry
        ]
        if len(selected) == len(_GLSL_ADVANCED_POP_TOPOLOGY_ROUTE):
            candidates.append(
                _candidate_from_glsl_advanced_pop_topology_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    if _supports_phase_one_pop_particle_preview(compiled):
        selected = [
            registry[pattern_id] for pattern_id in _POP_PARTICLE_PREVIEW_ROUTE if pattern_id in registry
        ]
        if len(selected) == len(_POP_PARTICLE_PREVIEW_ROUTE):
            candidates.append(
                _candidate_from_pop_particle_preview_patterns(
                    compiled,
                    selected,
                    available_ops=available_ops,
                    availability_matrix=availability_matrix,
                    device_sources=device_sources,
                )
            )
    candidates = _with_unsubstituted_operator_alternatives(candidates, availability_matrix)
    candidates = _with_runtime_validation_explanations(candidates, registry)
    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return candidates


def _supports_phase_one_audio_feedback_panel(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return {"audio_reactive", "feedback", "panel_ui"}.issubset(profiles) and {
        "audio_analysis",
        "feedback_loop",
        "panel_controls",
        "debug_output",
    }.issubset(capabilities)


def _supports_phase_one_audio_glsl_material(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return {"audio_reactive", "render_pipeline", "glsl_material"}.issubset(profiles) and {
        "audio_analysis",
        "render_pipeline",
        "material_modulation",
    }.issubset(capabilities)


def _supports_phase_one_audio_glsl_material_panel(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "panel_ui" in profiles and "panel_controls" in capabilities


def _supports_phase_one_audio_glsl_material_terrain(compiled: CompiledVisualTaskSpec) -> bool:
    capabilities = set(compiled.required_capabilities)
    return "terrain_surface" in capabilities


def _supports_phase_one_midi_control(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "midi_control" in profiles and "midi_control" in capabilities


def _supports_phase_one_serial_dat_protocol(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "dat_protocol" in profiles and "serial_dat_protocol" in capabilities


def _supports_phase_one_osc_dat_protocol(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "dat_protocol" in profiles and "osc_dat_protocol" in capabilities


def _supports_phase_one_websocket_dat_protocol(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "dat_protocol" in profiles and "websocket_dat_protocol" in capabilities


def _supports_phase_one_mqtt_dat_protocol(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "dat_protocol" in profiles and "mqtt_dat_protocol" in capabilities


def _supports_phase_one_udp_dat_protocol(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "dat_protocol" in profiles and "udp_dat_protocol" in capabilities


def _supports_phase_one_dat_table_render_switch(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "dat_protocol" in profiles and "dat_table_render_switch" in capabilities


def _supports_phase_one_dat_execute_callback(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "dat_protocol" in profiles and "dat_execute_callback" in capabilities


def _supports_phase_one_ndi_post_fx(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "video_io" in profiles and {"ndi_input", "post_fx_output"}.issubset(capabilities)


def _supports_phase_one_glsl_top_shader(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "glsl" in profiles and {"glsl_top_shader", "debug_output"}.issubset(capabilities)


def _supports_phase_one_glsl_advanced_pop_topology(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return {"glsl", "pop"}.issubset(profiles) and {"glsl_advanced_pop_topology", "debug_output"}.issubset(
        capabilities
    )


def _supports_phase_one_pop_particle_preview(compiled: CompiledVisualTaskSpec) -> bool:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    return "pop" in profiles and {"pop_particle_field_preview", "debug_output"}.issubset(capabilities)


def _promoted_trace_patterns_for_compiled(
    compiled: CompiledVisualTaskSpec,
    patterns: Iterable[BrainPattern],
) -> list[BrainPattern]:
    profiles = set(compiled.candidate_profiles)
    capabilities = set(compiled.required_capabilities)
    promoted: list[BrainPattern] = []
    for pattern in patterns:
        if not pattern.promoted_from_trace:
            continue
        pattern_profiles = set(pattern.profiles)
        if pattern_profiles and not pattern_profiles.issubset(profiles):
            continue
        pattern_tags = set(pattern.intent_tags)
        if capabilities and not capabilities.issubset(pattern_tags):
            continue
        promoted.append(pattern)
    return promoted


def _candidate_from_promoted_trace_pattern(
    compiled: CompiledVisualTaskSpec,
    pattern: BrainPattern,
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    required_ops = sorted(set(pattern.required_ops))
    optional_ops = sorted(set(pattern.optional_ops))
    risk_flags, score = _score_candidate(
        [pattern],
        required_ops,
        [*compiled.risk_flags, *pattern.rollback_risks],
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    support_count = _trace_support_count(pattern)
    runtime_validation_count = _trace_runtime_validation_count(pattern)
    trace_fingerprint = _trace_fingerprint(pattern)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{pattern.pattern_id}",
        compiled_task_id=compiled.id,
        label=pattern.title,
        profiles=list(pattern.profiles),
        pattern_ids=[pattern.pattern_id],
        concepts=list(pattern.concept_nodes),
        edges=list(pattern.concept_edges),
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys([*compiled.validation_needs, *pattern.validation_probes])),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *docs_evidence_for_patterns([pattern]),
                    *_availability_evidence(availability_matrix, [pattern]),
                    *_runtime_validation_evidence([pattern]),
                ]
            )
        ),
        score=score,
        explanation=(
            f"profiles:{'+'.join(pattern.profiles)}; "
            f"promoted_trace:{pattern.promoted_from_trace}; "
            f"trace_support:{support_count}; "
            f"runtime_validation:{runtime_validation_count}; "
            f"trace_fingerprint:{trace_fingerprint}; "
            f"required_ops:{','.join(required_ops)}"
        ),
    )


def _candidate_from_audio_feedback_panel_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    audio_out = _exposed_node(patterns[0], "analysis_chop")
    panel_out = _exposed_node(_pattern_with_id(patterns, "panel_controls_to_chop_output"), "panel_chop")
    stable_top = _exposed_node(_pattern_with_id(patterns, "feedback_decay_top_loop"), "stable_top")
    feedback_target = _consumed_target(_pattern_with_id(patterns, "feedback_decay_top_loop"), "analysis_chop")
    debug_target = _exposed_node(_pattern_with_id(patterns, "debug_output_conventions"), "debug_dat")
    if audio_out and feedback_target:
        edges.append(ConceptEdge(source=audio_out, target=feedback_target, kind="control"))
    if panel_out and feedback_target:
        edges.append(ConceptEdge(source=panel_out, target=feedback_target, kind="control"))
    if stable_top and debug_target:
        edges.append(ConceptEdge(source=stable_top, target=debug_target, kind="reference"))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )

    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    device_source_evidence = _device_source_evidence(patterns, device_sources)
    substitution_evidence, score = _substitution_evidence_and_score(
        patterns,
        score,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label=_candidate_label(patterns),
        profiles=["audio_reactive", "feedback", "panel_ui"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *substitution_evidence,
                    *device_source_evidence,
                ]
            )
        ),
        score=score,
        explanation=(
            "profiles:audio_reactive+feedback+panel_ui; "
            f"patterns:{route_label}; required_ops:{','.join(required_ops)}"
        ),
    )


def _candidate_from_audio_glsl_material_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    audio_out = _exposed_node(patterns[0], "analysis_chop")
    material_pattern = _pattern_with_id(patterns, "glsl_material_render_pipeline")
    material_target = _consumed_target(material_pattern, "analysis_chop")
    terrain_target = _consumed_target(material_pattern, "terrain_sop")
    panel_pattern = _pattern_with_id(patterns, "panel_controls_to_chop_output")
    panel_out = _exposed_node(panel_pattern, "panel_chop")
    terrain_pattern = _pattern_with_id(patterns, "sop_noise_terrain_surface")
    terrain_out = _exposed_node(terrain_pattern, "terrain_sop")
    stable_top = _exposed_node(material_pattern, "stable_top")
    debug_target = _exposed_node(_pattern_with_id(patterns, "debug_output_conventions"), "debug_dat")
    if audio_out and material_target:
        edges.append(ConceptEdge(source=audio_out, target=material_target, kind="control"))
    if terrain_out and terrain_target:
        edges.append(ConceptEdge(source=terrain_out, target=terrain_target, kind="reference"))
        concepts = _with_concept_param(concepts, terrain_target, "sop", f"${{path:{terrain_out}}}")
    if panel_out and material_target:
        edges.append(ConceptEdge(source=panel_out, target=material_target, kind="control"))
    if stable_top and debug_target:
        edges.append(ConceptEdge(source=stable_top, target=debug_target, kind="reference"))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )

    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    substitution_evidence, score = _substitution_evidence_and_score(
        patterns,
        score,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    profiles = ["audio_reactive", "render_pipeline", "glsl_material"]
    if any(pattern.pattern_id == "panel_controls_to_chop_output" for pattern in patterns):
        profiles.append("panel_ui")
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label=_candidate_label(patterns),
        profiles=profiles,
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *substitution_evidence,
                ]
            )
        ),
        score=score,
        explanation=(
            f"profiles:{'+'.join(profiles)}; patterns:{route_label}; required_ops:{','.join(required_ops)}"
        ),
    )


def _candidate_from_midi_control_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    device_source_evidence = _device_source_evidence(patterns, device_sources)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="MIDI control bridge to bounded CHOP output",
        profiles=["midi_control"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *device_source_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:midi_control; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_serial_dat_protocol_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    device_source_evidence = _device_source_evidence(patterns, device_sources)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="Serial DAT protocol bridge with stable diagnostics",
        profiles=["dat_protocol"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *device_source_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:dat_protocol; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_osc_dat_protocol_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    device_source_evidence = _device_source_evidence(patterns, device_sources)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="OSC DAT protocol bridge with stable diagnostics",
        profiles=["dat_protocol"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *device_source_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:dat_protocol; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_websocket_dat_protocol_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    device_source_evidence = _device_source_evidence(patterns, device_sources)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="WebSocket DAT protocol bridge with stable diagnostics",
        profiles=["dat_protocol"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *device_source_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:dat_protocol; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_mqtt_dat_protocol_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    device_source_evidence = _device_source_evidence(patterns, device_sources)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="MQTT Client DAT protocol bridge with stable diagnostics",
        profiles=["dat_protocol"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *device_source_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:dat_protocol; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_udp_dat_protocol_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    device_source_evidence = _device_source_evidence(patterns, device_sources)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="UDP In DAT protocol bridge with stable diagnostics",
        profiles=["dat_protocol"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *device_source_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:dat_protocol; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_dat_table_render_switch_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="DAT table render switch with stable TOP output",
        profiles=["dat_protocol"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:dat_protocol; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_dat_execute_callback_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    device_source_evidence = _device_source_evidence(patterns, device_sources)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="DAT Execute table-change callback with stable diagnostics",
        profiles=["dat_protocol"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:dat_protocol; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_ndi_post_fx_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    device_source_evidence = _device_source_evidence(patterns, device_sources)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="NDI input with post-FX stable TOP output",
        profiles=["video_io"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *device_source_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:video_io; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_pop_particle_preview_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    pop_pattern = _pattern_with_id(patterns, "pop_particle_field_preview")
    debug_pattern = _pattern_with_id(patterns, "debug_output_conventions")
    stable_top = _exposed_node(pop_pattern, "stable_top")
    debug_target = _exposed_node(debug_pattern, "debug_dat")
    if stable_top and debug_target:
        edges.append(ConceptEdge(source=stable_top, target=debug_target, kind="reference"))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="POP particle field preview with stable TOP and debug output",
        profiles=["pop"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:pop; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_glsl_top_shader_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    shader_pattern = _pattern_with_id(patterns, "glsl_top_shader_with_text_dat")
    debug_pattern = _pattern_with_id(patterns, "debug_output_conventions")
    stable_top = _exposed_node(shader_pattern, "stable_top")
    debug_target = _exposed_node(debug_pattern, "debug_dat")
    if stable_top and debug_target:
        edges.append(ConceptEdge(source=stable_top, target=debug_target, kind="reference"))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="GLSL TOP shader with source DAT and debug output",
        profiles=["glsl"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:glsl; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _candidate_from_glsl_advanced_pop_topology_patterns(
    compiled: CompiledVisualTaskSpec,
    patterns: list[BrainPattern],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> CandidateConceptGraph:
    concepts = []
    edges = []
    required_ops: list[str] = []
    optional_ops: list[str] = []
    validation_needs: list[str] = list(compiled.validation_needs)
    risk_flags: list[str] = list(compiled.risk_flags)
    pattern_ids: list[str] = []

    for pattern in patterns:
        concepts.extend(pattern.concept_nodes)
        edges.extend(pattern.concept_edges)
        required_ops.extend(pattern.required_ops)
        optional_ops.extend(pattern.optional_ops)
        validation_needs.extend(pattern.validation_probes)
        risk_flags.extend(pattern.rollback_risks)
        pattern_ids.append(pattern.pattern_id)
        pattern_ids.extend(pattern_id_aliases(pattern.pattern_id))

    shader_pattern = _pattern_with_id(patterns, "glsl_advanced_pop_topology_shader")
    debug_pattern = _pattern_with_id(patterns, "debug_output_conventions")
    stable_top = _exposed_node(shader_pattern, "stable_top")
    debug_target = _exposed_node(debug_pattern, "debug_dat")
    if stable_top and debug_target:
        edges.append(ConceptEdge(source=stable_top, target=debug_target, kind="reference"))

    required_ops = sorted(set(required_ops))
    optional_ops = sorted(set(optional_ops))
    concepts, required_ops, operator_substitution_evidence = _apply_available_operator_substitutions(
        concepts, required_ops, availability_matrix
    )
    risk_flags, score = _score_candidate(
        patterns,
        required_ops,
        risk_flags,
        available_ops=available_ops,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
    )
    pattern_evidence = docs_evidence_for_patterns(patterns)
    availability_evidence = _availability_evidence(availability_matrix, patterns)
    substitution_evidence, score = _substitution_evidence_and_score(
        patterns,
        score,
        availability_matrix=availability_matrix,
        device_sources=device_sources,
        compiled=compiled,
    )
    route_label = "+".join(pattern.pattern_id for pattern in patterns)
    return CandidateConceptGraph(
        id=f"candidate:{compiled.id}:{route_label}",
        compiled_task_id=compiled.id,
        label="GLSL Advanced POP topology shader with stable preview and debug output",
        profiles=["glsl", "pop"],
        pattern_ids=list(dict.fromkeys(pattern_ids)),
        concepts=concepts,
        edges=edges,
        required_ops=required_ops,
        optional_ops=optional_ops,
        expected_outputs=[item.get("path") or item["kind"] for item in compiled.outputs if item.get("kind")],
        validation_needs=list(dict.fromkeys(validation_needs)),
        risk_flags=list(dict.fromkeys(risk_flags)),
        grounding_evidence=list(
            dict.fromkeys(
                [
                    *compiled.grounding_evidence,
                    *pattern_evidence,
                    *availability_evidence,
                    *operator_substitution_evidence,
                    *substitution_evidence,
                ]
            )
        ),
        score=score,
        explanation=f"profiles:glsl+pop; patterns:{route_label}; required_ops:{','.join(required_ops)}",
    )


def _apply_available_operator_substitutions(
    concepts: list,
    required_ops: list[str],
    availability_matrix: OperatorAvailabilityMatrix | None,
) -> tuple[list, list[str], list[str]]:
    if availability_matrix is None:
        return concepts, sorted(set(required_ops)), []

    replacements: dict[str, str] = {}
    evidence: list[str] = []
    substituted_required_ops: list[str] = []

    for op_type in required_ops:
        rule = _available_direct_substitution_rule(op_type, availability_matrix)
        if rule is None:
            substituted_required_ops.append(op_type)
            continue

        replacement_op = rule.replacement_ops[0]
        replacements[op_type] = replacement_op
        substituted_required_ops.append(replacement_op)
        evidence.extend(
            [
                f"substitution:{op_type}->{replacement_op}",
                f"substitution-rule:{op_type}->{replacement_op}:{rule.confidence}",
                f"docs:{replacement_op}",
            ]
        )

    if not replacements:
        return concepts, sorted(set(substituted_required_ops)), []

    substituted_concepts = []
    for concept in concepts:
        replacement_op = replacements.get(concept.op_type)
        if replacement_op is None:
            substituted_concepts.append(concept)
            continue

        concept_evidence = list(
            dict.fromkeys(
                [
                    *concept.evidence,
                    f"substitution:{concept.op_type}->{replacement_op}",
                    f"docs:{replacement_op}",
                ]
            )
        )
        updates = {"op_type": replacement_op, "evidence": concept_evidence}
        if concept.create_type == concept.op_type:
            updates["create_type"] = replacement_op
        substituted_concepts.append(concept.model_copy(update=updates))

    return substituted_concepts, sorted(set(substituted_required_ops)), list(dict.fromkeys(evidence))


def _available_direct_substitution_rule(
    missing_op: str,
    availability_matrix: OperatorAvailabilityMatrix,
):
    for rule in load_operator_substitution_rules():
        if rule.missing_op != missing_op:
            continue
        if rule.replacement_pattern is not None or len(rule.replacement_ops) != 1:
            continue
        if rule.requires_user_approval:
            continue
        if availability_matrix.operators.get(rule.missing_op, {}).get("available") is not False:
            continue
        if not all(
            availability_matrix.operators.get(op_type, {}).get("available") is True
            for op_type in rule.replacement_ops
        ):
            continue
        return rule
    return None


def _with_unsubstituted_operator_alternatives(
    candidates: list[CandidateConceptGraph],
    availability_matrix: OperatorAvailabilityMatrix | None,
) -> list[CandidateConceptGraph]:
    if availability_matrix is None:
        return candidates

    expanded: list[CandidateConceptGraph] = []
    for candidate in candidates:
        expanded.append(candidate)
        substitutions = _direct_substitutions_from_candidate(candidate)
        if not substitutions:
            continue

        original_required_ops = _restore_required_ops(candidate.required_ops, substitutions)
        original_concepts = [
            _restore_substituted_concept(concept, substitutions) for concept in candidate.concepts
        ]
        original_risk_flags = list(
            dict.fromkeys(
                [*candidate.risk_flags, *[f"missing-op:{missing}" for missing, _replacement in substitutions]]
            )
        )
        original_evidence = _without_direct_substitution_evidence(candidate.grounding_evidence, substitutions)
        original_score = max(0.0, round(candidate.score - min(0.5, 0.12 * len(substitutions)), 3))

        expanded.append(
            candidate.model_copy(
                update={
                    "id": f"{candidate.id}:unsubstituted",
                    "concepts": original_concepts,
                    "required_ops": original_required_ops,
                    "risk_flags": original_risk_flags,
                    "grounding_evidence": original_evidence,
                    "score": original_score,
                    "explanation": f"{candidate.explanation}; unsubstituted_ops:{','.join(missing for missing, _ in substitutions)}",
                }
            )
        )
    return expanded


def _direct_substitutions_from_candidate(candidate: CandidateConceptGraph) -> list[tuple[str, str]]:
    substitutions: list[tuple[str, str]] = []
    for item in candidate.grounding_evidence:
        if not item.startswith("substitution:") or "->" not in item:
            continue
        missing_op, replacement_op = item.removeprefix("substitution:").split("->", 1)
        rule = _direct_substitution_rule_for(missing_op=missing_op, replacement_op=replacement_op)
        if rule is not None:
            substitutions.append((missing_op, replacement_op))
    return list(dict.fromkeys(substitutions))


def _direct_substitution_rule_for(*, missing_op: str, replacement_op: str):
    for rule in load_operator_substitution_rules():
        if rule.missing_op != missing_op:
            continue
        if rule.replacement_pattern is None and rule.replacement_ops == [replacement_op]:
            return rule
    return None


def _restore_required_ops(required_ops: list[str], substitutions: list[tuple[str, str]]) -> list[str]:
    restored = list(required_ops)
    for missing_op, replacement_op in substitutions:
        restored = [missing_op if op_type == replacement_op else op_type for op_type in restored]
    return sorted(set(restored))


def _restore_substituted_concept(concept, substitutions: list[tuple[str, str]]):
    for missing_op, replacement_op in substitutions:
        if concept.op_type != replacement_op:
            continue
        marker = f"substitution:{missing_op}->{replacement_op}"
        if marker not in concept.evidence:
            continue
        evidence = [item for item in concept.evidence if item not in {marker, f"docs:{replacement_op}"}]
        updates = {"op_type": missing_op, "evidence": evidence}
        if concept.create_type == replacement_op:
            updates["create_type"] = missing_op
        return concept.model_copy(update=updates)
    return concept


def _without_direct_substitution_evidence(
    evidence: list[str],
    substitutions: list[tuple[str, str]],
) -> list[str]:
    remove = set()
    for missing_op, replacement_op in substitutions:
        remove.add(f"substitution:{missing_op}->{replacement_op}")
        remove.add(f"docs:{replacement_op}")
        for item in evidence:
            if item.startswith(f"substitution-rule:{missing_op}->{replacement_op}:"):
                remove.add(item)
    return [item for item in evidence if item not in remove]


def _score_candidate(
    patterns: list[BrainPattern],
    required_ops: list[str],
    risk_flags: list[str],
    *,
    available_ops: set[str] | None,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
) -> tuple[list[str], float]:
    score = 0.95
    if any(pattern.safety == "device_dependent" for pattern in patterns):
        score -= 0.03
        missing_sources = _missing_required_device_sources(patterns, device_sources)
        if missing_sources:
            risk_flags.append("device-source-required")
            score -= 0.25
    if available_ops is not None:
        missing_ops = sorted(op_type for op_type in required_ops if op_type not in available_ops)
        for op_type in missing_ops:
            risk_flags.append(f"missing-op:{op_type}")
        score -= min(0.5, 0.12 * len(missing_ops))
    if availability_matrix is not None:
        missing_addons = _missing_required_addons(patterns, availability_matrix)
        for addon in missing_addons:
            risk_flags.append(f"missing-addon:{addon}")
        score -= min(0.3, 0.15 * len(missing_addons))
    promoted_trace_count = sum(1 for pattern in patterns if pattern.promoted_from_trace)
    runtime_validation_penalty = 0.0
    if promoted_trace_count:
        support_count = sum(
            max(1, _trace_support_count(pattern)) for pattern in patterns if pattern.promoted_from_trace
        )
        runtime_validation_count = sum(_trace_runtime_validation_count(pattern) for pattern in patterns)
        runtime_validation_score = sum(_trace_runtime_validation_score(pattern) for pattern in patterns)
        missing_runtime_probe_count = sum(
            len(_trace_runtime_validation_missing_probe_ids(pattern)) for pattern in patterns
        )
        failed_runtime_probe_count = sum(
            len(_trace_runtime_validation_failed_probe_ids(pattern)) for pattern in patterns
        )
        failed_required_runtime_probe_count = sum(
            len(_trace_runtime_validation_failed_required_probe_ids(pattern)) for pattern in patterns
        )
        if missing_runtime_probe_count:
            risk_flags.append("runtime-validation-missing")
        if failed_runtime_probe_count:
            risk_flags.append("runtime-validation-failed")
        if failed_required_runtime_probe_count:
            risk_flags.append("runtime-validation-failed-required")
        score += min(
            0.24,
            0.06 * promoted_trace_count
            + 0.02 * max(0, support_count - promoted_trace_count)
            + 0.012 * runtime_validation_count
            + 0.018 * runtime_validation_score,
        )
        if missing_runtime_probe_count:
            runtime_validation_penalty += min(0.24, 0.06 * missing_runtime_probe_count)
        if failed_runtime_probe_count:
            runtime_validation_penalty += min(
                0.45,
                0.16 * failed_runtime_probe_count + 0.08 * failed_required_runtime_probe_count,
            )
    # Clamp to 1.0 BEFORE subtracting the runtime penalty — this is deliberate.
    # It guarantees a missing/failed-probe penalty is always visible in the final
    # score (subtracted from a capped 1.0) rather than being absorbed by a large
    # trace-support bonus, so a high-support-but-failed candidate ranks below a
    # clean one. See test_pattern_resolver_does_not_let_support_hide_failed_runtime_probes.
    score = min(1.0, score) - runtime_validation_penalty
    return list(dict.fromkeys(risk_flags)), max(0.0, round(score, 3))


def _trace_support_count(pattern: BrainPattern) -> int:
    layout = pattern.layout if isinstance(pattern.layout, dict) else {}
    raw = layout.get("trace_support_count")
    if isinstance(raw, int) and raw > 0:
        return raw
    support_trace_ids = layout.get("support_trace_ids")
    if isinstance(support_trace_ids, list):
        return len([item for item in support_trace_ids if str(item).strip()])
    return 1 if pattern.promoted_from_trace else 0


def _trace_runtime_validation_count(pattern: BrainPattern) -> int:
    layout = pattern.layout if isinstance(pattern.layout, dict) else {}
    runtime = layout.get("runtime_validation")
    if not isinstance(runtime, dict):
        return 0
    passed_probe_ids = runtime.get("passed_probe_ids")
    passed_contract_ids = runtime.get("generated_code_passed_contract_ids")
    count = 0
    if isinstance(passed_probe_ids, list):
        count += len([item for item in passed_probe_ids if str(item).strip()])
    if isinstance(passed_contract_ids, list):
        count += len([item for item in passed_contract_ids if str(item).strip()])
    return count


def _trace_runtime_validation_score(pattern: BrainPattern) -> float:
    runtime = _runtime_validation_payload(pattern)
    if not runtime:
        return 0.0
    raw_score = 0.0
    for _probe_id, weight in _runtime_validation_probe_weights(runtime):
        raw_score += weight
    passed_contract_ids = runtime.get("generated_code_passed_contract_ids")
    if isinstance(passed_contract_ids, list):
        raw_score += _GENERATED_CODE_CONTRACT_WEIGHT * len(
            [item for item in passed_contract_ids if str(item).strip()]
        )
    return round(raw_score * _runtime_validation_decay(runtime), 4)


def _trace_runtime_validation_missing_probe_ids(pattern: BrainPattern) -> list[str]:
    runtime = _runtime_validation_payload(pattern)
    if not runtime:
        return []
    explicit_missing = _runtime_string_list(runtime.get("missing_probe_ids"))
    required = _runtime_string_list(runtime.get("required_probe_ids"))
    passed = set(_runtime_string_list(runtime.get("passed_probe_ids")))
    derived_missing = [probe_id for probe_id in required if probe_id not in passed]
    return list(dict.fromkeys([*explicit_missing, *derived_missing]))


def _trace_runtime_validation_failed_probe_ids(pattern: BrainPattern) -> list[str]:
    runtime = _runtime_validation_payload(pattern)
    if not runtime:
        return []
    return _runtime_string_list(runtime.get("failed_probe_ids"))


def _trace_runtime_validation_failed_required_probe_ids(pattern: BrainPattern) -> list[str]:
    runtime = _runtime_validation_payload(pattern)
    if not runtime:
        return []
    required = set(_runtime_string_list(runtime.get("required_probe_ids")))
    if not required:
        return []
    return [
        probe_id for probe_id in _trace_runtime_validation_failed_probe_ids(pattern) if probe_id in required
    ]


def _trace_runtime_validation_failed_probe_status(runtime: dict, probe_id: str) -> str:
    statuses = runtime.get("failed_probe_statuses")
    if isinstance(statuses, dict):
        status = str(statuses.get(probe_id) or "").strip()
        if status:
            return status
    return "runtime_fail"


def _trace_runtime_validation_failed_probe_detail(runtime: dict, probe_id: str) -> dict[str, object]:
    details = runtime.get("failed_probe_details")
    if not isinstance(details, dict):
        return {}
    detail = details.get(probe_id)
    return detail if isinstance(detail, dict) else {}


def _trace_runtime_validation_missing_probe_detail(runtime: dict, probe_id: str) -> dict[str, object]:
    details = runtime.get("missing_probe_details")
    if not isinstance(details, dict):
        return {}
    detail = details.get(probe_id)
    return detail if isinstance(detail, dict) else {}


def _runtime_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := str(item).strip())]


def _with_runtime_validation_explanations(
    candidates: list[CandidateConceptGraph],
    registry: dict[str, BrainPattern],
) -> list[CandidateConceptGraph]:
    updated: list[CandidateConceptGraph] = []
    for candidate in candidates:
        runtime_patterns = [
            registry[pattern_id] for pattern_id in candidate.pattern_ids if pattern_id in registry
        ]
        runtime_count = sum(_trace_runtime_validation_count(pattern) for pattern in runtime_patterns)
        runtime_score = sum(_trace_runtime_validation_score(pattern) for pattern in runtime_patterns)
        missing_count = sum(
            len(_trace_runtime_validation_missing_probe_ids(pattern)) for pattern in runtime_patterns
        )
        failed_count = sum(
            len(_trace_runtime_validation_failed_probe_ids(pattern)) for pattern in runtime_patterns
        )
        failed_required_count = sum(
            len(_trace_runtime_validation_failed_required_probe_ids(pattern)) for pattern in runtime_patterns
        )
        marker = f"runtime_validation:{runtime_count}"
        score_marker = f"runtime_validation_score:{runtime_score:.4f}"
        missing_marker = f"runtime_validation_missing:{missing_count}"
        failed_marker = f"runtime_validation_failed:{failed_count}"
        failed_required_marker = f"runtime_validation_failed_required:{failed_required_count}"
        grounding_evidence = list(
            dict.fromkeys([*candidate.grounding_evidence, *_runtime_validation_evidence(runtime_patterns)])
        )
        updates = {}
        if grounding_evidence != candidate.grounding_evidence:
            updates["grounding_evidence"] = grounding_evidence
        if runtime_count and marker not in candidate.explanation:
            updates["explanation"] = f"{candidate.explanation}; {marker}"
        if runtime_score and score_marker not in updates.get("explanation", candidate.explanation):
            explanation = updates.get("explanation", candidate.explanation)
            updates["explanation"] = f"{explanation}; {score_marker}"
        if missing_count and missing_marker not in updates.get("explanation", candidate.explanation):
            explanation = updates.get("explanation", candidate.explanation)
            updates["explanation"] = f"{explanation}; {missing_marker}"
        if failed_count and failed_marker not in updates.get("explanation", candidate.explanation):
            explanation = updates.get("explanation", candidate.explanation)
            updates["explanation"] = f"{explanation}; {failed_marker}"
        if failed_required_count and failed_required_marker not in updates.get(
            "explanation", candidate.explanation
        ):
            explanation = updates.get("explanation", candidate.explanation)
            updates["explanation"] = f"{explanation}; {failed_required_marker}"
        if updates:
            updated.append(candidate.model_copy(update=updates))
        else:
            updated.append(candidate)
    return updated


def _runtime_validation_evidence(patterns: list[BrainPattern]) -> list[str]:
    evidence: list[str] = []
    for pattern in patterns:
        count = _trace_runtime_validation_count(pattern)
        missing_probe_ids = _trace_runtime_validation_missing_probe_ids(pattern)
        failed_probe_ids = _trace_runtime_validation_failed_probe_ids(pattern)
        failed_required_probe_ids = _trace_runtime_validation_failed_required_probe_ids(pattern)
        if count <= 0 and not missing_probe_ids and not failed_probe_ids:
            continue
        runtime = _runtime_validation_payload(pattern)
        if count > 0:
            evidence.append(f"runtime-validation:{pattern.pattern_id}:{count}")
        for probe_id, weight in _runtime_validation_probe_weights(runtime):
            evidence.append(f"runtime-validation-probe:{pattern.pattern_id}:{probe_id}:{weight:.4f}")
        for probe_id in missing_probe_ids:
            evidence.append(f"runtime-validation-missing:{pattern.pattern_id}:{probe_id}")
            detail = _trace_runtime_validation_missing_probe_detail(runtime, probe_id)
            readback_strategy = str(detail.get("readback_strategy") or "").strip()
            if readback_strategy:
                evidence.append(
                    f"runtime-validation-missing-detail:{pattern.pattern_id}:{probe_id}:{readback_strategy}"
                )
            status = str(detail.get("status") or "").strip()
            if status:
                evidence.append(f"runtime-validation-missing-status:{pattern.pattern_id}:{probe_id}:{status}")
            issue_code = str(detail.get("issue_code") or "").strip()
            if issue_code:
                evidence.append(
                    f"runtime-validation-missing-issue:{pattern.pattern_id}:{probe_id}:{issue_code}"
                )
        for probe_id in failed_probe_ids:
            status = _trace_runtime_validation_failed_probe_status(runtime, probe_id)
            evidence.append(f"runtime-validation-failed:{pattern.pattern_id}:{probe_id}:{status}")
            detail = _trace_runtime_validation_failed_probe_detail(runtime, probe_id)
            issue_code = str(detail.get("issue_code") or "").strip()
            if issue_code:
                evidence.append(
                    f"runtime-validation-failed-detail:{pattern.pattern_id}:{probe_id}:{issue_code}"
                )
        for probe_id in failed_required_probe_ids:
            evidence.append(f"runtime-validation-failed-required:{pattern.pattern_id}:{probe_id}")
        decay = _runtime_validation_decay(runtime)
        if decay != 1.0:
            evidence.append(f"runtime-validation-decay:{pattern.pattern_id}:{decay:.4f}")
        score = _trace_runtime_validation_score(pattern)
        if score:
            evidence.append(f"runtime-validation-score:{pattern.pattern_id}:{score:.4f}")
        replay = runtime.get("aggregated_replay_validation")
        if isinstance(replay, dict):
            for field, label in (
                ("missing_probe_counts", "missing"),
                ("failed_probe_counts", "failed"),
                ("failed_required_probe_counts", "failed-required"),
                ("failed_optional_probe_counts", "failed-optional"),
            ):
                counts = replay.get(field)
                if not isinstance(counts, dict):
                    continue
                for probe_id, count in counts.items():
                    if isinstance(count, bool) or not isinstance(count, int | float):
                        continue
                    evidence.append(
                        "runtime-validation-replay-aggregate:"
                        f"{pattern.pattern_id}:{label}:{probe_id}:{int(count)}"
                    )
        fingerprint = _trace_fingerprint(pattern)
        if fingerprint:
            evidence.append(f"trace-fingerprint:{pattern.pattern_id}:{fingerprint}")
    return evidence


def _runtime_validation_payload(pattern: BrainPattern) -> dict:
    layout = pattern.layout if isinstance(pattern.layout, dict) else {}
    runtime = layout.get("runtime_validation")
    return runtime if isinstance(runtime, dict) else {}


def _runtime_validation_probe_weights(runtime: dict) -> list[tuple[str, float]]:
    passed_probe_ids = runtime.get("passed_probe_ids")
    if not isinstance(passed_probe_ids, list):
        return []
    explicit_weights = runtime.get("passed_probe_weights")
    explicit = explicit_weights if isinstance(explicit_weights, dict) else {}
    weighted: list[tuple[str, float]] = []
    for raw_probe_id in passed_probe_ids:
        probe_id = str(raw_probe_id).strip()
        if not probe_id:
            continue
        raw_weight = explicit.get(probe_id, _RUNTIME_PROBE_WEIGHTS.get(probe_id, 1.0))
        weight = raw_weight if isinstance(raw_weight, int | float) else 1.0
        weighted.append((probe_id, max(0.0, min(4.0, float(weight)))))
    return weighted


def _runtime_validation_decay(runtime: dict) -> float:
    raw = runtime.get("confidence_decay", runtime.get("validation_decay", 1.0))
    if not isinstance(raw, int | float):
        return 1.0
    return max(0.0, min(1.0, float(raw)))


def _trace_fingerprint(pattern: BrainPattern) -> str:
    layout = pattern.layout if isinstance(pattern.layout, dict) else {}
    return str(layout.get("trace_fingerprint") or "")


def _available_ops_from_matrix(matrix: OperatorAvailabilityMatrix) -> set[str]:
    return {op_type for op_type, data in matrix.operators.items() if data.get("available") is True}


def _availability_evidence(
    matrix: OperatorAvailabilityMatrix | None,
    patterns: list[BrainPattern] | None = None,
) -> list[str]:
    if matrix is None:
        return []
    evidence = [f"availability:td_build:{matrix.td_build}", f"availability:platform:{matrix.platform}"]
    evidence.extend(f"availability:addon:{addon}" for addon in matrix.installed_addons)
    if patterns:
        installed_addons = set(matrix.installed_addons)
        for addon in _required_addons(patterns):
            evidence.append(f"addon-required:{addon}")
            status = "addon-installed" if addon in installed_addons else "addon-missing"
            evidence.append(f"{status}:{addon}")
    return evidence


def _device_source_evidence(
    patterns: list[BrainPattern],
    device_sources: set[str] | None,
) -> list[str]:
    declared = device_sources or set()
    evidence: list[str] = []
    for source in _required_device_sources(patterns):
        prefix = "device-source-declared" if source in declared else "device-source-required"
        evidence.append(f"{prefix}:{source}")
    return evidence


def _substitution_evidence_and_score(
    patterns: list[BrainPattern],
    score: float,
    *,
    availability_matrix: OperatorAvailabilityMatrix | None,
    device_sources: set[str] | None,
    compiled: CompiledVisualTaskSpec | None = None,
) -> tuple[list[str], float]:
    pattern_ids = {pattern.pattern_id for pattern in patterns}
    if (
        compiled is not None
        and "glsl_advanced_pop_topology_shader" in pattern_ids
        and "deprecated-op:glslcreatePOP" in compiled.risk_flags
    ):
        evidence = ["substitution:glslcreatePOP->glsladvancedPOP+topologyPOP"]
        rule = _substitution_rule_for(missing_op="glslcreatePOP", replacement_pattern=None)
        if rule is not None:
            evidence.append(
                f"substitution-rule:{rule.missing_op}->{'+'.join(rule.replacement_ops)}:{rule.confidence}"
            )
        return evidence, score

    if "audio_device_to_analysis_chop" not in pattern_ids:
        return [], score
    if availability_matrix is None:
        return [], score
    missing_file_audio = availability_matrix.operators.get("audiofileinCHOP", {}).get("available") is False
    device_audio_available = (
        availability_matrix.operators.get("audiodeviceinCHOP", {}).get("available") is True
    )
    if missing_file_audio and device_audio_available:
        rule = _substitution_rule_for(
            missing_op="audiofileinCHOP", replacement_pattern="audio_device_to_analysis_chop"
        )
        approved = not _missing_required_device_sources(patterns, device_sources)
        if approved:
            evidence = ["substitution:audiofileinCHOP->audio_device_to_analysis_chop"]
            if rule is not None:
                approval_suffix = ":requires-approval" if rule.requires_user_approval else ""
                evidence.append(
                    f"substitution-rule:{rule.missing_op}->{'+'.join(rule.replacement_ops)}:{rule.confidence}"
                    f"{approval_suffix}"
                )
            return evidence, min(1.0, round(score + 0.16, 3))

        evidence = ["substitution:audiofileinCHOP->audio_device_to_analysis_chop:pending-approval"]
        if rule is not None:
            approval_suffix = ":requires-approval" if rule.requires_user_approval else ""
            evidence.append(
                f"substitution-rule:{rule.missing_op}->{'+'.join(rule.replacement_ops)}:{rule.confidence}{approval_suffix}"
            )
        return evidence, min(0.9, round(score + 0.2, 3))
    return [], score


def _substitution_rule_for(*, missing_op: str, replacement_pattern: str):
    for rule in load_operator_substitution_rules():
        if rule.missing_op == missing_op and rule.replacement_pattern == replacement_pattern:
            return rule
    return None


def _missing_required_device_sources(
    patterns: list[BrainPattern],
    device_sources: set[str] | None,
) -> list[str]:
    declared = device_sources or set()
    return [source for source in _required_device_sources(patterns) if source not in declared]


def _missing_required_addons(
    patterns: list[BrainPattern],
    availability_matrix: OperatorAvailabilityMatrix,
) -> list[str]:
    installed = set(availability_matrix.installed_addons)
    return [addon for addon in _required_addons(patterns) if addon not in installed]


def _required_addons(patterns: list[BrainPattern]) -> list[str]:
    return sorted({addon for pattern in patterns for addon in pattern.required_addons})


def _required_device_sources(patterns: list[BrainPattern]) -> list[str]:
    return sorted(
        {
            required_source
            for pattern in patterns
            for required_source in [_PATTERN_REQUIRED_DEVICE_SOURCES.get(pattern.pattern_id)]
            if required_source
        }
    )


def _candidate_label(patterns: list[BrainPattern]) -> str:
    pattern_ids = {pattern.pattern_id for pattern in patterns}
    if "ndi_in_to_post_fx_output" in pattern_ids:
        return "NDI input with post-FX stable TOP output"
    if "pop_particle_field_preview" in pattern_ids:
        return "POP particle field preview with stable TOP and debug output"
    if "glsl_top_shader_with_text_dat" in pattern_ids:
        return "GLSL TOP shader with source DAT and debug output"
    if "dat_execute_table_change_callback" in pattern_ids:
        return "DAT Execute table-change callback with stable diagnostics"
    if "websocket_dat_protocol_bridge" in pattern_ids:
        return "WebSocket DAT protocol bridge with stable diagnostics"
    if "osc_in_dat_protocol_bridge" in pattern_ids:
        return "OSC DAT protocol bridge with stable diagnostics"
    if "serial_dat_protocol_bridge" in pattern_ids:
        return "Serial DAT protocol bridge with stable diagnostics"
    if "midi_in_to_control_chop" in pattern_ids:
        return "MIDI control bridge to bounded CHOP output"
    if "glsl_material_render_pipeline" in pattern_ids:
        if "sop_noise_terrain_surface" in pattern_ids:
            if "audio_device_to_analysis_chop" in pattern_ids:
                return "Audio-device-reactive terrain GLSL material render with controls and debug output"
            return "Audio-file-reactive terrain GLSL material render with controls and debug output"
        if "panel_controls_to_chop_output" in pattern_ids:
            if "audio_device_to_analysis_chop" in pattern_ids:
                return "Audio-device-reactive GLSL material render with panel controls and debug output"
            return "Audio-file-reactive GLSL material render with panel controls and debug output"
        if "audio_device_to_analysis_chop" in pattern_ids:
            return "Audio-device-reactive GLSL material render with debug output"
        return "Audio-file-reactive GLSL material render with debug output"
    if patterns and patterns[0].pattern_id == "audio_device_to_analysis_chop":
        return "Audio-device-reactive feedback visual with panel controls and debug output"
    return "Audio-file-reactive feedback visual with panel controls and debug output"


def _pattern_with_id(patterns: list[BrainPattern], pattern_id: str) -> BrainPattern:
    for pattern in patterns:
        if pattern.pattern_id == pattern_id:
            return pattern
    return patterns[0]


def _with_concept_param(concepts, concept_id: str, param_name: str, value: str):
    updated = []
    for concept in concepts:
        if concept.id != concept_id:
            updated.append(concept)
            continue
        params = dict(concept.params)
        params[param_name] = value
        updated.append(concept.model_copy(update={"params": params}))
    return updated


def _exposed_node(pattern: BrainPattern, port_id: str) -> str | None:
    for port in pattern.exposes:
        if port.get("port_id") == port_id and port.get("node_id"):
            return str(port["node_id"])
    return None


def _consumed_target(pattern: BrainPattern, port_id: str) -> str | None:
    for port in pattern.consumes:
        if port.get("port_id") == port_id and port.get("target_node_id"):
            return str(port["target_node_id"])
    return None


__all__ = ["resolve_candidate_graphs"]
