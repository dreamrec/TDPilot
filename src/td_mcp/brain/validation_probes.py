"""Profile-specific validation probe registry for BrainPlan validation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from td_mcp.models.brain import ProfileValidationProbe

_REQUIRED_VALIDATION_PROFILES: tuple[str, ...] = (
    "feedback",
    "audio_reactive",
    "pop",
    "glsl",
    "glsl_material",
    "render_pipeline",
    "panel_ui",
    "dat_protocol",
)
_STRUCTURAL_VALIDATION_PROFILES: frozenset[str] = frozenset(
    {"auto", "structural_visual_safe", "structural_visual_expensive"}
)


def load_profile_validation_probes() -> list[ProfileValidationProbe]:
    """Return typed validation probes for current brain concept profiles."""
    return [ProfileValidationProbe(**item) for item in _PROBE_RECORDS]


def probes_for_profile(
    profile: str | None,
    *,
    registry: Iterable[ProfileValidationProbe] | None = None,
) -> list[ProfileValidationProbe]:
    """Return probes for one concept profile in registry order."""
    if not profile:
        return []
    return [probe for probe in (registry or load_profile_validation_probes()) if probe.profile == profile]


def probes_for_profiles(
    profiles: Iterable[str | None],
    *,
    registry: Iterable[ProfileValidationProbe] | None = None,
) -> list[ProfileValidationProbe]:
    """Return probes for several concept profiles in first-seen profile order."""
    records = list(registry or load_profile_validation_probes())
    probes: list[ProfileValidationProbe] = []
    seen: set[tuple[str, str]] = set()
    for profile in profiles:
        if not profile:
            continue
        for probe in probes_for_profile(profile, registry=records):
            key = (probe.profile, probe.probe_id)
            if key in seen:
                continue
            seen.add(key)
            probes.append(probe)
    return probes


def probe_ids_for_profile(
    profile: str | None,
    *,
    registry: Iterable[ProfileValidationProbe] | None = None,
) -> list[str]:
    """Return stable probe/check identifiers for one concept profile."""
    return list(dict.fromkeys(probe.probe_id for probe in probes_for_profile(profile, registry=registry)))


def probe_ids_for_profiles(
    profiles: Iterable[str | None],
    *,
    registry: Iterable[ProfileValidationProbe] | None = None,
) -> list[str]:
    """Return stable probe/check identifiers for several concept profiles."""
    return list(dict.fromkeys(probe.probe_id for probe in probes_for_profiles(profiles, registry=registry)))


def probe_summaries_for_profile(
    validation_profile: str,
    concept_profile: str | None,
    *,
    include_expensive: bool = False,
    registry: Iterable[ProfileValidationProbe] | None = None,
) -> list[dict[str, Any]]:
    """Return machine-readable probe summaries for planning/report payloads."""
    return probe_summaries_for_profiles(
        validation_profile,
        [concept_profile],
        include_expensive=include_expensive,
        registry=registry,
    )


def probe_summaries_for_profiles(
    validation_profile: str,
    concept_profiles: Iterable[str | None],
    *,
    include_expensive: bool = False,
    registry: Iterable[ProfileValidationProbe] | None = None,
) -> list[dict[str, Any]]:
    """Return machine-readable probe summaries for one or more profile layers."""
    if validation_profile not in _STRUCTURAL_VALIDATION_PROFILES:
        return []
    include_expensive = include_expensive or validation_profile == "structural_visual_expensive"
    summaries: list[dict[str, Any]] = []
    for probe in probes_for_profiles(concept_profiles, registry=registry):
        if probe.cost_level == "expensive" and not include_expensive:
            continue
        summaries.append(
            {
                "probe_id": probe.probe_id,
                "profile": probe.profile,
                "required_inputs": list(probe.required_inputs),
                "readback_strategy": probe.readback_strategy,
                "metric_names": list(probe.metric_names),
                "pass_conditions": list(probe.pass_conditions),
                "cost_level": probe.cost_level,
                "failure_message": probe.failure_message,
                "official_sources": list(probe.official_sources),
            }
        )
    return summaries


def validation_probe_coverage_report(
    registry: Iterable[ProfileValidationProbe] | None = None,
) -> dict[str, Any]:
    """Report release-gate coverage for profile-specific validation probes."""
    records = list(registry or load_profile_validation_probes())
    by_profile: dict[str, list[ProfileValidationProbe]] = {}
    invalid_sources: list[dict[str, str]] = []
    uncontrolled_expensive: list[dict[str, str]] = []

    for probe in records:
        by_profile.setdefault(probe.profile, []).append(probe)
        for source in probe.official_sources:
            if not source.startswith("https://docs.derivative.ca/"):
                invalid_sources.append(
                    {
                        "profile": probe.profile,
                        "probe_id": probe.probe_id,
                        "official_source": source,
                    }
                )
        if probe.cost_level == "expensive" and "optional" not in probe.readback_strategy:
            uncontrolled_expensive.append(
                {
                    "profile": probe.profile,
                    "probe_id": probe.probe_id,
                    "readback_strategy": probe.readback_strategy,
                }
            )

    missing_required = sorted(
        profile for profile in _REQUIRED_VALIDATION_PROFILES if not by_profile.get(profile)
    )
    covered_required = sorted(profile for profile in _REQUIRED_VALIDATION_PROFILES if by_profile.get(profile))
    expensive = [
        {"profile": probe.profile, "probe_id": probe.probe_id}
        for probe in records
        if probe.cost_level == "expensive"
    ]
    return {
        "schema_version": 1,
        "ok": not missing_required and not invalid_sources and not uncontrolled_expensive,
        "probe_count": len(records),
        "profile_count": len(by_profile),
        "required_profile_count": len(_REQUIRED_VALIDATION_PROFILES),
        "covered_required_profile_count": len(covered_required),
        "covered_required_profiles": covered_required,
        "missing_required_profile_count": len(missing_required),
        "missing_required_profiles": missing_required,
        "invalid_source_count": len(invalid_sources),
        "invalid_sources": invalid_sources,
        "expensive_probe_count": len(expensive),
        "expensive_probes": expensive,
        "uncontrolled_expensive_probe_count": len(uncontrolled_expensive),
        "uncontrolled_expensive_probes": uncontrolled_expensive,
        "probe_count_by_profile": {profile: len(probes) for profile, probes in sorted(by_profile.items())},
    }


def _probe(
    probe_id: str,
    profile: str,
    *,
    required_inputs: list[str],
    readback_strategy: str,
    metric_names: list[str],
    pass_conditions: list[str],
    cost_level: str = "cheap",
    failure_message: str,
    official_sources: list[str],
) -> dict[str, Any]:
    return {
        "probe_id": probe_id,
        "profile": profile,
        "required_inputs": required_inputs,
        "readback_strategy": readback_strategy,
        "metric_names": metric_names,
        "pass_conditions": pass_conditions,
        "cost_level": cost_level,
        "failure_message": failure_message,
        "official_sources": official_sources,
    }


_PROBE_RECORDS: list[dict[str, Any]] = [
    _probe(
        "output_node_present",
        "generic",
        required_inputs=["nullTOP"],
        readback_strategy="static_graph",
        metric_names=["stable_output_node_present"],
        pass_conditions=["a stable output operator exists in the planned graph"],
        failure_message="Generic plans must expose a stable output node.",
        official_sources=["https://docs.derivative.ca/Null_TOP"],
    ),
    _probe(
        "feedback_cycle",
        "feedback",
        required_inputs=["feedbackTOP", "compositeTOP"],
        readback_strategy="static_graph",
        metric_names=["feedback_cycle_present"],
        pass_conditions=["feedback path closes through a downstream TOP target"],
        failure_message="Feedback plans must contain a closed feedback path.",
        official_sources=["https://docs.derivative.ca/Feedback_TOP"],
    ),
    _probe(
        "decay_control",
        "feedback",
        required_inputs=["levelTOP"],
        readback_strategy="parameter_readback",
        metric_names=["feedback_decay_stage_present"],
        pass_conditions=["feedback path contains a bounded decay or level stage"],
        failure_message="Feedback plans must include a bounded decay control stage.",
        official_sources=["https://docs.derivative.ca/Level_TOP"],
    ),
    _probe(
        "feedback_static_warning_review",
        "feedback",
        required_inputs=["feedbackTOP"],
        readback_strategy="td_error_report",
        metric_names=["feedback_static_warning_count"],
        pass_conditions=["no unresolved feedback static/cook warnings remain"],
        failure_message="Feedback warnings must be reviewed before the network is considered complete.",
        official_sources=["https://docs.derivative.ca/Feedback_TOP"],
    ),
    _probe(
        "feedback_output_readback",
        "feedback",
        required_inputs=["feedbackTOP", "nullTOP"],
        readback_strategy="top_luminance_runtime",
        metric_names=["feedback_output_luminance_mean", "feedback_output_luminance_max"],
        pass_conditions=["runtime validation samples the stable TOP output and sees visible luminance"],
        failure_message="Feedback plans require runtime evidence that the stable TOP output is visible.",
        official_sources=[
            "https://docs.derivative.ca/Feedback_TOP",
            "https://docs.derivative.ca/Null_TOP",
            "https://docs.derivative.ca/TOP_Class",
        ],
    ),
    _probe(
        "audio_source_present",
        "audio_reactive",
        required_inputs=["audiofileinCHOP"],
        readback_strategy="static_graph",
        metric_names=["audio_source_node_present"],
        pass_conditions=["an audio CHOP source exists before analysis"],
        failure_message="Audio-reactive plans require a real audio source CHOP.",
        official_sources=["https://docs.derivative.ca/Audio_File_In_CHOP"],
    ),
    _probe(
        "analysis_stage",
        "audio_reactive",
        required_inputs=["analyzeCHOP"],
        readback_strategy="static_graph",
        metric_names=["analysis_stage_present"],
        pass_conditions=["audio signal is routed through an analysis stage"],
        failure_message="Audio-reactive plans require an analysis stage.",
        official_sources=["https://docs.derivative.ca/Analyze_CHOP"],
    ),
    _probe(
        "range_mapping",
        "audio_reactive",
        required_inputs=["mathCHOP"],
        readback_strategy="parameter_readback",
        metric_names=["mapped_control_range_present"],
        pass_conditions=["analysis output is shaped into a bounded control range"],
        failure_message="Audio-reactive plans require bounded range mapping.",
        official_sources=["https://docs.derivative.ca/Math_CHOP"],
    ),
    _probe(
        "audio_signal_activity",
        "audio_reactive",
        required_inputs=["audiofileinCHOP", "audiodeviceinCHOP", "analyzeCHOP", "nullCHOP"],
        readback_strategy="chop_channel_delta_runtime",
        metric_names=["audio_analysis_channel_delta", "audio_analysis_channel_samples"],
        pass_conditions=[
            "runtime validation samples analyzed CHOP output over frames and observes a non-zero delta"
        ],
        failure_message="Audio-reactive plans require runtime evidence that analyzed audio channels move over time.",
        official_sources=[
            "https://docs.derivative.ca/Audio_File_In_CHOP",
            "https://docs.derivative.ca/Audio_Device_In_CHOP",
            "https://docs.derivative.ca/Analyze_CHOP",
            "https://docs.derivative.ca/Null_CHOP",
        ],
    ),
    _probe(
        "visual_or_chop_target",
        "audio_reactive",
        required_inputs=["nullCHOP"],
        readback_strategy="static_graph",
        metric_names=["audio_control_output_present"],
        pass_conditions=["audio analysis exposes a stable CHOP control output"],
        failure_message="Audio-reactive plans must expose a stable control output.",
        official_sources=["https://docs.derivative.ca/Null_CHOP"],
    ),
    _probe(
        "midi_source_present",
        "midi_control",
        required_inputs=["midiinCHOP"],
        readback_strategy="static_graph",
        metric_names=["midi_source_node_present"],
        pass_conditions=["a MIDI In CHOP exists before range mapping"],
        failure_message="MIDI control plans require a MIDI In CHOP source.",
        official_sources=["https://docs.derivative.ca/MIDI_In_CHOP"],
    ),
    _probe(
        "serial_source_present",
        "dat_protocol",
        required_inputs=["serialDAT"],
        readback_strategy="static_graph",
        metric_names=["serial_dat_source_present"],
        pass_conditions=["a Serial DAT exists before stable DAT output"],
        failure_message="Serial DAT protocol plans require a Serial DAT source.",
        official_sources=["https://docs.derivative.ca/Serial_DAT"],
    ),
    _probe(
        "osc_source_present",
        "dat_protocol",
        required_inputs=["oscinDAT"],
        readback_strategy="static_graph",
        metric_names=["osc_dat_source_present"],
        pass_conditions=["an OSC In DAT exists before stable DAT output"],
        failure_message="OSC DAT protocol plans require an OSC In DAT source.",
        official_sources=["https://docs.derivative.ca/OSC_In_DAT"],
    ),
    _probe(
        "websocket_source_present",
        "dat_protocol",
        required_inputs=["websocketDAT"],
        readback_strategy="static_graph",
        metric_names=["websocket_dat_source_present"],
        pass_conditions=["a WebSocket DAT exists before stable DAT output"],
        failure_message="WebSocket DAT protocol plans require a WebSocket DAT source.",
        official_sources=["https://docs.derivative.ca/WebSocket_DAT"],
    ),
    _probe(
        "mqtt_source_present",
        "dat_protocol",
        required_inputs=["mqttclientDAT"],
        readback_strategy="static_graph",
        metric_names=["mqtt_client_dat_source_present"],
        pass_conditions=["an MQTT Client DAT exists before stable DAT output"],
        failure_message="MQTT DAT protocol plans require an MQTT Client DAT source.",
        official_sources=["https://docs.derivative.ca/MQTT_Client_DAT"],
    ),
    _probe(
        "udp_source_present",
        "dat_protocol",
        required_inputs=["udpinDAT"],
        readback_strategy="static_graph",
        metric_names=["udp_in_dat_source_present"],
        pass_conditions=["a UDP In DAT exists before stable DAT output"],
        failure_message="UDP DAT protocol plans require a UDP In DAT source.",
        official_sources=["https://docs.derivative.ca/UDP_In_DAT"],
    ),
    _probe(
        "protocol_table_output",
        "dat_protocol",
        required_inputs=["tableDAT", "nullDAT"],
        readback_strategy="static_graph",
        metric_names=["protocol_table_and_stable_dat_present"],
        pass_conditions=["protocol diagnostics table and stable DAT output exist"],
        failure_message="DAT protocol plans require diagnostics table and stable DAT output.",
        official_sources=["https://docs.derivative.ca/Table_DAT", "https://docs.derivative.ca/Null_DAT"],
    ),
    _probe(
        "render_switch_table_present",
        "dat_protocol",
        required_inputs=["tableDAT", "switchTOP"],
        readback_strategy="static_graph",
        metric_names=["render_switch_table_and_switch_present"],
        pass_conditions=["a DAT table and Switch TOP are both present in the compiled graph"],
        failure_message="DAT table render-switch plans require a table and Switch TOP.",
        official_sources=["https://docs.derivative.ca/Table_DAT", "https://docs.derivative.ca/Switch_TOP"],
    ),
    _probe(
        "render_switch_index_binding",
        "dat_protocol",
        required_inputs=["tableDAT", "switchTOP"],
        readback_strategy="parameter_readback",
        metric_names=["render_switch_table_index_binding_present"],
        pass_conditions=["Switch TOP index is driven by the generated DAT table selection"],
        failure_message="DAT table render-switch plans require Switch TOP index to read the generated table.",
        official_sources=["https://docs.derivative.ca/Table_DAT", "https://docs.derivative.ca/Switch_TOP"],
    ),
    _probe(
        "render_switch_output_present",
        "dat_protocol",
        required_inputs=["switchTOP", "nullTOP"],
        readback_strategy="static_graph",
        metric_names=["render_switch_stable_top_present"],
        pass_conditions=["Switch TOP output terminates at a stable Null TOP"],
        failure_message="DAT table render-switch plans require a stable TOP output.",
        official_sources=["https://docs.derivative.ca/Switch_TOP", "https://docs.derivative.ca/Null_TOP"],
    ),
    _probe(
        "dat_execute_callback_present",
        "dat_protocol",
        required_inputs=["datexecuteDAT", "textDAT"],
        readback_strategy="static_graph",
        metric_names=["dat_execute_callback_source_present"],
        pass_conditions=["a DAT Execute DAT carries generated callback source for the monitored table"],
        failure_message="DAT Execute callback plans require generated callback source on the DAT Execute DAT.",
        official_sources=[
            "https://docs.derivative.ca/DAT_Execute_DAT",
            "https://docs.derivative.ca/Text_DAT",
        ],
    ),
    _probe(
        "callback_guard_present",
        "dat_protocol",
        required_inputs=["datexecuteDAT"],
        readback_strategy="node_content_runtime",
        metric_names=["modern_table_change_callback_present"],
        pass_conditions=["callback source uses onTableChange and avoids deprecated row/cell/size callbacks"],
        failure_message="DAT Execute callback plans require a modern onTableChange callback template.",
        official_sources=["https://docs.derivative.ca/DAT_Execute_DAT"],
    ),
    _probe(
        "ndi_source_present",
        "video_io",
        required_inputs=["ndiinTOP"],
        readback_strategy="static_graph",
        metric_names=["ndi_source_top_present"],
        pass_conditions=["an NDI In TOP exists before post-FX processing"],
        failure_message="NDI video I/O plans require an NDI In TOP source.",
        official_sources=["https://docs.derivative.ca/NDI_In_TOP"],
    ),
    _probe(
        "post_fx_stage",
        "video_io",
        required_inputs=["levelTOP"],
        readback_strategy="static_graph",
        metric_names=["post_fx_top_stage_present"],
        pass_conditions=["network video is routed through a post-FX TOP stage"],
        failure_message="NDI post-FX plans require a TOP processing stage.",
        official_sources=["https://docs.derivative.ca/Level_TOP"],
    ),
    _probe(
        "top_output_present",
        "video_io",
        required_inputs=["nullTOP"],
        readback_strategy="static_graph",
        metric_names=["stable_top_output_present"],
        pass_conditions=["post-FX video terminates at a stable TOP output"],
        failure_message="NDI post-FX plans require a stable TOP output.",
        official_sources=["https://docs.derivative.ca/Null_TOP"],
    ),
    _probe(
        "pop_source_present",
        "pop",
        required_inputs=["circlePOP"],
        readback_strategy="static_graph",
        metric_names=["pop_source_node_present"],
        pass_conditions=["a POP source or generator begins the particle graph"],
        failure_message="POP plans require a source POP.",
        official_sources=["https://docs.derivative.ca/Circle_POP"],
    ),
    _probe(
        "pop_output_attached",
        "pop",
        required_inputs=["nullPOP", "rendersimpleTOP"],
        readback_strategy="static_graph",
        metric_names=["pop_output_attached_to_preview"],
        pass_conditions=["POP output is routed to a stable POP and preview TOP"],
        failure_message="POP plans must attach output to a stable POP and preview.",
        official_sources=["https://docs.derivative.ca/Render_Simple_TOP"],
    ),
    _probe(
        "finite_pop_bounds",
        "pop",
        required_inputs=["nullPOP"],
        readback_strategy="pop_bounds_runtime",
        metric_names=["pop_bounds_finite"],
        pass_conditions=["POP output bounds remain finite"],
        failure_message="POP output bounds must be finite.",
        official_sources=["https://docs.derivative.ca/POP"],
    ),
    _probe(
        "attribute_sample_available",
        "pop",
        required_inputs=["nullPOP"],
        readback_strategy="pop_attribute_metadata_runtime",
        metric_names=["pop_attribute_count_present"],
        pass_conditions=["POP output exposes attribute metadata for validation"],
        failure_message="POP validation needs attribute metadata from the output POP.",
        official_sources=["https://docs.derivative.ca/POP"],
    ),
    _probe(
        "shader_source_present",
        "glsl",
        required_inputs=["glslTOP", "textDAT"],
        readback_strategy="static_graph",
        metric_names=["shader_dat_reference_present"],
        pass_conditions=["GLSL operator references a shader source DAT"],
        failure_message="GLSL TOP plans must attach shader source DATs.",
        official_sources=["https://docs.derivative.ca/GLSL_TOP"],
    ),
    _probe(
        "compile_state",
        "glsl",
        required_inputs=["glslTOP"],
        readback_strategy="node_errors_runtime",
        metric_names=["shader_compile_clean"],
        pass_conditions=["shader compile diagnostics report no errors"],
        failure_message="GLSL TOP compile state must be clean.",
        official_sources=["https://docs.derivative.ca/GLSL_TOP"],
    ),
    _probe(
        "sampler_uniforms",
        "glsl",
        required_inputs=["glslTOP"],
        readback_strategy="parameter_readback",
        metric_names=["sampler_binding_count"],
        pass_conditions=["declared sampler inputs match planned TOP inputs"],
        failure_message="GLSL TOP sampler bindings must match planned inputs.",
        official_sources=["https://docs.derivative.ca/GLSL_TOP"],
    ),
    _probe(
        "nonblack_output",
        "glsl",
        required_inputs=["nullTOP"],
        readback_strategy="top_sample_optional",
        metric_names=["output_luminance", "output_entropy"],
        pass_conditions=["output TOP is neither black nor trivially constant"],
        cost_level="expensive",
        failure_message="GLSL TOP output must produce nontrivial pixels.",
        official_sources=["https://docs.derivative.ca/TOP_Class"],
    ),
    _probe(
        "shader_source_present",
        "glsl_material",
        required_inputs=["glslMAT", "textDAT"],
        readback_strategy="static_graph",
        metric_names=["material_shader_dat_refs_present"],
        pass_conditions=["GLSL MAT references vertex and pixel shader DATs"],
        failure_message="GLSL MAT plans must attach shader source DATs.",
        official_sources=["https://docs.derivative.ca/GLSL_MAT"],
    ),
    _probe(
        "material_assigned",
        "glsl_material",
        required_inputs=["geometryCOMP", "glslMAT"],
        readback_strategy="parameter_readback",
        metric_names=["geometry_material_ref_valid"],
        pass_conditions=["geometry material parameter points at the created MAT"],
        failure_message="Rendered GLSL material plans must assign the material to geometry.",
        official_sources=["https://docs.derivative.ca/Geometry_COMP"],
    ),
    _probe(
        "vertex_position_transform",
        "glsl_material",
        required_inputs=["glslMAT"],
        readback_strategy="shader_static_check",
        metric_names=["vertex_transform_code_present"],
        pass_conditions=["vertex shader uses TouchDesigner material transform conventions"],
        failure_message="GLSL MAT vertex shaders must follow TouchDesigner transform conventions.",
        official_sources=["https://docs.derivative.ca/Write_a_GLSL_MAT"],
    ),
    _probe(
        "compile_state",
        "glsl_material",
        required_inputs=["glslMAT"],
        readback_strategy="node_errors_runtime",
        metric_names=["material_compile_clean"],
        pass_conditions=["material shader diagnostics report no errors"],
        failure_message="GLSL MAT compile state must be clean.",
        official_sources=["https://docs.derivative.ca/GLSL_MAT"],
    ),
    _probe(
        "render_top_output",
        "glsl_material",
        required_inputs=["renderTOP", "nullTOP"],
        readback_strategy="top_sample_optional",
        metric_names=["render_luminance", "render_coverage"],
        pass_conditions=["render output has visible coverage"],
        cost_level="expensive",
        failure_message="GLSL material render output must be visible.",
        official_sources=["https://docs.derivative.ca/TOP_Class"],
    ),
    _probe(
        "shader_source_present",
        "glsl_pop",
        required_inputs=["glslPOP", "textDAT"],
        readback_strategy="static_graph",
        metric_names=["pop_shader_dat_ref_present"],
        pass_conditions=["GLSL POP references compute shader DAT"],
        failure_message="GLSL POP plans must attach compute shader source.",
        official_sources=["https://docs.derivative.ca/GLSL_POP"],
    ),
    _probe(
        "pop_attribute_class",
        "glsl_pop",
        required_inputs=["glslPOP"],
        readback_strategy="parameter_readback",
        metric_names=["pop_attribute_class_valid"],
        pass_conditions=["GLSL POP attribute class matches the planned data"],
        failure_message="GLSL POP attribute class must match the planned data.",
        official_sources=["https://docs.derivative.ca/GLSL_POP"],
    ),
    _probe(
        "compile_state",
        "glsl_pop",
        required_inputs=["glslPOP"],
        readback_strategy="node_errors_runtime",
        metric_names=["pop_shader_compile_clean"],
        pass_conditions=["GLSL POP compile diagnostics report no errors"],
        failure_message="GLSL POP compile state must be clean.",
        official_sources=["https://docs.derivative.ca/GLSL_POP"],
    ),
    _probe(
        "finite_pop_bounds",
        "glsl_pop",
        required_inputs=["nullPOP"],
        readback_strategy="pop_bounds_runtime",
        metric_names=["pop_bounds_finite"],
        pass_conditions=["shader-authored POP bounds remain finite"],
        failure_message="GLSL POP output bounds must be finite.",
        official_sources=["https://docs.derivative.ca/POP"],
    ),
    _probe(
        "attribute_sample_available",
        "glsl_pop",
        required_inputs=["nullPOP"],
        readback_strategy="pop_attribute_metadata_runtime",
        metric_names=["pop_attribute_count_present"],
        pass_conditions=["shader-authored POP exposes attribute metadata"],
        failure_message="GLSL POP validation needs output attribute metadata.",
        official_sources=["https://docs.derivative.ca/POP"],
    ),
    _probe(
        "topology_capacity",
        "glsl_pop",
        required_inputs=["glsladvancedPOP", "topologyPOP"],
        readback_strategy="parameter_readback",
        metric_names=["advanced_pop_topology_capacity_present"],
        pass_conditions=["advanced POP/topology stages declare bounded output topology capacity"],
        failure_message="Topology-changing GLSL POP plans require bounded topology capacity.",
        official_sources=[
            "https://docs.derivative.ca/GLSL_Advanced_POP",
            "https://docs.derivative.ca/Topology_POP",
        ],
    ),
    _probe(
        "camera_present",
        "render_pipeline",
        required_inputs=["cameraCOMP"],
        readback_strategy="static_graph",
        metric_names=["camera_comp_present"],
        pass_conditions=["render pipeline includes a Camera COMP"],
        failure_message="Render pipelines require a camera.",
        official_sources=["https://docs.derivative.ca/Camera_COMP"],
    ),
    _probe(
        "geometry_present",
        "render_pipeline",
        required_inputs=["geometryCOMP"],
        readback_strategy="static_graph",
        metric_names=["geometry_comp_present"],
        pass_conditions=["render pipeline includes a Geometry COMP"],
        failure_message="Render pipelines require geometry.",
        official_sources=["https://docs.derivative.ca/Geometry_COMP"],
    ),
    _probe(
        "material_or_default",
        "render_pipeline",
        required_inputs=["geometryCOMP"],
        readback_strategy="parameter_readback",
        metric_names=["material_or_default_render_path_present"],
        pass_conditions=["geometry has material assignment or explicit default-material design"],
        failure_message="Render pipelines must define material/default render behavior.",
        official_sources=["https://docs.derivative.ca/Render_TOP"],
    ),
    _probe(
        "camera_frustum_coverage",
        "render_pipeline",
        required_inputs=["renderTOP", "cameraCOMP", "geometryCOMP"],
        readback_strategy="render_camera_frustum_runtime",
        metric_names=["render_camera_ref_bound", "render_geometry_ref_bound"],
        pass_conditions=["Render TOP references the planned Camera COMP and Geometry COMP"],
        failure_message="Render pipelines require camera and geometry references that can enter the render view.",
        official_sources=[
            "https://docs.derivative.ca/Render_TOP",
            "https://docs.derivative.ca/Camera_COMP",
            "https://docs.derivative.ca/Geometry_COMP",
        ],
    ),
    _probe(
        "render_top_output",
        "render_pipeline",
        required_inputs=["renderTOP", "nullTOP"],
        readback_strategy="top_sample_optional",
        metric_names=["render_luminance", "render_coverage"],
        pass_conditions=["render output has visible coverage"],
        cost_level="expensive",
        failure_message="Render TOP output must be visible.",
        official_sources=["https://docs.derivative.ca/TOP_Class"],
    ),
    _probe(
        "panel_components_present",
        "panel_ui",
        required_inputs=["containerCOMP", "sliderCOMP", "buttonCOMP"],
        readback_strategy="static_graph",
        metric_names=["panel_component_count"],
        pass_conditions=["panel UI contains visible/control components"],
        failure_message="Panel UI plans require panel components.",
        official_sources=["https://docs.derivative.ca/Panel"],
    ),
    _probe(
        "panel_state_reader",
        "panel_ui",
        required_inputs=["panelCHOP"],
        readback_strategy="static_graph",
        metric_names=["panel_chop_present"],
        pass_conditions=["Panel CHOP reads state from panel components"],
        failure_message="Panel UI plans require a Panel CHOP state reader.",
        official_sources=["https://docs.derivative.ca/Panel_CHOP"],
    ),
    _probe(
        "panel_state_readback",
        "panel_ui",
        required_inputs=["panelCHOP", "nullCHOP"],
        readback_strategy="chop_channel_presence_runtime",
        metric_names=["panel_state_channel_count", "panel_state_sample_count"],
        pass_conditions=["runtime validation samples the stable panel CHOP output and sees channels"],
        failure_message="Panel UI plans require runtime evidence that panel state reaches a stable CHOP output.",
        official_sources=[
            "https://docs.derivative.ca/Panel_CHOP",
            "https://docs.derivative.ca/Null_CHOP",
        ],
    ),
    _probe(
        "callbacks_or_exports",
        "panel_ui",
        required_inputs=["panelCHOP"],
        readback_strategy="static_graph",
        metric_names=["panel_binding_path_present"],
        pass_conditions=["panel state has callbacks, exports, or stable output for downstream binding"],
        failure_message="Panel UI controls need a downstream binding path.",
        official_sources=["https://docs.derivative.ca/Export"],
    ),
    _probe(
        "control_output",
        "panel_ui",
        required_inputs=["nullCHOP"],
        readback_strategy="static_graph",
        metric_names=["panel_control_output_present"],
        pass_conditions=["panel control channels terminate at a stable CHOP output"],
        failure_message="Panel UI plans must expose stable CHOP control output.",
        official_sources=["https://docs.derivative.ca/Null_CHOP"],
    ),
    _probe(
        "custom_parameters_present",
        "control_rig",
        required_inputs=["baseCOMP"],
        readback_strategy="parameter_readback",
        metric_names=["custom_parameter_host_present"],
        pass_conditions=["a component hosts the custom parameter/control surface"],
        failure_message="Control rigs require a parameter host component.",
        official_sources=["https://docs.derivative.ca/Component_Editor_Dialog"],
    ),
    _probe(
        "bounds_or_ranges",
        "control_rig",
        required_inputs=["mathCHOP"],
        readback_strategy="parameter_readback",
        metric_names=["control_range_bounds_present"],
        pass_conditions=["control values are bounded before output"],
        failure_message="Control rigs must define bounded control ranges.",
        official_sources=["https://docs.derivative.ca/Math_CHOP"],
    ),
    _probe(
        "mapping_output",
        "control_rig",
        required_inputs=["mathCHOP", "nullCHOP"],
        readback_strategy="static_graph",
        metric_names=["control_mapping_output_present"],
        pass_conditions=["control mapping terminates at a stable CHOP output"],
        failure_message="Control rigs must expose mapped CHOP output.",
        official_sources=["https://docs.derivative.ca/Null_CHOP"],
    ),
    _probe(
        "target_bindings",
        "control_rig",
        required_inputs=["baseCOMP"],
        readback_strategy="static_graph",
        metric_names=["control_target_binding_path_present"],
        pass_conditions=["control rig declares or exposes target bindings"],
        failure_message="Control rigs need explicit target binding paths.",
        official_sources=["https://docs.derivative.ca/Binding"],
    ),
    _probe(
        "component_shell_present",
        "concept_compiled",
        required_inputs=["baseCOMP"],
        readback_strategy="static_graph",
        metric_names=["component_shell_present"],
        pass_conditions=["compiler-backed assembly is rooted inside a deterministic Base COMP shell"],
        failure_message="Compiler-backed assembly plans require a component shell.",
        official_sources=[
            "https://docs.derivative.ca/Base_COMP",
            "https://docs.derivative.ca/Component",
        ],
    ),
    _probe(
        "audio_source_present",
        "concept_compiled",
        required_inputs=["audiofileinCHOP", "audiodeviceinCHOP"],
        readback_strategy="static_graph",
        metric_names=["compiled_audio_source_present"],
        pass_conditions=["compiled graph contains an audio source pattern"],
        failure_message="Compiler-backed audio feedback plans require an audio source.",
        official_sources=["https://docs.derivative.ca/Audio_File_In_CHOP"],
    ),
    _probe(
        "feedback_cycle",
        "concept_compiled",
        required_inputs=["feedbackTOP", "levelTOP", "compositeTOP"],
        readback_strategy="static_graph",
        metric_names=["compiled_feedback_cycle_present"],
        pass_conditions=["compiled graph contains feedback, decay, and composite stages"],
        failure_message="Compiler-backed feedback plans require a bounded feedback loop.",
        official_sources=["https://docs.derivative.ca/Feedback_TOP"],
    ),
    _probe(
        "panel_state_reader",
        "concept_compiled",
        required_inputs=["panelCHOP"],
        readback_strategy="static_graph",
        metric_names=["compiled_panel_state_reader_present"],
        pass_conditions=["compiled graph contains a panel state reader"],
        failure_message="Compiler-backed control plans require panel state readback.",
        official_sources=["https://docs.derivative.ca/Panel_CHOP"],
    ),
    _probe(
        "control_output",
        "concept_compiled",
        required_inputs=["nullCHOP"],
        readback_strategy="static_graph",
        metric_names=["compiled_control_output_present"],
        pass_conditions=["compiled graph exposes stable CHOP control output"],
        failure_message="Compiler-backed control plans require stable CHOP output.",
        official_sources=["https://docs.derivative.ca/Null_CHOP"],
    ),
    _probe(
        "output_node_present",
        "concept_compiled",
        required_inputs=["nullTOP", "nullCHOP", "nullDAT", "nullPOP", "textDAT"],
        readback_strategy="static_graph",
        metric_names=["compiled_stable_and_debug_outputs_present"],
        pass_conditions=["compiled graph exposes stable output and debug output conventions"],
        failure_message="Compiler-backed plans require stable and debug outputs.",
        official_sources=[
            "https://docs.derivative.ca/Null_TOP",
            "https://docs.derivative.ca/Null_CHOP",
            "https://docs.derivative.ca/Null_DAT",
            "https://docs.derivative.ca/Null_POP",
        ],
    ),
]


__all__ = [
    "load_profile_validation_probes",
    "probe_ids_for_profile",
    "probe_ids_for_profiles",
    "probe_summaries_for_profile",
    "probe_summaries_for_profiles",
    "probes_for_profile",
    "probes_for_profiles",
    "validation_probe_coverage_report",
]
