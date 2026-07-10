from __future__ import annotations

import json

import pytest

from td_mcp.brain.concept_compiler import build_candidate_graphs, compile_visual_task
from td_mcp.brain.operator_availability import build_operator_availability_matrix
from td_mcp.brain.pattern_resolver import resolve_candidate_graphs
from td_mcp.brain.patterns import load_pattern_registry


class FakeCardIndex:
    def __init__(self, known: set[str]):
        self.known = known

    def get_operator(self, op_type: str):
        if op_type in self.known:
            return {
                "op_type": op_type,
                "docs_url": f"https://docs.derivative.ca/{op_type}",
                "summary": f"{op_type} official docs",
            }
        return None


ALL_SEED_OPS = {
    "audiofileinCHOP",
    "analyzeCHOP",
    "mathCHOP",
    "nullCHOP",
    "noiseTOP",
    "feedbackTOP",
    "levelTOP",
    "compositeTOP",
    "nullTOP",
    "containerCOMP",
    "sliderCOMP",
    "buttonCOMP",
    "panelCHOP",
    "textDAT",
}

MATERIAL_RENDER_OPS = ALL_SEED_OPS | {
    "geometryCOMP",
    "cameraCOMP",
    "glslMAT",
    "renderTOP",
}
TERRAIN_MATERIAL_OPS = MATERIAL_RENDER_OPS | {"gridSOP", "noiseSOP", "nullSOP"}
MIDI_CONTROL_OPS = {"midiinCHOP", "mathCHOP", "nullCHOP"}
SERIAL_PROTOCOL_OPS = {"serialDAT", "tableDAT", "nullDAT"}
OSC_PROTOCOL_OPS = {"oscinDAT", "tableDAT", "nullDAT"}
WEBSOCKET_PROTOCOL_OPS = {"websocketDAT", "tableDAT", "nullDAT"}
MQTT_PROTOCOL_OPS = {"mqttclientDAT", "tableDAT", "nullDAT"}
UDP_PROTOCOL_OPS = {"udpinDAT", "tableDAT", "nullDAT"}
DAT_EXECUTE_CALLBACK_OPS = {"datexecuteDAT", "tableDAT", "textDAT", "nullDAT"}
NDI_POST_FX_OPS = {"ndiinTOP", "levelTOP", "nullTOP"}
POP_PREVIEW_OPS = {"circlePOP", "noisePOP", "mathmixPOP", "nullPOP", "rendersimpleTOP", "nullTOP"}
GLSL_TOP_SHADER_OPS = {"constantTOP", "glslTOP", "textDAT", "nullTOP"}
DAT_RENDER_SWITCH_OPS = {"tableDAT", "constantTOP", "noiseTOP", "switchTOP", "nullTOP", "textDAT"}
GLSL_ADVANCED_POP_OPS = {
    "circlePOP",
    "glsladvancedPOP",
    "topologyPOP",
    "textDAT",
    "nullPOP",
    "rendersimpleTOP",
    "nullTOP",
}


def test_compiler_extracts_multi_domain_audio_feedback_panel_task():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["CHOP", "TOP", "COMP", "DAT"]
    assert {"audio-reactive", "feedback", "control-panel", "debug-output"}.issubset(set(compiled.motifs))
    assert compiled.time_behavior == [
        "beat_or_amplitude_modulation",
        "continuous_feedback",
        "event_driven_control",
    ]
    assert {"audio_reactive", "feedback", "panel_ui"}.issubset(set(compiled.candidate_profiles))
    assert "audio_signal_activity" in compiled.validation_needs
    assert "feedback_output_readback" in compiled.validation_needs
    assert "panel_state_readback" in compiled.validation_needs
    assert {"audio_analysis", "feedback_loop", "panel_controls", "debug_output"}.issubset(
        set(compiled.required_capabilities)
    )
    assert "docs:audiofileinCHOP" in compiled.grounding_evidence
    assert "docs:feedbackTOP" in compiled.grounding_evidence
    assert "docs:panelCHOP" in compiled.grounding_evidence


def test_compiler_extracts_audio_reactive_glsl_material_render_task():
    compiled = compile_visual_task(
        "Build an audio-reactive 3D render with material modulation",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(MATERIAL_RENDER_OPS),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["CHOP", "TOP", "COMP", "DAT", "MAT"]
    assert {"audio-reactive", "rendered-3d", "material-modulation"}.issubset(set(compiled.motifs))
    assert {"audio_reactive", "render_pipeline", "glsl_material"}.issubset(set(compiled.candidate_profiles))
    assert "audio_signal_activity" in compiled.validation_needs
    assert {"audio_analysis", "render_pipeline", "material_modulation"}.issubset(
        set(compiled.required_capabilities)
    )
    assert "docs:audiofileinCHOP" in compiled.grounding_evidence
    assert "docs:glslMAT" in compiled.grounding_evidence
    assert "docs:renderTOP" in compiled.grounding_evidence


def test_compiler_extracts_audio_reactive_glsl_material_render_with_panel_task():
    compiled = compile_visual_task(
        "Build an audio-reactive GLSL material render with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(MATERIAL_RENDER_OPS),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["CHOP", "TOP", "COMP", "DAT", "MAT"]
    assert {
        "audio-reactive",
        "rendered-3d",
        "material-modulation",
        "control-panel",
        "debug-output",
    }.issubset(set(compiled.motifs))
    assert {"audio_reactive", "render_pipeline", "glsl_material", "panel_ui"}.issubset(
        set(compiled.candidate_profiles)
    )
    assert {
        "audio_analysis",
        "render_pipeline",
        "material_modulation",
        "panel_controls",
        "debug_output",
    }.issubset(set(compiled.required_capabilities))
    assert "docs:audiofileinCHOP" in compiled.grounding_evidence
    assert "docs:glslMAT" in compiled.grounding_evidence
    assert "docs:panelCHOP" in compiled.grounding_evidence


def test_compiler_extracts_audio_reactive_terrain_material_with_controls_task():
    compiled = compile_visual_task(
        "Build a melting glass terrain driven by music with UI controls and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(TERRAIN_MATERIAL_OPS),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["CHOP", "TOP", "COMP", "DAT", "SOP", "MAT"]
    assert {
        "beat_or_amplitude_modulation",
        "continuous_animation",
        "event_driven_control",
    }.issubset(set(compiled.time_behavior))
    assert {
        "audio-reactive",
        "terrain-surface",
        "rendered-3d",
        "material-modulation",
        "control-panel",
        "debug-output",
    }.issubset(set(compiled.motifs))
    assert {"audio_reactive", "render_pipeline", "glsl_material", "panel_ui"}.issubset(
        set(compiled.candidate_profiles)
    )
    assert {
        "audio_analysis",
        "terrain_surface",
        "render_pipeline",
        "material_modulation",
        "panel_controls",
        "debug_output",
    }.issubset(set(compiled.required_capabilities))
    assert "docs:gridSOP" in compiled.grounding_evidence
    assert "docs:noiseSOP" in compiled.grounding_evidence
    assert "docs:glslMAT" in compiled.grounding_evidence


def test_compiler_extracts_midi_control_chop_task():
    compiled = compile_visual_task(
        "Build a MIDI control bridge with normalized CHOP output",
        target_root="/project1",
        card_index=FakeCardIndex(MIDI_CONTROL_OPS),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["CHOP"]
    assert "midi-control" in compiled.motifs
    assert compiled.candidate_profiles == ["midi_control"]
    assert "midi_control" in compiled.required_capabilities
    assert "docs:midiinCHOP" in compiled.grounding_evidence


def test_compiler_extracts_serial_dat_protocol_task():
    compiled = compile_visual_task(
        "Build a serial DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(SERIAL_PROTOCOL_OPS),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["DAT"]
    assert "serial-protocol" in compiled.motifs
    assert compiled.candidate_profiles == ["dat_protocol"]
    assert "serial_dat_protocol" in compiled.required_capabilities
    assert "docs:serialDAT" in compiled.grounding_evidence


def test_compiler_extracts_dat_execute_table_change_callback_task():
    compiled = compile_visual_task(
        "Build a DAT Execute table-change callback with stable DAT diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(DAT_EXECUTE_CALLBACK_OPS),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["DAT"]
    assert "dat-table-callback" in compiled.motifs
    assert compiled.candidate_profiles == ["dat_protocol"]
    assert "dat_execute_callback" in compiled.required_capabilities
    assert "docs:datexecuteDAT" in compiled.grounding_evidence


def test_compiler_extracts_mqtt_dat_protocol_task():
    compiled = compile_visual_task(
        "Build an MQTT DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(MQTT_PROTOCOL_OPS),
    )
    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert compiled.blocked_questions == []
    assert compiled.domains == ["DAT"]
    assert "mqtt-protocol" in compiled.motifs
    assert compiled.candidate_profiles == ["dat_protocol"]
    assert "mqtt_dat_protocol" in compiled.required_capabilities
    assert "mqtt_source_present" in compiled.validation_needs
    assert "docs:mqttclientDAT" in compiled.grounding_evidence

    assert candidates
    candidate = candidates[0]
    assert "mqtt_client_dat_protocol_bridge" in candidate.pattern_ids
    assert {"mqttclientDAT", "tableDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    assert "mqtt_source_present" in candidate.validation_needs


def test_compiler_extracts_udp_dat_protocol_task():
    compiled = compile_visual_task(
        "Build a UDP DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(UDP_PROTOCOL_OPS),
    )
    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert compiled.blocked_questions == []
    assert compiled.domains == ["DAT"]
    assert "udp-protocol" in compiled.motifs
    assert compiled.candidate_profiles == ["dat_protocol"]
    assert "udp_dat_protocol" in compiled.required_capabilities
    assert "udp_source_present" in compiled.validation_needs
    assert "docs:udpinDAT" in compiled.grounding_evidence

    assert candidates
    candidate = candidates[0]
    assert "udp_in_dat_protocol_bridge" in candidate.pattern_ids
    assert {"udpinDAT", "tableDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    assert "udp_source_present" in candidate.validation_needs


def test_compiler_extracts_dat_table_render_switch_task():
    compiled = compile_visual_task(
        "Build a DAT table driven render switch with stable TOP output and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(DAT_RENDER_SWITCH_OPS),
    )
    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert compiled.blocked_questions == []
    assert compiled.domains == ["TOP", "DAT"]
    assert {"dat-table-render-switch", "debug-output"}.issubset(set(compiled.motifs))
    assert compiled.candidate_profiles == ["dat_protocol"]
    assert {"dat_table_render_switch", "debug_output"}.issubset(set(compiled.required_capabilities))
    assert "render_switch_table_present" in compiled.validation_needs
    assert "render_switch_index_binding" in compiled.validation_needs
    assert "render_switch_output_present" in compiled.validation_needs
    assert "docs:tableDAT" in compiled.grounding_evidence
    assert "docs:switchTOP" in compiled.grounding_evidence
    assert "docs:nullTOP" in compiled.grounding_evidence

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "dat_table_render_switch_top" in candidate.pattern_ids
    assert {"tableDAT", "constantTOP", "noiseTOP", "switchTOP", "nullTOP"}.issubset(
        set(candidate.required_ops)
    )
    assert "render_switch_table_present" in candidate.validation_needs
    assert "render_switch_index_binding" in candidate.validation_needs
    assert "render_switch_output_present" in candidate.validation_needs
    assert any(edge.kind == "reference" and edge.source == "switch_table" for edge in candidate.edges)


def test_compiler_extracts_ndi_post_fx_output_task():
    compiled = compile_visual_task(
        "Build an NDI input with post FX and stable TOP output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(NDI_POST_FX_OPS),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["TOP"]
    assert "ndi-video-input" in compiled.motifs
    assert compiled.candidate_profiles == ["video_io"]
    assert "ndi_input" in compiled.required_capabilities
    assert "post_fx_output" in compiled.required_capabilities
    assert "docs:ndiinTOP" in compiled.grounding_evidence
    assert "docs:levelTOP" in compiled.grounding_evidence
    assert "docs:nullTOP" in compiled.grounding_evidence


def test_compiler_extracts_pop_particle_preview_task():
    compiled = compile_visual_task(
        "Build a POP particle field preview with stable TOP output and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(POP_PREVIEW_OPS | {"textDAT"}),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["TOP", "DAT", "POP"]
    assert {"pop-particle-field", "preview", "debug-output"}.issubset(set(compiled.motifs))
    assert compiled.candidate_profiles == ["pop"]
    assert {"pop_particle_field_preview", "debug_output"}.issubset(set(compiled.required_capabilities))
    assert "docs:circlePOP" in compiled.grounding_evidence
    assert "docs:rendersimpleTOP" in compiled.grounding_evidence
    assert "docs:nullTOP" in compiled.grounding_evidence


def test_compiler_extracts_glsl_top_shader_task():
    compiled = compile_visual_task(
        "Build a GLSL TOP shader with source texture, shader DAT, stable TOP output, and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(GLSL_TOP_SHADER_OPS),
    )

    assert compiled.blocked_questions == []
    assert compiled.domains == ["TOP", "DAT"]
    assert {"glsl-top-shader", "texture-effect", "debug-output"}.issubset(set(compiled.motifs))
    assert compiled.candidate_profiles == ["glsl"]
    assert {"glsl_top_shader", "debug_output"}.issubset(set(compiled.required_capabilities))
    assert "docs:constantTOP" in compiled.grounding_evidence
    assert "docs:glslTOP" in compiled.grounding_evidence
    assert "docs:textDAT" in compiled.grounding_evidence


def test_compiler_routes_topology_changing_glsl_pop_to_advanced_pop_pattern():
    compiled = compile_visual_task(
        "Build a GLSL POP shader that changes point counts and writes topology "
        "with a stable TOP preview and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(GLSL_ADVANCED_POP_OPS),
    )
    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert compiled.blocked_questions == []
    assert compiled.domains == ["TOP", "DAT", "POP"]
    assert {"glsl-advanced-pop", "topology-changing", "debug-output"}.issubset(set(compiled.motifs))
    assert {"pop", "glsl"}.issubset(set(compiled.candidate_profiles))
    assert {"glsl_advanced_pop_topology", "debug_output"}.issubset(set(compiled.required_capabilities))
    assert "docs:glsladvancedPOP" in compiled.grounding_evidence
    assert "docs:topologyPOP" in compiled.grounding_evidence

    assert candidates
    candidate = candidates[0]
    assert "glsl_advanced_pop_topology_shader" in candidate.pattern_ids
    assert {
        "circlePOP",
        "glsladvancedPOP",
        "topologyPOP",
        "textDAT",
        "nullPOP",
        "rendersimpleTOP",
        "nullTOP",
    }.issubset(set(candidate.required_ops))
    assert "glslPOP" not in candidate.required_ops
    assert "topology_capacity" in candidate.validation_needs


def test_compiler_surfaces_deprecated_glsl_create_pop_substitution_evidence():
    compiled = compile_visual_task(
        "Build a GLSL Create POP topology shader with stable TOP preview and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(GLSL_ADVANCED_POP_OPS | {"glslcreatePOP"}),
    )
    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert compiled.blocked_questions == []
    assert "deprecated-glsl-create-pop" in compiled.motifs
    assert "deprecated-op:glslcreatePOP" in compiled.risk_flags

    assert candidates
    candidate = candidates[0]
    assert "glsl_advanced_pop_topology_shader" in candidate.pattern_ids
    assert "glslcreatePOP" not in candidate.required_ops
    assert "substitution:glslcreatePOP->glsladvancedPOP+topologyPOP" in candidate.grounding_evidence
    assert "substitution-rule:glslcreatePOP->glsladvancedPOP+topologyPOP:high" in candidate.grounding_evidence


def test_vague_prompt_blocks_without_candidate_profiles_or_graphs():
    compiled = compile_visual_task("make it cool", target_root="/project1")

    assert compiled.blocked_questions
    assert compiled.candidate_profiles == []
    assert build_candidate_graphs(compiled) == []


def test_pattern_registry_loads_seed_patterns_with_official_sources():
    patterns = load_pattern_registry()
    by_id = {pattern.pattern_id: pattern for pattern in patterns}

    assert {
        "audio_analysis_chop_chain",
        "feedback_top_loop",
        "panel_control_output",
        "debug_output_conventions",
        "dat_execute_table_change_callback",
        "mqtt_client_dat_protocol_bridge",
        "udp_in_dat_protocol_bridge",
        "dat_table_render_switch_top",
        "ndi_in_to_post_fx_output",
    }.issubset(by_id)
    assert by_id["audio_analysis_chop_chain"].required_ops == [
        "audiofileinCHOP",
        "analyzeCHOP",
        "mathCHOP",
        "nullCHOP",
    ]
    for pattern in patterns:
        assert pattern.required_ops
        assert pattern.validation_probes
        assert all(source.startswith("https://docs.derivative.ca/") for source in pattern.official_sources)
    assert "feedback_output_readback" in by_id["feedback_top_loop"].validation_probes


def test_pattern_registry_validates_all_seed_patterns_from_json(tmp_path):
    from td_mcp.brain import patterns as pattern_module

    assert hasattr(pattern_module, "load_pattern_registry_from_json")
    expected = load_pattern_registry()
    pattern_path = tmp_path / "patterns.json"
    pattern_path.write_text(
        json.dumps([pattern.model_dump(mode="json") for pattern in expected]),
        encoding="utf-8",
    )

    loaded = pattern_module.load_pattern_registry_from_json(pattern_path)

    assert [pattern.pattern_id for pattern in loaded] == [pattern.pattern_id for pattern in expected]
    assert loaded[0].concept_nodes[0].op_type == expected[0].concept_nodes[0].op_type
    assert all(
        source.startswith("https://docs.derivative.ca/")
        for pattern in loaded
        for source in pattern.official_sources
    )


def test_pattern_registry_rejects_invalid_json_pattern_records(tmp_path):
    from td_mcp.brain import patterns as pattern_module

    assert hasattr(pattern_module, "load_pattern_registry_from_json")
    bad_record = load_pattern_registry()[0].model_dump(mode="json")
    bad_record["required_ops"] = []
    pattern_path = tmp_path / "bad_patterns.json"
    pattern_path.write_text(json.dumps([bad_record]), encoding="utf-8")

    with pytest.raises(ValueError, match="pattern requires at least one required op"):
        pattern_module.load_pattern_registry_from_json(pattern_path)


def test_pattern_registry_covers_master_plan_first_pattern_set():
    patterns = load_pattern_registry()
    by_id = {pattern.pattern_id: pattern for pattern in patterns}

    assert {
        "audio_file_to_analysis_chop",
        "audio_device_to_analysis_chop",
        "feedback_decay_top_loop",
        "pop_particle_field_preview",
        "glsl_top_shader_with_text_dat",
        "glsl_material_render_pipeline",
        "render_geo_camera_light_output",
        "panel_controls_to_chop_output",
        "dat_execute_table_change_callback",
        "serial_dat_protocol_bridge",
        "dat_table_render_switch_top",
        "midi_in_to_control_chop",
        "ndi_in_to_post_fx_output",
    }.issubset(by_id)

    audio = by_id["audio_file_to_analysis_chop"]
    audio_analyze = next(node for node in audio.concept_nodes if node.id == "audio_analyze")
    audio_math = next(node for node in audio.concept_nodes if node.id == "audio_math")
    assert audio_analyze.params == {
        "function": "RMS Power",
        "allowstart": False,
        "allowend": False,
        "valleys": False,
    }
    assert audio_math.params == {"fromrange": (0.0, 1.0), "torange": (0.0, 1.0), "interppars": True}

    audio_device = by_id["audio_device_to_analysis_chop"]
    audio_device_source = next(
        node for node in audio_device.concept_nodes if node.id == "audio_device_source"
    )
    assert audio_device_source.params == {"active": True, "errormissing": True, "format": "stereo"}

    feedback = by_id["feedback_decay_top_loop"]
    feedback_decay = next(node for node in feedback.concept_nodes if node.id == "feedback_decay")
    assert feedback_decay.params == {"opacity": 0.92}

    midi = by_id["midi_in_to_control_chop"]
    midi_source = next(node for node in midi.concept_nodes if node.id == "midi_source")
    assert midi_source.params == {"simplified": True, "record": False, "timer": False, "sys": False}
    midi_range = next(node for node in midi.concept_nodes if node.id == "midi_range")
    assert midi_range.params == {
        "fromrange": (0.0, 127.0),
        "torange": (0.0, 1.0),
        "interppars": True,
        "integer": "off",
    }

    serial = by_id["serial_dat_protocol_bridge"]
    serial_source = next(node for node in serial.concept_nodes if node.id == "serial_source")
    assert serial_source.params == {"active": True, "format": "perline", "clamp": True, "maxlines": 256}

    osc = by_id["osc_in_dat_protocol_bridge"]
    osc_source = next(node for node in osc.concept_nodes if node.id == "osc_source")
    assert osc_source.params == {"active": True, "protocol": "msging", "clamp": True, "maxlines": 256}

    websocket = by_id["websocket_dat_protocol_bridge"]
    websocket_source = next(node for node in websocket.concept_nodes if node.id == "websocket_source")
    assert websocket_source.params == {"active": True, "clamp": True, "maxlines": 256}

    mqtt = by_id["mqtt_client_dat_protocol_bridge"]
    mqtt_source = next(node for node in mqtt.concept_nodes if node.id == "mqtt_source")
    assert mqtt_source.params == {"active": True, "reconnect": True, "clamp": True, "maxlines": 256}

    udp = by_id["udp_in_dat_protocol_bridge"]
    udp_source = next(node for node in udp.concept_nodes if node.id == "udp_source")
    assert udp_source.params == {
        "active": True,
        "protocol": "msging",
        "format": "permessage",
        "clamp": True,
        "maxlines": 256,
    }

    pop = by_id["pop_particle_field_preview"]
    assert pop.required_ops == [
        "circlePOP",
        "noisePOP",
        "mathmixPOP",
        "nullPOP",
        "rendersimpleTOP",
        "nullTOP",
    ]
    assert {"pop_source_present", "pop_output_attached", "finite_pop_bounds"}.issubset(
        set(pop.validation_probes)
    )
    assert pop.exposes == [
        {"port_id": "stable_pop", "domain": "POP", "node_id": "pop_out"},
        {"port_id": "stable_top", "domain": "TOP", "node_id": "stable_output"},
    ]

    glsl_top = by_id["glsl_top_shader_with_text_dat"]
    assert glsl_top.required_ops == ["constantTOP", "glslTOP", "textDAT", "nullTOP"]
    shader_node = next(node for node in glsl_top.concept_nodes if node.id == "shader")
    assert shader_node.params["pixeldat"] == "${path:shader_code}"
    code_node = next(node for node in glsl_top.concept_nodes if node.id == "shader_code")
    assert code_node.generated_code is not None
    assert code_node.generated_code["static_checks"] == [
        "glsl_no_version_line",
        "glsl_top_declares_pixel_output",
        "glsl_top_uses_td_output_swizzle",
    ]

    render = by_id["render_geo_camera_light_output"]
    assert render.required_ops == ["geometryCOMP", "cameraCOMP", "lightCOMP", "renderTOP", "nullTOP"]
    assert {"camera_present", "geometry_present", "material_or_default", "render_top_output"}.issubset(
        set(render.validation_probes)
    )

    terrain = by_id["sop_noise_terrain_surface"]
    assert terrain.required_ops == ["gridSOP", "noiseSOP", "nullSOP"]
    assert terrain.exposes == [{"port_id": "terrain_sop", "domain": "SOP", "node_id": "terrain_out"}]
    assert "output_node_present" in terrain.validation_probes


def test_candidate_graph_composes_seed_patterns_and_docs_grounded_required_ops():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS),
    )
    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert len(candidates) >= 2
    candidate = candidates[0]
    assert candidate.profiles == ["audio_reactive", "feedback", "panel_ui"]
    assert {
        "audio_analysis_chop_chain",
        "feedback_top_loop",
        "panel_control_output",
        "debug_output_conventions",
    }.issubset(set(candidate.pattern_ids))
    assert {
        "audiofileinCHOP",
        "analyzeCHOP",
        "mathCHOP",
        "nullCHOP",
        "noiseTOP",
        "feedbackTOP",
        "levelTOP",
        "compositeTOP",
        "nullTOP",
        "containerCOMP",
        "sliderCOMP",
        "buttonCOMP",
        "panelCHOP",
        "textDAT",
    }.issubset(set(candidate.required_ops))
    assert "feedback_output_readback" in candidate.validation_needs
    assert "panel_state_readback" in candidate.validation_needs
    assert any(edge.kind == "control" and edge.source == "audio_out" for edge in candidate.edges)
    concept_params = {node.id: node.params for node in candidate.concepts if node.params}
    assert concept_params["audio_analyze"]["function"] == "RMS Power"
    assert concept_params["audio_math"]["torange"] == (0.0, 1.0)
    assert concept_params["feedback_decay"]["opacity"] == 0.92
    assert all(f"docs:{op_type}" in candidate.grounding_evidence for op_type in candidate.required_ops)


def test_candidate_graph_composes_audio_reactive_glsl_material_render():
    compiled = compile_visual_task(
        "Build an audio-reactive 3D render with material modulation",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(MATERIAL_RENDER_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["audio_reactive", "render_pipeline", "glsl_material"]
    assert {
        "audio_analysis_chop_chain",
        "glsl_material_render_pipeline",
        "debug_output_conventions",
    }.issubset(set(candidate.pattern_ids))
    assert {
        "audiofileinCHOP",
        "analyzeCHOP",
        "mathCHOP",
        "nullCHOP",
        "geometryCOMP",
        "cameraCOMP",
        "glslMAT",
        "renderTOP",
        "textDAT",
        "nullTOP",
    }.issubset(set(candidate.required_ops))
    assert any(
        edge.kind == "control" and edge.source == "audio_out" and edge.target == "material"
        for edge in candidate.edges
    )
    assert all(f"docs:{op_type}" in candidate.grounding_evidence for op_type in candidate.required_ops)


def test_candidate_graph_composes_audio_reactive_glsl_material_render_with_panel_controls():
    compiled = compile_visual_task(
        "Build an audio-reactive GLSL material render with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(MATERIAL_RENDER_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["audio_reactive", "render_pipeline", "glsl_material", "panel_ui"]
    assert {
        "audio_analysis_chop_chain",
        "glsl_material_render_pipeline",
        "panel_control_output",
        "debug_output_conventions",
    }.issubset(set(candidate.pattern_ids))
    assert {
        "audiofileinCHOP",
        "analyzeCHOP",
        "mathCHOP",
        "nullCHOP",
        "geometryCOMP",
        "cameraCOMP",
        "glslMAT",
        "renderTOP",
        "textDAT",
        "containerCOMP",
        "sliderCOMP",
        "buttonCOMP",
        "panelCHOP",
        "nullTOP",
    }.issubset(set(candidate.required_ops))
    assert any(
        edge.kind == "control" and edge.source == "audio_out" and edge.target == "material"
        for edge in candidate.edges
    )
    assert any(
        edge.kind == "control" and edge.source == "panel_out" and edge.target == "material"
        for edge in candidate.edges
    )
    assert all(f"docs:{op_type}" in candidate.grounding_evidence for op_type in candidate.required_ops)


def test_candidate_graph_composes_audio_reactive_terrain_material_controls():
    compiled = compile_visual_task(
        "Build a melting glass terrain driven by music with UI controls and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(TERRAIN_MATERIAL_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["audio_reactive", "render_pipeline", "glsl_material", "panel_ui"]
    assert {
        "audio_analysis_chop_chain",
        "sop_noise_terrain_surface",
        "glsl_material_render_pipeline",
        "panel_control_output",
        "debug_output_conventions",
    }.issubset(set(candidate.pattern_ids))
    assert {
        "audiofileinCHOP",
        "analyzeCHOP",
        "mathCHOP",
        "nullCHOP",
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "glslMAT",
        "renderTOP",
        "textDAT",
        "containerCOMP",
        "sliderCOMP",
        "buttonCOMP",
        "panelCHOP",
        "nullTOP",
    }.issubset(set(candidate.required_ops))
    geo = next(concept for concept in candidate.concepts if concept.id == "geo")
    assert geo.params["sop"] == "${path:terrain_out}"
    assert any(
        edge.kind == "reference" and edge.source == "terrain_out" and edge.target == "geo"
        for edge in candidate.edges
    )
    assert any(
        edge.kind == "control" and edge.source == "audio_out" and edge.target == "material"
        for edge in candidate.edges
    )
    assert all(f"docs:{op_type}" in candidate.grounding_evidence for op_type in candidate.required_ops)


def test_candidate_graph_composes_midi_control_pattern_and_marks_device_dependency():
    compiled = compile_visual_task(
        "Build a MIDI control bridge with normalized CHOP output",
        target_root="/project1",
        card_index=FakeCardIndex(MIDI_CONTROL_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry(), device_sources=set())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["midi_control"]
    assert "midi_in_to_control_chop" in candidate.pattern_ids
    assert {"midiinCHOP", "mathCHOP", "nullCHOP"}.issubset(set(candidate.required_ops))
    midi_source = next(node for node in candidate.concepts if node.id == "midi_source")
    assert midi_source.params == {"simplified": True, "record": False, "timer": False, "sys": False}
    midi_range = next(node for node in candidate.concepts if node.id == "midi_range")
    assert midi_range.params == {
        "fromrange": (0.0, 127.0),
        "torange": (0.0, 1.0),
        "interppars": True,
        "integer": "off",
    }
    assert "device-source-required" in candidate.risk_flags


def test_candidate_graph_composes_serial_dat_protocol_pattern_and_marks_device_dependency():
    compiled = compile_visual_task(
        "Build a serial DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(SERIAL_PROTOCOL_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry(), device_sources=set())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "serial_dat_protocol_bridge" in candidate.pattern_ids
    assert {"serialDAT", "tableDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    serial_source = next(node for node in candidate.concepts if node.id == "serial_source")
    assert serial_source.params == {"active": True, "format": "perline", "clamp": True, "maxlines": 256}
    assert "device-source-required" in candidate.risk_flags


def test_candidate_graph_composes_osc_dat_protocol_pattern_and_marks_device_dependency():
    compiled = compile_visual_task(
        "Build an OSC DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(OSC_PROTOCOL_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry(), device_sources=set())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "osc_in_dat_protocol_bridge" in candidate.pattern_ids
    assert {"oscinDAT", "tableDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    osc_source = next(node for node in candidate.concepts if node.id == "osc_source")
    assert osc_source.params == {"active": True, "protocol": "msging", "clamp": True, "maxlines": 256}
    assert "device-source-required" in candidate.risk_flags
    assert "osc_source_present" in candidate.validation_needs


def test_candidate_graph_composes_websocket_dat_protocol_pattern_and_marks_device_dependency():
    compiled = compile_visual_task(
        "Build a WebSocket DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(WEBSOCKET_PROTOCOL_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry(), device_sources=set())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "websocket_dat_protocol_bridge" in candidate.pattern_ids
    assert {"websocketDAT", "tableDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    websocket_source = next(node for node in candidate.concepts if node.id == "websocket_source")
    assert websocket_source.params == {"active": True, "clamp": True, "maxlines": 256}
    assert "device-source-required" in candidate.risk_flags
    assert "websocket_source_present" in candidate.validation_needs


def test_candidate_graph_composes_dat_execute_table_change_callback_pattern():
    compiled = compile_visual_task(
        "Build a DAT Execute table-change callback with stable DAT diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(DAT_EXECUTE_CALLBACK_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry(), device_sources=set())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "dat_execute_table_change_callback" in candidate.pattern_ids
    assert {"datexecuteDAT", "tableDAT", "textDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    assert "device-source-required" not in candidate.risk_flags
    assert "callback_guard_present" in candidate.validation_needs


def test_candidate_graph_composes_ndi_post_fx_pattern_and_marks_device_dependency():
    compiled = compile_visual_task(
        "Build an NDI input with post FX and stable TOP output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(NDI_POST_FX_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry(), device_sources=set())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["video_io"]
    assert "ndi_in_to_post_fx_output" in candidate.pattern_ids
    assert {"ndiinTOP", "levelTOP", "nullTOP"}.issubset(set(candidate.required_ops))
    assert "device-source-required" in candidate.risk_flags
    assert "ndi_source_present" in candidate.validation_needs
    assert "post_fx_stage" in candidate.validation_needs


@pytest.mark.parametrize(
    ("prompt", "card_ops", "pattern_id", "required_source"),
    [
        (
            "Build a MIDI control bridge with normalized CHOP output",
            MIDI_CONTROL_OPS,
            "midi_in_to_control_chop",
            "midi_device",
        ),
        (
            "Build a serial DAT protocol bridge with table diagnostics",
            SERIAL_PROTOCOL_OPS,
            "serial_dat_protocol_bridge",
            "serial_device",
        ),
        (
            "Build an OSC DAT protocol bridge with table diagnostics",
            OSC_PROTOCOL_OPS,
            "osc_in_dat_protocol_bridge",
            "osc_source",
        ),
        (
            "Build a WebSocket DAT protocol bridge with table diagnostics",
            WEBSOCKET_PROTOCOL_OPS,
            "websocket_dat_protocol_bridge",
            "websocket_endpoint",
        ),
        (
            "Build an NDI input with post FX and stable TOP output",
            NDI_POST_FX_OPS,
            "ndi_in_to_post_fx_output",
            "ndi_source",
        ),
    ],
)
def test_device_dependent_candidates_explain_required_device_source(
    prompt: str,
    card_ops: set[str],
    pattern_id: str,
    required_source: str,
) -> None:
    compiled = compile_visual_task(
        prompt,
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(card_ops),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry(), device_sources=set())

    candidate = next(item for item in candidates if pattern_id in item.pattern_ids)
    assert "device-source-required" in candidate.risk_flags
    assert f"device-source-required:{required_source}" in candidate.grounding_evidence


def test_candidate_graph_composes_pop_particle_preview_and_debug_patterns():
    compiled = compile_visual_task(
        "Build a POP particle field preview with stable TOP output and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(POP_PREVIEW_OPS | {"textDAT"}),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry(), device_sources=set())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["pop"]
    assert {"pop_particle_field_preview", "debug_output_conventions"}.issubset(set(candidate.pattern_ids))
    assert {
        "circlePOP",
        "noisePOP",
        "mathmixPOP",
        "nullPOP",
        "rendersimpleTOP",
        "nullTOP",
        "textDAT",
    }.issubset(set(candidate.required_ops))
    assert "finite_pop_bounds" in candidate.validation_needs
    assert "validate-pop-render-preview" in candidate.risk_flags
    # Debug notes are validation metadata, not an operator reference target;
    # the compiler must not emit a semantic reference edge it cannot lower.
    assert not any(edge.kind == "reference" and edge.target == "debug_notes" for edge in candidate.edges)
    assert all(f"docs:{op_type}" in candidate.grounding_evidence for op_type in candidate.required_ops)


def test_candidate_graph_composes_glsl_top_shader_and_debug_patterns():
    compiled = compile_visual_task(
        "Build a GLSL TOP shader with source texture, shader DAT, stable TOP output, and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(GLSL_TOP_SHADER_OPS),
    )

    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry(), device_sources=set())

    assert candidates
    candidate = candidates[0]
    assert candidate.profiles == ["glsl"]
    assert {"glsl_top_shader_with_text_dat", "debug_output_conventions"}.issubset(set(candidate.pattern_ids))
    assert {"constantTOP", "glslTOP", "textDAT", "nullTOP"}.issubset(set(candidate.required_ops))
    assert "shader_source_present" in candidate.validation_needs
    assert "compile_state" in candidate.validation_needs
    assert "validate-glsl-compile-state" in candidate.risk_flags
    assert not any(edge.kind == "reference" and edge.target == "debug_notes" for edge in candidate.edges)
    assert all(f"docs:{op_type}" in candidate.grounding_evidence for op_type in candidate.required_ops)


def test_pattern_resolver_returns_ranked_file_and_device_candidates():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
    )

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=load_pattern_registry(),
        available_ops=ALL_SEED_OPS | {"audiodeviceinCHOP"},
    )

    assert len(candidates) >= 2
    assert candidates[0].score > candidates[1].score
    assert "audio_file_to_analysis_chop" in candidates[0].pattern_ids
    assert "audio_device_to_analysis_chop" in {
        pid for candidate in candidates for pid in candidate.pattern_ids
    }
    assert "profiles:audio_reactive+feedback+panel_ui" in candidates[0].explanation


def test_pattern_resolver_prefers_promoted_trace_patterns_when_inputs_are_available():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
    )
    patterns = [
        pattern.model_copy(update={"promoted_from_trace": "trace:audio-device-feedback-green"})
        if pattern.pattern_id == "audio_device_to_analysis_chop"
        else pattern
        for pattern in load_pattern_registry()
    ]

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=patterns,
        available_ops=ALL_SEED_OPS | {"audiodeviceinCHOP"},
        device_sources={"audio_device"},
    )

    assert "audio_device_to_analysis_chop" in candidates[0].pattern_ids
    assert "trace-promoted:trace:audio-device-feedback-green" in candidates[0].grounding_evidence
    assert candidates[0].score > next(
        candidate.score for candidate in candidates if "audio_file_to_analysis_chop" in candidate.pattern_ids
    )


def test_pattern_resolver_marks_runtime_validated_trace_evidence_and_ranking_bonus():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
    )
    patterns = [
        pattern.model_copy(
            update={
                "promoted_from_trace": "trace:audio-device-feedback-green",
                "layout": {
                    **pattern.layout,
                    "trace_support_count": 1,
                    "support_trace_ids": ["trace:audio-device-feedback-green"],
                    "runtime_validation": {
                        "required_probe_ids": ["audio_signal_activity", "feedback_output_readback"],
                        "passed_probe_ids": ["audio_signal_activity", "feedback_output_readback"],
                    },
                },
            }
        )
        if pattern.pattern_id == "audio_device_to_analysis_chop"
        else pattern
        for pattern in load_pattern_registry()
    ]

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=patterns,
        available_ops=ALL_SEED_OPS | {"audiodeviceinCHOP"},
        device_sources={"audio_device"},
    )

    assert "audio_device_to_analysis_chop" in candidates[0].pattern_ids
    assert "trace-runtime-validation:2" in candidates[0].grounding_evidence
    assert "runtime_validation:2" in candidates[0].explanation


def test_pattern_resolver_marks_weighted_runtime_validation_evidence():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
    )
    patterns = [
        pattern.model_copy(
            update={
                "promoted_from_trace": "trace:audio-device-feedback-weighted",
                "layout": {
                    **pattern.layout,
                    "trace_support_count": 1,
                    "support_trace_ids": ["trace:audio-device-feedback-weighted"],
                    "runtime_validation": {
                        "required_probe_ids": ["audio_signal_activity", "feedback_output_readback"],
                        "passed_probe_ids": ["audio_signal_activity", "feedback_output_readback"],
                        "passed_probe_weights": {
                            "audio_signal_activity": 0.75,
                            "feedback_output_readback": 1.5,
                        },
                        "confidence_decay": 0.8,
                    },
                },
            }
        )
        if pattern.pattern_id == "audio_device_to_analysis_chop"
        else pattern
        for pattern in load_pattern_registry()
    ]

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=patterns,
        available_ops=ALL_SEED_OPS | {"audiodeviceinCHOP"},
        device_sources={"audio_device"},
    )

    top = candidates[0]
    assert "audio_device_to_analysis_chop" in top.pattern_ids
    assert (
        "runtime-validation-probe:audio_device_to_analysis_chop:audio_signal_activity:0.7500"
        in top.grounding_evidence
    )
    assert (
        "runtime-validation-probe:audio_device_to_analysis_chop:feedback_output_readback:1.5000"
        in top.grounding_evidence
    )
    assert "runtime-validation-decay:audio_device_to_analysis_chop:0.8000" in top.grounding_evidence
    assert "runtime-validation-score:audio_device_to_analysis_chop:1.8000" in top.grounding_evidence
    assert "runtime_validation_score:1.8000" in top.explanation


def test_pattern_resolver_penalizes_promoted_traces_with_missing_runtime_probes():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
    )
    patterns = []
    for pattern in load_pattern_registry():
        if pattern.pattern_id == "audio_file_to_analysis_chop":
            patterns.append(
                pattern.model_copy(
                    update={
                        "promoted_from_trace": "trace:audio-file-feedback-complete",
                        "layout": {
                            **pattern.layout,
                            "trace_support_count": 1,
                            "support_trace_ids": ["trace:audio-file-feedback-complete"],
                            "runtime_validation": {
                                "required_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                                "passed_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                            },
                        },
                    }
                )
            )
        elif pattern.pattern_id == "audio_device_to_analysis_chop":
            patterns.append(
                pattern.model_copy(
                    update={
                        "promoted_from_trace": "trace:audio-device-feedback-incomplete",
                        "layout": {
                            **pattern.layout,
                            "trace_support_count": 1,
                            "support_trace_ids": ["trace:audio-device-feedback-incomplete"],
                            "runtime_validation": {
                                "required_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                    "top_output_present",
                                    "panel_state_readback",
                                ],
                                "passed_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                                "missing_probe_ids": [
                                    "top_output_present",
                                    "panel_state_readback",
                                ],
                            },
                        },
                    }
                )
            )
        else:
            patterns.append(pattern)

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=patterns,
        available_ops=ALL_SEED_OPS | {"audiodeviceinCHOP"},
        device_sources={"audio_device"},
    )

    file_candidate = next(
        candidate for candidate in candidates if "audio_file_to_analysis_chop" in candidate.pattern_ids
    )
    device_candidate = next(
        candidate for candidate in candidates if "audio_device_to_analysis_chop" in candidate.pattern_ids
    )
    assert file_candidate.score > device_candidate.score
    assert (
        "runtime-validation-missing:audio_device_to_analysis_chop:top_output_present"
        in device_candidate.grounding_evidence
    )
    assert (
        "runtime-validation-missing:audio_device_to_analysis_chop:panel_state_readback"
        in device_candidate.grounding_evidence
    )
    assert "runtime_validation_missing:2" in device_candidate.explanation


def test_pattern_resolver_penalizes_promoted_traces_with_failed_runtime_probes():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
    )
    patterns = []
    for pattern in load_pattern_registry():
        if pattern.pattern_id == "audio_file_to_analysis_chop":
            patterns.append(
                pattern.model_copy(
                    update={
                        "promoted_from_trace": "trace:audio-file-feedback-clean",
                        "layout": {
                            **pattern.layout,
                            "trace_support_count": 1,
                            "support_trace_ids": ["trace:audio-file-feedback-clean"],
                            "runtime_validation": {
                                "required_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                                "passed_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                            },
                        },
                    }
                )
            )
        elif pattern.pattern_id == "audio_device_to_analysis_chop":
            patterns.append(
                pattern.model_copy(
                    update={
                        "promoted_from_trace": "trace:audio-device-feedback-failed-visual",
                        "layout": {
                            **pattern.layout,
                            "trace_support_count": 1,
                            "support_trace_ids": ["trace:audio-device-feedback-failed-visual"],
                            "runtime_validation": {
                                "required_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                                "passed_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                                "failed_probe_ids": [
                                    "cheap_visual_metrics",
                                ],
                                "failed_probe_statuses": {
                                    "cheap_visual_metrics": "runtime_fail",
                                },
                            },
                        },
                    }
                )
            )
        else:
            patterns.append(pattern)

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=patterns,
        available_ops=ALL_SEED_OPS | {"audiodeviceinCHOP"},
        device_sources={"audio_device"},
    )

    file_candidate = next(
        candidate for candidate in candidates if "audio_file_to_analysis_chop" in candidate.pattern_ids
    )
    device_candidate = next(
        candidate for candidate in candidates if "audio_device_to_analysis_chop" in candidate.pattern_ids
    )
    assert file_candidate.score > device_candidate.score
    assert (
        "runtime-validation-failed:audio_device_to_analysis_chop:cheap_visual_metrics:runtime_fail"
        in device_candidate.grounding_evidence
    )
    assert "runtime_validation_failed:1" in device_candidate.explanation


def test_pattern_resolver_does_not_let_support_hide_failed_runtime_probes():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
    )
    patterns = []
    for pattern in load_pattern_registry():
        if pattern.pattern_id == "audio_file_to_analysis_chop":
            patterns.append(
                pattern.model_copy(
                    update={
                        "promoted_from_trace": "trace:audio-file-feedback-clean",
                        "layout": {
                            **pattern.layout,
                            "trace_support_count": 1,
                            "support_trace_ids": ["trace:audio-file-feedback-clean"],
                            "runtime_validation": {
                                "required_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                                "passed_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                            },
                        },
                    }
                )
            )
        elif pattern.pattern_id == "audio_device_to_analysis_chop":
            patterns.append(
                pattern.model_copy(
                    update={
                        "promoted_from_trace": "trace:audio-device-feedback-supported-but-failed",
                        "layout": {
                            **pattern.layout,
                            "trace_support_count": 12,
                            "support_trace_ids": [
                                f"trace:audio-device-feedback-supported-but-failed-{index}"
                                for index in range(12)
                            ],
                            "runtime_validation": {
                                "required_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                                "passed_probe_ids": [
                                    "audio_signal_activity",
                                    "feedback_output_readback",
                                ],
                                "failed_probe_ids": [
                                    "cheap_visual_metrics",
                                ],
                                "failed_probe_statuses": {
                                    "cheap_visual_metrics": "runtime_fail",
                                },
                            },
                        },
                    }
                )
            )
        else:
            patterns.append(pattern)

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=patterns,
        available_ops=ALL_SEED_OPS | {"audiodeviceinCHOP"},
        device_sources={"audio_device"},
    )

    file_candidate = next(
        candidate for candidate in candidates if "audio_file_to_analysis_chop" in candidate.pattern_ids
    )
    device_candidate = next(
        candidate for candidate in candidates if "audio_device_to_analysis_chop" in candidate.pattern_ids
    )
    assert file_candidate.score > device_candidate.score
    assert "runtime_validation_failed:1" in device_candidate.explanation
    assert (
        "runtime-validation-failed:audio_device_to_analysis_chop:cheap_visual_metrics:runtime_fail"
        in device_candidate.grounding_evidence
    )


def test_pattern_resolver_marks_device_candidate_without_device_source():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
    )

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=load_pattern_registry(),
        available_ops=ALL_SEED_OPS | {"audiodeviceinCHOP"},
        device_sources=set(),
    )

    device_candidates = [
        candidate for candidate in candidates if "audio_device_to_analysis_chop" in candidate.pattern_ids
    ]
    assert device_candidates
    assert "device-source-required" in device_candidates[0].risk_flags
    assert device_candidates[0].score < candidates[0].score


def test_pattern_resolver_uses_required_addons_in_availability_scoring():
    compiled = compile_visual_task(
        "Build a particle field with stable TOP preview and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(POP_PREVIEW_OPS | {"textDAT"}),
    )
    registry = load_pattern_registry()
    patterns = [
        pattern.model_copy(update={"required_addons": ["POPX"]})
        if pattern.pattern_id == "pop_particle_field_preview"
        else pattern
        for pattern in registry
    ]
    available_ops = POP_PREVIEW_OPS | {"textDAT"}
    missing_addon_matrix = build_operator_availability_matrix(
        available_ops,
        required_ops=sorted(available_ops),
        td_build="2025.32820",
        platform="macOS",
        installed_addons=[],
    )
    installed_addon_matrix = build_operator_availability_matrix(
        available_ops,
        required_ops=sorted(available_ops),
        td_build="2025.32820",
        platform="macOS",
        installed_addons=["POPX"],
    )

    missing_candidates = resolve_candidate_graphs(
        compiled,
        patterns=patterns,
        availability_matrix=missing_addon_matrix,
    )
    installed_candidates = resolve_candidate_graphs(
        compiled,
        patterns=patterns,
        availability_matrix=installed_addon_matrix,
    )

    assert missing_candidates
    assert installed_candidates
    assert "missing-addon:POPX" in missing_candidates[0].risk_flags
    assert "addon-required:POPX" in missing_candidates[0].grounding_evidence
    assert "missing-addon:POPX" not in installed_candidates[0].risk_flags
    assert "addon-installed:POPX" in installed_candidates[0].grounding_evidence
    assert installed_candidates[0].score > missing_candidates[0].score


def test_pattern_resolver_prefers_available_device_substitution_when_file_audio_missing():
    available_ops = (ALL_SEED_OPS - {"audiofileinCHOP"}) | {"audiodeviceinCHOP"}
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(available_ops | {"audiofileinCHOP"}),
    )
    matrix = build_operator_availability_matrix(
        available_ops,
        required_ops=sorted(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
        td_build="2025.32820",
        platform="macOS",
    )

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=load_pattern_registry(),
        availability_matrix=matrix,
        device_sources={"audio_device"},
    )

    assert "audio_device_to_analysis_chop" in candidates[0].pattern_ids
    assert "substitution:audiofileinCHOP->audio_device_to_analysis_chop" in candidates[0].grounding_evidence
    assert (
        "substitution-rule:audiofileinCHOP->audiodeviceinCHOP:medium:requires-approval"
        in candidates[0].grounding_evidence
    )
    assert "device-source-declared:audio_device" in candidates[0].grounding_evidence
    assert "availability:td_build:2025.32820" in candidates[0].grounding_evidence
    assert "availability:platform:macOS" in candidates[0].grounding_evidence
    assert "missing-op:audiodeviceinCHOP" not in candidates[0].risk_flags


def test_pattern_resolver_surfaces_unapproved_available_audio_device_substitution():
    available_ops = (ALL_SEED_OPS - {"audiofileinCHOP"}) | {"audiodeviceinCHOP"}
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(available_ops | {"audiofileinCHOP"}),
    )
    matrix = build_operator_availability_matrix(
        available_ops,
        required_ops=sorted(ALL_SEED_OPS | {"audiodeviceinCHOP"}),
        td_build="2025.32820",
        platform="macOS",
    )

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=load_pattern_registry(),
        availability_matrix=matrix,
        device_sources={"midi_device"},
    )

    assert "audio_device_to_analysis_chop" in candidates[0].pattern_ids
    assert "device-source-required" in candidates[0].risk_flags
    assert "missing-op:audiofileinCHOP" not in candidates[0].risk_flags
    assert "substitution:audiofileinCHOP->audio_device_to_analysis_chop:pending-approval" in (
        candidates[0].grounding_evidence
    )
    assert "substitution-rule:audiofileinCHOP->audiodeviceinCHOP:medium:requires-approval" in (
        candidates[0].grounding_evidence
    )


def test_pattern_resolver_applies_generic_official_replacement_to_candidate_graph():
    available_ops = {"webclientDAT", "nullDAT"}
    compiled = compile_visual_task(
        "Build a serial DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex({"webDAT", "webclientDAT", "nullDAT"}),
    )
    registry = []
    for pattern in load_pattern_registry():
        if pattern.pattern_id != "serial_dat_protocol_bridge":
            registry.append(pattern)
            continue
        registry.append(
            pattern.model_copy(
                update={
                    "required_ops": ["webDAT", "nullDAT"],
                    "concept_nodes": [
                        node.model_copy(update={"op_type": "webDAT", "evidence": ["docs:webDAT"]})
                        if node.id == "serial_source"
                        else node
                        for node in pattern.concept_nodes
                    ],
                    "official_sources": [
                        "https://docs.derivative.ca/Web_DAT",
                        "https://docs.derivative.ca/Web_Client_DAT",
                        "https://docs.derivative.ca/Null_DAT",
                    ],
                }
            )
        )
    matrix = build_operator_availability_matrix(
        available_ops,
        required_ops=["webDAT", "webclientDAT", "nullDAT"],
        td_build="2025.32820",
        platform="macOS",
    )

    candidates = resolve_candidate_graphs(
        compiled,
        patterns=registry,
        availability_matrix=matrix,
        device_sources={"serial_device"},
    )

    assert len(candidates) >= 2
    substituted = candidates[0]
    original = next(candidate for candidate in candidates if "webDAT" in candidate.required_ops)
    assert substituted.score > original.score
    assert "webDAT" not in substituted.required_ops
    assert "webclientDAT" in substituted.required_ops
    assert all(node.op_type != "webDAT" for node in substituted.concepts)
    assert any(node.op_type == "webclientDAT" for node in substituted.concepts)
    assert "missing-op:webDAT" not in substituted.risk_flags
    assert "substitution:webDAT->webclientDAT" in substituted.grounding_evidence
    assert "substitution-rule:webDAT->webclientDAT:high" in substituted.grounding_evidence
    assert "webclientDAT" not in original.required_ops
    assert "missing-op:webDAT" in original.risk_flags
