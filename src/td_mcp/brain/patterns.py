"""Small Phase 1 pattern registry for concept-to-node planning."""

from __future__ import annotations

import json
from pathlib import Path

from td_mcp.models.brain import BrainPattern, ConceptEdge, ConceptNode


def load_pattern_registry() -> list[BrainPattern]:
    """Load the built-in Phase 1 seed patterns."""
    return [BrainPattern(**item) for item in _DEFAULT_PATTERNS]


def load_pattern_registry_from_json(path: str | Path) -> list[BrainPattern]:
    """Load and validate pattern records from a JSON list or {"patterns": [...]} object."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload.get("patterns") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("pattern registry JSON must be a list or an object with a patterns list")
    return [BrainPattern.model_validate(record) for record in records]


def patterns_by_id(patterns: list[BrainPattern] | None = None) -> dict[str, BrainPattern]:
    """Return pattern registry entries keyed by stable pattern id."""
    return {pattern.pattern_id: pattern for pattern in (patterns or load_pattern_registry())}


def docs_evidence_for_patterns(patterns: list[BrainPattern]) -> list[str]:
    """Return stable docs evidence markers for pattern required operators."""
    evidence: list[str] = []
    for pattern in patterns:
        evidence.append(f"pattern:{pattern.pattern_id}")
        for op_type in pattern.required_ops:
            evidence.append(f"docs:{op_type}")
        if pattern.promoted_from_trace:
            evidence.append(f"trace-promoted:{pattern.promoted_from_trace}")
            layout = pattern.layout if isinstance(pattern.layout, dict) else {}
            trace_fingerprint = str(layout.get("trace_fingerprint") or "").strip()
            if trace_fingerprint:
                evidence.append(f"trace-fingerprint:{trace_fingerprint}")
            support_count = _trace_support_count(layout)
            if support_count:
                evidence.append(f"trace-support:{support_count}")
            runtime_count = _trace_runtime_validation_count(layout)
            if runtime_count:
                evidence.append(f"trace-runtime-validation:{runtime_count}")
    return list(dict.fromkeys(evidence))


def pattern_id_aliases(pattern_id: str) -> tuple[str, ...]:
    """Return compatibility aliases for patterns renamed into master-plan terms."""
    return _PATTERN_ALIASES.get(pattern_id, ())


_PATTERN_ALIASES = {
    "audio_file_to_analysis_chop": ("audio_analysis_chop_chain",),
    "feedback_decay_top_loop": ("feedback_top_loop",),
    "panel_controls_to_chop_output": ("panel_control_output",),
}


def _trace_support_count(layout: dict) -> int:
    raw = layout.get("trace_support_count")
    if isinstance(raw, int) and raw > 0:
        return raw
    support_trace_ids = layout.get("support_trace_ids")
    if isinstance(support_trace_ids, list):
        return len([item for item in support_trace_ids if str(item).strip()])
    return 0


def _trace_runtime_validation_count(layout: dict) -> int:
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


_DEFAULT_PATTERNS = [
    {
        "pattern_id": "audio_file_to_analysis_chop",
        "title": "Audio File To Analysis CHOP",
        "intent_tags": ["audio", "audio-reactive", "analysis", "control"],
        "profiles": ["audio_reactive"],
        "required_ops": ["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"],
        "optional_ops": ["audiospectrumCHOP"],
        "concept_nodes": [
            ConceptNode(
                id="audio_source",
                label="Audio file input",
                role="source",
                domain="CHOP",
                op_type="audiofileinCHOP",
                evidence=["docs:audiofileinCHOP"],
            ),
            ConceptNode(
                id="audio_analyze",
                label="Signal analysis",
                role="process",
                domain="CHOP",
                op_type="analyzeCHOP",
                params={"function": "RMS Power", "allowstart": False, "allowend": False, "valleys": False},
                evidence=["docs:analyzeCHOP"],
            ),
            ConceptNode(
                id="audio_math",
                label="Range shaping",
                role="process",
                domain="CHOP",
                op_type="mathCHOP",
                params={"fromrange": (0.0, 1.0), "torange": (0.0, 1.0), "interppars": True},
                evidence=["docs:mathCHOP"],
            ),
            ConceptNode(
                id="audio_out",
                label="Audio control output",
                role="output",
                domain="CHOP",
                op_type="nullCHOP",
                evidence=["docs:nullCHOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="audio_source", target="audio_analyze", kind="data"),
            ConceptEdge(source="audio_analyze", target="audio_math", kind="data"),
            ConceptEdge(source="audio_math", target="audio_out", kind="data"),
        ],
        "exposes": [{"port_id": "analysis_chop", "domain": "CHOP", "node_id": "audio_out"}],
        "consumes": [],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "audio_out", "domain": "CHOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "audio_source_present",
            "analysis_stage",
            "range_mapping",
            "audio_signal_activity",
        ],
        "rollback_risks": [],
        "official_sources": [
            "https://docs.derivative.ca/Audio_File_In_CHOP",
            "https://docs.derivative.ca/Analyze_CHOP",
            "https://docs.derivative.ca/Math_CHOP",
            "https://docs.derivative.ca/Null_CHOP",
        ],
    },
    {
        "pattern_id": "audio_device_to_analysis_chop",
        "title": "Audio Device To Analysis CHOP",
        "intent_tags": ["audio", "audio-reactive", "analysis", "device", "control"],
        "profiles": ["audio_reactive"],
        "required_ops": ["audiodeviceinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"],
        "optional_ops": ["audiospectrumCHOP"],
        "concept_nodes": [
            ConceptNode(
                id="audio_device_source",
                label="Audio device input",
                role="source",
                domain="CHOP",
                op_type="audiodeviceinCHOP",
                params={"active": True, "errormissing": True, "format": "stereo"},
                evidence=["docs:audiodeviceinCHOP"],
            ),
            ConceptNode(
                id="device_audio_analyze",
                label="Device signal analysis",
                role="process",
                domain="CHOP",
                op_type="analyzeCHOP",
                params={"function": "RMS Power", "allowstart": False, "allowend": False, "valleys": False},
                evidence=["docs:analyzeCHOP"],
            ),
            ConceptNode(
                id="device_audio_math",
                label="Device range shaping",
                role="process",
                domain="CHOP",
                op_type="mathCHOP",
                params={"fromrange": (0.0, 1.0), "torange": (0.0, 1.0), "interppars": True},
                evidence=["docs:mathCHOP"],
            ),
            ConceptNode(
                id="device_audio_out",
                label="Device audio control output",
                role="output",
                domain="CHOP",
                op_type="nullCHOP",
                evidence=["docs:nullCHOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="audio_device_source", target="device_audio_analyze", kind="data"),
            ConceptEdge(source="device_audio_analyze", target="device_audio_math", kind="data"),
            ConceptEdge(source="device_audio_math", target="device_audio_out", kind="data"),
        ],
        "exposes": [{"port_id": "analysis_chop", "domain": "CHOP", "node_id": "device_audio_out"}],
        "consumes": [{"port_id": "audio_device", "domain": "CHOP"}],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "device_audio_out", "domain": "CHOP"}],
        "safety": "device_dependent",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "audio_source_present",
            "analysis_stage",
            "range_mapping",
            "audio_signal_activity",
        ],
        "rollback_risks": ["device-source-required"],
        "official_sources": [
            "https://docs.derivative.ca/Audio_Device_In_CHOP",
            "https://docs.derivative.ca/Analyze_CHOP",
            "https://docs.derivative.ca/Math_CHOP",
            "https://docs.derivative.ca/Null_CHOP",
        ],
    },
    {
        "pattern_id": "audio_analysis_chop_chain",
        "title": "Audio Analysis CHOP Chain",
        "intent_tags": ["audio", "audio-reactive", "analysis", "control"],
        "profiles": ["audio_reactive"],
        "required_ops": ["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"],
        "optional_ops": ["audiodeviceinCHOP", "audiospectrumCHOP"],
        "concept_nodes": [
            ConceptNode(
                id="audio_source",
                label="Audio input",
                role="source",
                domain="CHOP",
                op_type="audiofileinCHOP",
                evidence=["docs:audiofileinCHOP"],
            ),
            ConceptNode(
                id="audio_analyze",
                label="Signal analysis",
                role="process",
                domain="CHOP",
                op_type="analyzeCHOP",
                params={"function": "RMS Power", "allowstart": False, "allowend": False, "valleys": False},
                evidence=["docs:analyzeCHOP"],
            ),
            ConceptNode(
                id="audio_math",
                label="Range shaping",
                role="process",
                domain="CHOP",
                op_type="mathCHOP",
                params={"fromrange": (0.0, 1.0), "torange": (0.0, 1.0), "interppars": True},
                evidence=["docs:mathCHOP"],
            ),
            ConceptNode(
                id="audio_out",
                label="Audio control output",
                role="output",
                domain="CHOP",
                op_type="nullCHOP",
                evidence=["docs:nullCHOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="audio_source", target="audio_analyze", kind="data"),
            ConceptEdge(source="audio_analyze", target="audio_math", kind="data"),
            ConceptEdge(source="audio_math", target="audio_out", kind="data"),
        ],
        "exposes": [{"port_id": "analysis_chop", "domain": "CHOP", "node_id": "audio_out"}],
        "consumes": [],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "audio_out", "domain": "CHOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "audio_source_present",
            "analysis_stage",
            "range_mapping",
            "audio_signal_activity",
        ],
        "rollback_risks": [],
        "official_sources": [
            "https://docs.derivative.ca/Audio_File_In_CHOP",
            "https://docs.derivative.ca/Analyze_CHOP",
            "https://docs.derivative.ca/Math_CHOP",
            "https://docs.derivative.ca/Null_CHOP",
        ],
    },
    {
        "pattern_id": "feedback_decay_top_loop",
        "title": "Feedback Decay TOP Loop",
        "intent_tags": ["feedback", "trail", "visual", "top"],
        "profiles": ["feedback"],
        "required_ops": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
        "optional_ops": [],
        "concept_nodes": [
            ConceptNode(
                id="feedback_source",
                label="Noise source",
                role="source",
                domain="TOP",
                op_type="noiseTOP",
                evidence=["docs:noiseTOP"],
            ),
            ConceptNode(
                id="feedback_buffer",
                label="Feedback buffer",
                role="feedback",
                domain="TOP",
                op_type="feedbackTOP",
                evidence=["docs:feedbackTOP"],
            ),
            ConceptNode(
                id="feedback_decay",
                label="Decay and level",
                role="process",
                domain="TOP",
                op_type="levelTOP",
                params={"opacity": 0.92},
                evidence=["docs:levelTOP"],
            ),
            ConceptNode(
                id="feedback_composite",
                label="Composite merge",
                role="process",
                domain="TOP",
                op_type="compositeTOP",
                evidence=["docs:compositeTOP"],
            ),
            ConceptNode(
                id="stable_output",
                label="Stable TOP output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
                evidence=["docs:nullTOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="feedback_source", target="feedback_composite", kind="data"),
            ConceptEdge(source="feedback_buffer", target="feedback_decay", kind="feedback"),
            ConceptEdge(source="feedback_decay", target="feedback_composite", target_index=1, kind="data"),
            ConceptEdge(source="feedback_composite", target="feedback_buffer", kind="feedback"),
            ConceptEdge(source="feedback_composite", target="stable_output", kind="data"),
        ],
        "exposes": [{"port_id": "stable_top", "domain": "TOP", "node_id": "stable_output"}],
        "consumes": [{"port_id": "analysis_chop", "domain": "CHOP", "target_node_id": "feedback_decay"}],
        "parameters": [
            {
                "name": "feedback_decay",
                "target_node_id": "feedback_decay",
                "target_param": "opacity",
                "value_kind": "float",
                "default": 0.92,
                "control_type": "slider",
            }
        ],
        "layout": {"column": 1},
        "debug_outputs": [{"node": "stable_output", "domain": "TOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "feedback_cycle",
            "decay_control",
            "feedback_output_readback",
            "cheap_visual_metrics",
        ],
        "rollback_risks": ["unbounded_feedback_without_decay"],
        "official_sources": [
            "https://docs.derivative.ca/Noise_TOP",
            "https://docs.derivative.ca/Feedback_TOP",
            "https://docs.derivative.ca/Level_TOP",
            "https://docs.derivative.ca/Composite_TOP",
            "https://docs.derivative.ca/Null_TOP",
        ],
    },
    {
        "pattern_id": "feedback_top_loop",
        "title": "Feedback TOP Loop",
        "intent_tags": ["feedback", "trail", "visual", "top"],
        "profiles": ["feedback"],
        "required_ops": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
        "optional_ops": [],
        "concept_nodes": [
            ConceptNode(
                id="feedback_source",
                label="Noise source",
                role="source",
                domain="TOP",
                op_type="noiseTOP",
                evidence=["docs:noiseTOP"],
            ),
            ConceptNode(
                id="feedback_buffer",
                label="Feedback buffer",
                role="feedback",
                domain="TOP",
                op_type="feedbackTOP",
                evidence=["docs:feedbackTOP"],
            ),
            ConceptNode(
                id="feedback_decay",
                label="Decay and level",
                role="process",
                domain="TOP",
                op_type="levelTOP",
                params={"opacity": 0.92},
                evidence=["docs:levelTOP"],
            ),
            ConceptNode(
                id="feedback_composite",
                label="Composite merge",
                role="process",
                domain="TOP",
                op_type="compositeTOP",
                evidence=["docs:compositeTOP"],
            ),
            ConceptNode(
                id="stable_output",
                label="Stable TOP output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
                evidence=["docs:nullTOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="feedback_source", target="feedback_composite", kind="data"),
            ConceptEdge(source="feedback_buffer", target="feedback_decay", kind="feedback"),
            ConceptEdge(source="feedback_decay", target="feedback_composite", target_index=1, kind="data"),
            ConceptEdge(source="feedback_composite", target="feedback_buffer", kind="feedback"),
            ConceptEdge(source="feedback_composite", target="stable_output", kind="data"),
        ],
        "exposes": [{"port_id": "stable_top", "domain": "TOP", "node_id": "stable_output"}],
        "consumes": [{"port_id": "analysis_chop", "domain": "CHOP", "target_node_id": "feedback_decay"}],
        "parameters": [
            {
                "name": "feedback_decay",
                "target_node_id": "feedback_decay",
                "target_param": "opacity",
                "value_kind": "float",
                "default": 0.92,
                "control_type": "slider",
            }
        ],
        "layout": {"column": 1},
        "debug_outputs": [{"node": "stable_output", "domain": "TOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "feedback_cycle",
            "decay_control",
            "feedback_output_readback",
            "cheap_visual_metrics",
        ],
        "rollback_risks": ["unbounded_feedback_without_decay"],
        "official_sources": [
            "https://docs.derivative.ca/Noise_TOP",
            "https://docs.derivative.ca/Feedback_TOP",
            "https://docs.derivative.ca/Level_TOP",
            "https://docs.derivative.ca/Composite_TOP",
            "https://docs.derivative.ca/Null_TOP",
        ],
    },
    {
        "pattern_id": "panel_controls_to_chop_output",
        "title": "Panel Controls To CHOP Output",
        "intent_tags": ["panel", "ui", "controls", "slider", "button"],
        "profiles": ["panel_ui"],
        "required_ops": ["containerCOMP", "sliderCOMP", "buttonCOMP", "panelCHOP", "nullCHOP"],
        "optional_ops": [],
        "concept_nodes": [
            ConceptNode(
                id="panel_container",
                label="Panel container",
                role="ui",
                domain="COMP",
                op_type="containerCOMP",
                evidence=["docs:containerCOMP"],
            ),
            ConceptNode(
                id="panel_slider",
                label="Continuous control",
                role="ui",
                domain="COMP",
                op_type="sliderCOMP",
                evidence=["docs:sliderCOMP"],
            ),
            ConceptNode(
                id="panel_button",
                label="Discrete trigger",
                role="ui",
                domain="COMP",
                op_type="buttonCOMP",
                evidence=["docs:buttonCOMP"],
            ),
            ConceptNode(
                id="panel_reader",
                label="Panel state reader",
                role="control",
                domain="CHOP",
                op_type="panelCHOP",
                params={"component": "${path:panel_container}"},
                evidence=["docs:panelCHOP"],
            ),
            ConceptNode(
                id="panel_out",
                label="Panel control output",
                role="output",
                domain="CHOP",
                op_type="nullCHOP",
                evidence=["docs:nullCHOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="panel_container", target="panel_reader", kind="reference"),
            ConceptEdge(source="panel_reader", target="panel_out", kind="data"),
        ],
        "exposes": [{"port_id": "panel_chop", "domain": "CHOP", "node_id": "panel_out"}],
        "consumes": [],
        "parameters": [
            {
                "name": "panel_reader_component",
                "target_node_id": "panel_reader",
                "target_param": "component",
                "value_kind": "op_reference",
                "expected_family": "COMP",
                "default": "${path:panel_container}",
                "control_type": "operator_reference",
            }
        ],
        "layout": {"column": 2},
        "debug_outputs": [{"node": "panel_out", "domain": "CHOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "panel_components_present",
            "panel_state_reader",
            "panel_state_readback",
            "control_output",
        ],
        "rollback_risks": [],
        "official_sources": [
            "https://docs.derivative.ca/Container_COMP",
            "https://docs.derivative.ca/Slider_COMP",
            "https://docs.derivative.ca/Button_COMP",
            "https://docs.derivative.ca/Panel_CHOP",
            "https://docs.derivative.ca/Null_CHOP",
        ],
    },
    {
        "pattern_id": "panel_control_output",
        "title": "Panel Control Output",
        "intent_tags": ["panel", "ui", "controls", "slider", "button"],
        "profiles": ["panel_ui"],
        "required_ops": ["containerCOMP", "sliderCOMP", "buttonCOMP", "panelCHOP", "nullCHOP"],
        "optional_ops": [],
        "concept_nodes": [
            ConceptNode(
                id="panel_container",
                label="Panel container",
                role="ui",
                domain="COMP",
                op_type="containerCOMP",
                evidence=["docs:containerCOMP"],
            ),
            ConceptNode(
                id="panel_slider",
                label="Continuous control",
                role="ui",
                domain="COMP",
                op_type="sliderCOMP",
                evidence=["docs:sliderCOMP"],
            ),
            ConceptNode(
                id="panel_button",
                label="Discrete trigger",
                role="ui",
                domain="COMP",
                op_type="buttonCOMP",
                evidence=["docs:buttonCOMP"],
            ),
            ConceptNode(
                id="panel_reader",
                label="Panel state reader",
                role="control",
                domain="CHOP",
                op_type="panelCHOP",
                params={"component": "${path:panel_container}"},
                evidence=["docs:panelCHOP"],
            ),
            ConceptNode(
                id="panel_out",
                label="Panel control output",
                role="output",
                domain="CHOP",
                op_type="nullCHOP",
                evidence=["docs:nullCHOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="panel_container", target="panel_reader", kind="reference"),
            ConceptEdge(source="panel_reader", target="panel_out", kind="data"),
        ],
        "exposes": [{"port_id": "panel_chop", "domain": "CHOP", "node_id": "panel_out"}],
        "consumes": [],
        "parameters": [
            {
                "name": "panel_reader_component",
                "target_node_id": "panel_reader",
                "target_param": "component",
                "value_kind": "op_reference",
                "expected_family": "COMP",
                "default": "${path:panel_container}",
                "control_type": "operator_reference",
            }
        ],
        "layout": {"column": 2},
        "debug_outputs": [{"node": "panel_out", "domain": "CHOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "panel_components_present",
            "panel_state_reader",
            "panel_state_readback",
            "control_output",
        ],
        "rollback_risks": [],
        "official_sources": [
            "https://docs.derivative.ca/Container_COMP",
            "https://docs.derivative.ca/Slider_COMP",
            "https://docs.derivative.ca/Button_COMP",
            "https://docs.derivative.ca/Panel_CHOP",
            "https://docs.derivative.ca/Null_CHOP",
        ],
    },
    {
        "pattern_id": "pop_particle_field_preview",
        "title": "POP Particle Field Preview",
        "intent_tags": ["pop", "particles", "field", "motion", "preview"],
        "profiles": ["pop"],
        "required_ops": ["circlePOP", "noisePOP", "mathmixPOP", "nullPOP", "rendersimpleTOP", "nullTOP"],
        "optional_ops": ["cachePOP"],
        "concept_nodes": [
            ConceptNode(
                id="emit",
                label="Particle emitter",
                role="source",
                domain="POP",
                op_type="circlePOP",
                evidence=["docs:circlePOP"],
            ),
            ConceptNode(
                id="motion",
                label="Particle motion field",
                role="process",
                domain="POP",
                op_type="noisePOP",
                evidence=["docs:noisePOP"],
            ),
            ConceptNode(
                id="shape",
                label="Attribute shaping",
                role="process",
                domain="POP",
                op_type="mathmixPOP",
                evidence=["docs:mathmixPOP"],
            ),
            ConceptNode(
                id="pop_out",
                label="Finite POP output",
                role="output",
                domain="POP",
                op_type="nullPOP",
                evidence=["docs:nullPOP"],
            ),
            ConceptNode(
                id="preview",
                label="POP render preview",
                role="render",
                domain="TOP",
                op_type="rendersimpleTOP",
                create_type="rendersimple",
                params={"pop": "${path:pop_out}", "normalizegeo": True},
                evidence=["docs:rendersimpleTOP"],
            ),
            ConceptNode(
                id="stable_output",
                label="Stable rendered output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
                evidence=["docs:nullTOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="emit", target="motion", kind="data"),
            ConceptEdge(source="motion", target="shape", kind="data"),
            ConceptEdge(source="shape", target="pop_out", kind="data"),
            ConceptEdge(source="pop_out", target="preview", kind="reference"),
            ConceptEdge(source="preview", target="stable_output", kind="data"),
        ],
        "exposes": [
            {"port_id": "stable_pop", "domain": "POP", "node_id": "pop_out"},
            {"port_id": "stable_top", "domain": "TOP", "node_id": "stable_output"},
        ],
        "consumes": [],
        "parameters": [],
        "layout": {"column": 1},
        "debug_outputs": [
            {"node": "pop_out", "domain": "POP"},
            {"node": "stable_output", "domain": "TOP"},
        ],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "pop_source_present",
            "pop_output_attached",
            "finite_pop_bounds",
            "attribute_sample_available",
        ],
        "rollback_risks": ["validate-finite-pop-bounds", "validate-pop-render-preview"],
        "official_sources": [
            "https://docs.derivative.ca/Circle_POP",
            "https://docs.derivative.ca/Noise_POP",
            "https://docs.derivative.ca/Math_Mix_POP",
            "https://docs.derivative.ca/Null_POP",
            "https://docs.derivative.ca/Render_Simple_TOP",
            "https://docs.derivative.ca/Null_TOP",
        ],
    },
    {
        "pattern_id": "glsl_advanced_pop_topology_shader",
        "title": "GLSL Advanced POP Topology Shader",
        "intent_tags": ["glsl", "pop", "topology", "output-count", "preview"],
        "profiles": ["glsl", "pop"],
        "required_ops": [
            "circlePOP",
            "glsladvancedPOP",
            "topologyPOP",
            "textDAT",
            "nullPOP",
            "rendersimpleTOP",
            "nullTOP",
        ],
        "optional_ops": ["glslselectPOP"],
        "concept_nodes": [
            ConceptNode(
                id="advanced_seed",
                label="Seed POP",
                role="source",
                domain="POP",
                op_type="circlePOP",
                evidence=["docs:circlePOP"],
            ),
            ConceptNode(
                id="advanced_shader",
                label="Topology-changing shader",
                role="process",
                domain="POP",
                op_type="glsladvancedPOP",
                create_type="glsladvancedPOP",
                params={"computedat": "${path:advanced_code}"},
                evidence=["docs:glsladvancedPOP"],
            ),
            ConceptNode(
                id="advanced_code",
                label="Advanced POP compute shader DAT",
                role="validator",
                domain="DAT",
                op_type="textDAT",
                content={
                    "text": (
                        "void main() {\n"
                        "    uint idx = TDIndex();\n"
                        "    if (idx >= TDNumElements()) {\n"
                        "        return;\n"
                        "    }\n"
                        "    P += vec3(0.0, 0.0, 0.0);\n"
                        "}\n"
                    )
                },
                generated_code={
                    "block_id": "glsl_advanced_pop_topology_shader",
                    "language": "glsl",
                    "target_op": "${path:advanced_shader}",
                    "target_param": "computedat",
                    "source_kind": "generated",
                    "source_refs": ["${path:advanced_code}"],
                    "static_checks": ["glsl_no_version_line", "glsl_pop_bounds_guard"],
                    "runtime_checks": ["compile_state", "topology_capacity"],
                    "expected_outputs": ["${path:advanced_out}", "${path:stable_output}"],
                    "risk_flags": ["validate-glsl-compile-state", "validate-finite-pop-bounds"],
                    "official_sources": [
                        "https://docs.derivative.ca/GLSL_Advanced_POP",
                        "https://docs.derivative.ca/Write_a_GLSL_POP",
                    ],
                },
                evidence=["docs:textDAT", "docs:glsladvancedPOP"],
            ),
            ConceptNode(
                id="topology",
                label="Topology capacity stage",
                role="process",
                domain="POP",
                op_type="topologyPOP",
                evidence=["docs:topologyPOP"],
            ),
            ConceptNode(
                id="advanced_out",
                label="Stable topology POP output",
                role="output",
                domain="POP",
                op_type="nullPOP",
                evidence=["docs:nullPOP"],
            ),
            ConceptNode(
                id="advanced_preview",
                label="Advanced POP render preview",
                role="render",
                domain="TOP",
                op_type="rendersimpleTOP",
                create_type="rendersimple",
                params={"pop": "${path:advanced_out}", "normalizegeo": True},
                evidence=["docs:rendersimpleTOP"],
            ),
            ConceptNode(
                id="stable_output",
                label="Stable rendered output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
                evidence=["docs:nullTOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="advanced_seed", target="advanced_shader", kind="data"),
            ConceptEdge(source="advanced_code", target="advanced_shader", kind="reference"),
            ConceptEdge(source="advanced_shader", target="topology", kind="data"),
            ConceptEdge(source="topology", target="advanced_out", kind="data"),
            ConceptEdge(source="advanced_out", target="advanced_preview", kind="reference"),
            ConceptEdge(source="advanced_preview", target="stable_output", kind="data"),
        ],
        "exposes": [
            {"port_id": "stable_pop", "domain": "POP", "node_id": "advanced_out"},
            {"port_id": "stable_top", "domain": "TOP", "node_id": "stable_output"},
        ],
        "consumes": [],
        "parameters": [{"name": "topology_capacity", "target_node_id": "topology"}],
        "layout": {"column": 1},
        "debug_outputs": [
            {"node": "advanced_out", "domain": "POP"},
            {"node": "stable_output", "domain": "TOP"},
        ],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "shader_source_present",
            "compile_state",
            "topology_capacity",
            "pop_output_attached",
            "finite_pop_bounds",
            "attribute_sample_available",
        ],
        "rollback_risks": ["validate-glsl-compile-state", "validate-finite-pop-bounds"],
        "official_sources": [
            "https://docs.derivative.ca/Circle_POP",
            "https://docs.derivative.ca/GLSL_Advanced_POP",
            "https://docs.derivative.ca/Topology_POP",
            "https://docs.derivative.ca/Text_DAT",
            "https://docs.derivative.ca/Null_POP",
            "https://docs.derivative.ca/Render_Simple_TOP",
            "https://docs.derivative.ca/Null_TOP",
            "https://docs.derivative.ca/Write_a_GLSL_POP",
        ],
    },
    {
        "pattern_id": "glsl_top_shader_with_text_dat",
        "title": "GLSL TOP Shader With Text DAT",
        "intent_tags": ["glsl", "shader", "top", "text-dat", "image-effect"],
        "profiles": ["glsl"],
        "required_ops": ["constantTOP", "glslTOP", "textDAT", "nullTOP"],
        "optional_ops": ["infoDAT", "errorDAT"],
        "concept_nodes": [
            ConceptNode(
                id="source",
                label="Input texture",
                role="source",
                domain="TOP",
                op_type="constantTOP",
                evidence=["docs:constantTOP"],
            ),
            ConceptNode(
                id="shader",
                label="GLSL shader TOP",
                role="process",
                domain="TOP",
                op_type="glslTOP",
                create_type="glsl",
                params={"pixeldat": "${path:shader_code}", "glslversion": "glsl460"},
                evidence=["docs:glslTOP"],
            ),
            ConceptNode(
                id="shader_code",
                label="Shader source DAT",
                role="validator",
                domain="DAT",
                op_type="textDAT",
                content={
                    "text": (
                        "layout(location = 0) out vec4 fragColor;\n"
                        "void main() {\n"
                        "    vec2 uv = vUV.st;\n"
                        "    fragColor = TDOutputSwizzle(vec4(uv, 0.5, 1.0));\n"
                        "}\n"
                    )
                },
                generated_code={
                    "block_id": "glsl_top_shader_with_text_dat",
                    "language": "glsl",
                    "target_op": "${path:shader}",
                    "target_param": "pixeldat",
                    "source_kind": "generated",
                    "source_refs": ["${path:shader_code}"],
                    "static_checks": [
                        "glsl_no_version_line",
                        "glsl_top_declares_pixel_output",
                        "glsl_top_uses_td_output_swizzle",
                    ],
                    "runtime_checks": ["compile_state"],
                    "expected_outputs": ["${path:stable_output}"],
                    "risk_flags": ["validate-glsl-compile-state"],
                    "official_sources": [
                        "https://docs.derivative.ca/GLSL_TOP",
                        "https://docs.derivative.ca/Write_a_GLSL_TOP",
                    ],
                },
                evidence=["docs:textDAT", "docs:glslTOP"],
            ),
            ConceptNode(
                id="stable_output",
                label="Stable shader output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
                evidence=["docs:nullTOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="source", target="shader", kind="data"),
            ConceptEdge(source="shader_code", target="shader", kind="reference"),
            ConceptEdge(source="shader", target="stable_output", kind="data"),
        ],
        "exposes": [{"port_id": "stable_top", "domain": "TOP", "node_id": "stable_output"}],
        "consumes": [],
        "parameters": [],
        "layout": {"column": 1},
        "debug_outputs": [{"node": "stable_output", "domain": "TOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["shader_source_present", "compile_state", "sampler_uniforms"],
        "rollback_risks": ["validate-glsl-compile-state"],
        "official_sources": [
            "https://docs.derivative.ca/Constant_TOP",
            "https://docs.derivative.ca/GLSL_TOP",
            "https://docs.derivative.ca/Text_DAT",
            "https://docs.derivative.ca/Null_TOP",
            "https://docs.derivative.ca/Write_a_GLSL_TOP",
        ],
    },
    {
        "pattern_id": "glsl_material_render_pipeline",
        "title": "GLSL Material Render Pipeline",
        "intent_tags": ["3d", "render", "material", "glsl", "camera", "geometry"],
        "profiles": ["render_pipeline", "glsl_material"],
        "required_ops": ["geometryCOMP", "cameraCOMP", "glslMAT", "textDAT", "renderTOP", "nullTOP"],
        "optional_ops": ["lightCOMP"],
        "concept_nodes": [
            ConceptNode(
                id="geo",
                label="Material geometry",
                role="render",
                domain="COMP",
                op_type="geometryCOMP",
                params={"material": "${path:material}"},
                evidence=["docs:geometryCOMP"],
            ),
            ConceptNode(
                id="camera",
                label="Render camera",
                role="render",
                domain="COMP",
                op_type="cameraCOMP",
                evidence=["docs:cameraCOMP"],
            ),
            ConceptNode(
                id="material",
                label="GLSL material",
                role="material",
                domain="MAT",
                op_type="glslMAT",
                create_type="glslMAT",
                params={
                    "vdat": "${path:vertex_code}",
                    "pdat": "${path:pixel_code}",
                    "glslversion": "glsl460",
                },
                evidence=["docs:glslMAT"],
            ),
            ConceptNode(
                id="vertex_code",
                label="Vertex shader DAT",
                role="validator",
                domain="DAT",
                op_type="textDAT",
                content={
                    "text": ("void TDVertex() {\n    gl_Position = TDWorldToProj(TDDeform(TDPos()));\n}\n")
                },
                generated_code={
                    "block_id": "glsl_material_vertex_shader",
                    "language": "glsl",
                    "target_op": "${path:material}",
                    "target_param": "vdat",
                    "source_kind": "generated",
                    "source_refs": ["${path:vertex_code}"],
                    "static_checks": ["glsl_no_version_line", "glsl_mat_vertex_shader"],
                    "runtime_checks": ["compile_state"],
                    "expected_outputs": ["${path:render_output}"],
                    "risk_flags": ["validate-glsl-compile-state"],
                    "official_sources": [
                        "https://docs.derivative.ca/GLSL_MAT",
                        "https://docs.derivative.ca/Write_a_GLSL_MAT",
                    ],
                },
                evidence=["docs:textDAT"],
            ),
            ConceptNode(
                id="pixel_code",
                label="Pixel shader DAT",
                role="validator",
                domain="DAT",
                op_type="textDAT",
                content={
                    "text": (
                        "out vec4 fragColor;\n"
                        "void TDFragment() {\n"
                        "    fragColor = TDOutputSwizzle(vec4(0.72, 0.9, 1.0, 1.0));\n"
                        "}\n"
                    )
                },
                generated_code={
                    "block_id": "glsl_material_pixel_shader",
                    "language": "glsl",
                    "target_op": "${path:material}",
                    "target_param": "pdat",
                    "source_kind": "generated",
                    "source_refs": ["${path:pixel_code}"],
                    "static_checks": ["glsl_no_version_line", "glsl_mat_pixel_shader"],
                    "runtime_checks": ["compile_state"],
                    "expected_outputs": ["${path:render_output}"],
                    "risk_flags": ["validate-glsl-compile-state"],
                    "official_sources": [
                        "https://docs.derivative.ca/GLSL_MAT",
                        "https://docs.derivative.ca/Write_a_GLSL_MAT",
                    ],
                },
                evidence=["docs:textDAT"],
            ),
            ConceptNode(
                id="render",
                label="Rendered material",
                role="render",
                domain="TOP",
                op_type="renderTOP",
                params={"camera": "${path:camera}", "geometry": "${path:geo}"},
                evidence=["docs:renderTOP"],
            ),
            ConceptNode(
                id="render_output",
                label="Stable render output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
                evidence=["docs:nullTOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="material", target="geo", kind="reference"),
            ConceptEdge(source="vertex_code", target="material", kind="reference"),
            ConceptEdge(source="pixel_code", target="material", kind="reference"),
            ConceptEdge(source="geo", target="render", kind="reference"),
            ConceptEdge(source="camera", target="render", kind="reference"),
            ConceptEdge(source="render", target="render_output", kind="data"),
        ],
        "exposes": [{"port_id": "stable_top", "domain": "TOP", "node_id": "render_output"}],
        "consumes": [
            {"port_id": "analysis_chop", "domain": "CHOP", "target_node_id": "material"},
            {"port_id": "terrain_sop", "domain": "SOP", "target_node_id": "geo"},
        ],
        "parameters": [
            {"name": "material_modulation", "source_port": "analysis_chop", "target_node_id": "material"}
        ],
        "layout": {"column": 1},
        "debug_outputs": [{"node": "render_output", "domain": "TOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "shader_source_present",
            "material_assigned",
            "compile_state",
            "camera_present",
            "geometry_present",
            "camera_frustum_coverage",
            "render_top_output",
        ],
        "rollback_risks": ["validate-glsl-compile-state", "validate-material-assignment"],
        "official_sources": [
            "https://docs.derivative.ca/Geometry_COMP",
            "https://docs.derivative.ca/Camera_COMP",
            "https://docs.derivative.ca/GLSL_MAT",
            "https://docs.derivative.ca/Text_DAT",
            "https://docs.derivative.ca/Render_TOP",
            "https://docs.derivative.ca/Null_TOP",
        ],
    },
    {
        "pattern_id": "sop_noise_terrain_surface",
        "title": "SOP Noise Terrain Surface",
        "intent_tags": ["terrain", "landscape", "heightfield", "sop", "surface"],
        "profiles": ["render_pipeline"],
        "required_ops": ["gridSOP", "noiseSOP", "nullSOP"],
        "optional_ops": [],
        "concept_nodes": [
            ConceptNode(
                id="terrain_grid",
                label="Terrain grid surface",
                role="source",
                domain="SOP",
                op_type="gridSOP",
                params={"rows": 80, "cols": 80, "sizex": 10, "sizey": 10},
                evidence=["docs:gridSOP"],
            ),
            ConceptNode(
                id="terrain_noise",
                label="Terrain displacement noise",
                role="process",
                domain="SOP",
                op_type="noiseSOP",
                params={"amp": 0.35},
                evidence=["docs:noiseSOP"],
            ),
            ConceptNode(
                id="terrain_out",
                label="Stable terrain SOP output",
                role="output",
                domain="SOP",
                op_type="nullSOP",
                evidence=["docs:nullSOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="terrain_grid", target="terrain_noise", kind="data"),
            ConceptEdge(source="terrain_noise", target="terrain_out", kind="data"),
        ],
        "exposes": [{"port_id": "terrain_sop", "domain": "SOP", "node_id": "terrain_out"}],
        "consumes": [],
        "parameters": [],
        "layout": {"column": 3},
        "debug_outputs": [{"node": "terrain_out", "domain": "SOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["output_node_present"],
        "rollback_risks": [],
        "official_sources": [
            "https://docs.derivative.ca/Grid_SOP",
            "https://docs.derivative.ca/Noise_SOP",
            "https://docs.derivative.ca/Null_SOP",
        ],
    },
    {
        "pattern_id": "render_geo_camera_light_output",
        "title": "Geometry Camera Light Render Output",
        "intent_tags": ["render", "geometry", "camera", "light", "top-output"],
        "profiles": ["render_pipeline"],
        "required_ops": ["geometryCOMP", "cameraCOMP", "lightCOMP", "renderTOP", "nullTOP"],
        "optional_ops": ["constantMAT", "phongMAT"],
        "concept_nodes": [
            ConceptNode(
                id="geo",
                label="Render geometry",
                role="render",
                domain="COMP",
                op_type="geometryCOMP",
                evidence=["docs:geometryCOMP"],
            ),
            ConceptNode(
                id="camera",
                label="Render camera",
                role="render",
                domain="COMP",
                op_type="cameraCOMP",
                evidence=["docs:cameraCOMP"],
            ),
            ConceptNode(
                id="light",
                label="Scene light",
                role="render",
                domain="COMP",
                op_type="lightCOMP",
                evidence=["docs:lightCOMP"],
            ),
            ConceptNode(
                id="render",
                label="Rendered scene",
                role="render",
                domain="TOP",
                op_type="renderTOP",
                params={"camera": "${path:camera}", "geometry": "${path:geo}", "lights": "${path:light}"},
                evidence=["docs:renderTOP"],
            ),
            ConceptNode(
                id="stable_output",
                label="Stable render output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
                evidence=["docs:nullTOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="geo", target="render", kind="reference"),
            ConceptEdge(source="camera", target="render", kind="reference"),
            ConceptEdge(source="light", target="render", kind="reference"),
            ConceptEdge(source="render", target="stable_output", kind="data"),
        ],
        "exposes": [{"port_id": "stable_top", "domain": "TOP", "node_id": "stable_output"}],
        "consumes": [],
        "parameters": [],
        "layout": {"column": 1},
        "debug_outputs": [{"node": "stable_output", "domain": "TOP"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "camera_present",
            "geometry_present",
            "material_or_default",
            "camera_frustum_coverage",
            "render_top_output",
        ],
        "rollback_risks": ["validate-render-coverage", "validate-material-or-default-render-path"],
        "official_sources": [
            "https://docs.derivative.ca/Geometry_COMP",
            "https://docs.derivative.ca/Camera_COMP",
            "https://docs.derivative.ca/Light_COMP",
            "https://docs.derivative.ca/Render_TOP",
            "https://docs.derivative.ca/Null_TOP",
        ],
    },
    {
        "pattern_id": "midi_in_to_control_chop",
        "title": "MIDI In To Control CHOP",
        "intent_tags": ["midi", "control", "protocol", "chop"],
        "profiles": ["midi_control"],
        "required_ops": ["midiinCHOP", "mathCHOP", "nullCHOP"],
        "optional_ops": ["midiinDAT", "midieventDAT"],
        "concept_nodes": [
            ConceptNode(
                id="midi_source",
                label="MIDI input",
                role="source",
                domain="CHOP",
                op_type="midiinCHOP",
                params={"simplified": True, "record": False, "timer": False, "sys": False},
                evidence=["docs:midiinCHOP"],
            ),
            ConceptNode(
                id="midi_range",
                label="MIDI range mapping",
                role="process",
                domain="CHOP",
                op_type="mathCHOP",
                params={
                    "fromrange": (0.0, 127.0),
                    "torange": (0.0, 1.0),
                    "interppars": True,
                    "integer": "off",
                },
                evidence=["docs:mathCHOP"],
            ),
            ConceptNode(
                id="midi_out",
                label="MIDI control output",
                role="output",
                domain="CHOP",
                op_type="nullCHOP",
                evidence=["docs:nullCHOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="midi_source", target="midi_range", kind="data"),
            ConceptEdge(source="midi_range", target="midi_out", kind="data"),
        ],
        "exposes": [{"port_id": "control_chop", "domain": "CHOP", "node_id": "midi_out"}],
        "consumes": [{"port_id": "midi_device", "domain": "CHOP"}],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "midi_out", "domain": "CHOP"}],
        "safety": "device_dependent",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["midi_source_present", "range_mapping", "control_output"],
        "rollback_risks": ["device-source-required"],
        "official_sources": [
            "https://docs.derivative.ca/MIDI_In_CHOP",
            "https://docs.derivative.ca/Math_CHOP",
            "https://docs.derivative.ca/Null_CHOP",
        ],
    },
    {
        "pattern_id": "serial_dat_protocol_bridge",
        "title": "Serial DAT Protocol Bridge",
        "intent_tags": ["serial", "protocol", "dat", "diagnostics"],
        "profiles": ["dat_protocol"],
        "required_ops": ["serialDAT", "tableDAT", "nullDAT"],
        "optional_ops": ["serialdevicesDAT", "datexecuteDAT"],
        "concept_nodes": [
            ConceptNode(
                id="serial_source",
                label="Serial protocol input",
                role="source",
                domain="DAT",
                op_type="serialDAT",
                params={"active": True, "format": "perline", "clamp": True, "maxlines": 256},
                evidence=["docs:serialDAT"],
            ),
            ConceptNode(
                id="serial_diagnostics",
                label="Protocol diagnostics table",
                role="validator",
                domain="DAT",
                op_type="tableDAT",
                evidence=["docs:tableDAT"],
            ),
            ConceptNode(
                id="serial_out",
                label="Stable serial DAT output",
                role="output",
                domain="DAT",
                op_type="nullDAT",
                evidence=["docs:nullDAT"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="serial_source", target="serial_out", kind="data"),
        ],
        "exposes": [{"port_id": "protocol_dat", "domain": "DAT", "node_id": "serial_out"}],
        "consumes": [{"port_id": "serial_device", "domain": "DAT"}],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "serial_diagnostics", "domain": "DAT"}],
        "safety": "device_dependent",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["serial_source_present", "protocol_table_output"],
        "rollback_risks": ["device-source-required"],
        "official_sources": [
            "https://docs.derivative.ca/Serial_DAT",
            "https://docs.derivative.ca/Table_DAT",
            "https://docs.derivative.ca/Null_DAT",
        ],
    },
    {
        "pattern_id": "osc_in_dat_protocol_bridge",
        "title": "OSC In DAT Protocol Bridge",
        "intent_tags": ["osc", "protocol", "dat", "diagnostics"],
        "profiles": ["dat_protocol"],
        "required_ops": ["oscinDAT", "tableDAT", "nullDAT"],
        "optional_ops": ["oscinCHOP", "oscoutDAT"],
        "concept_nodes": [
            ConceptNode(
                id="osc_source",
                label="OSC protocol input",
                role="source",
                domain="DAT",
                op_type="oscinDAT",
                params={"active": True, "protocol": "msging", "clamp": True, "maxlines": 256},
                evidence=["docs:oscinDAT"],
            ),
            ConceptNode(
                id="osc_diagnostics",
                label="OSC diagnostics table",
                role="validator",
                domain="DAT",
                op_type="tableDAT",
                evidence=["docs:tableDAT"],
            ),
            ConceptNode(
                id="osc_out",
                label="Stable OSC DAT output",
                role="output",
                domain="DAT",
                op_type="nullDAT",
                evidence=["docs:nullDAT"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="osc_source", target="osc_out", kind="data"),
        ],
        "exposes": [{"port_id": "protocol_dat", "domain": "DAT", "node_id": "osc_out"}],
        "consumes": [{"port_id": "osc_source", "domain": "DAT"}],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "osc_diagnostics", "domain": "DAT"}],
        "safety": "device_dependent",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["osc_source_present", "protocol_table_output"],
        "rollback_risks": ["device-source-required", "network-source-required"],
        "official_sources": [
            "https://docs.derivative.ca/OSC_In_DAT",
            "https://docs.derivative.ca/Table_DAT",
            "https://docs.derivative.ca/Null_DAT",
        ],
    },
    {
        "pattern_id": "websocket_dat_protocol_bridge",
        "title": "WebSocket DAT Protocol Bridge",
        "intent_tags": ["websocket", "protocol", "dat", "diagnostics"],
        "profiles": ["dat_protocol"],
        "required_ops": ["websocketDAT", "tableDAT", "nullDAT"],
        "optional_ops": ["webserverDAT"],
        "concept_nodes": [
            ConceptNode(
                id="websocket_source",
                label="WebSocket protocol input",
                role="source",
                domain="DAT",
                op_type="websocketDAT",
                params={"active": True, "clamp": True, "maxlines": 256},
                evidence=["docs:websocketDAT"],
            ),
            ConceptNode(
                id="websocket_diagnostics",
                label="WebSocket diagnostics table",
                role="validator",
                domain="DAT",
                op_type="tableDAT",
                evidence=["docs:tableDAT"],
            ),
            ConceptNode(
                id="websocket_out",
                label="Stable WebSocket DAT output",
                role="output",
                domain="DAT",
                op_type="nullDAT",
                evidence=["docs:nullDAT"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="websocket_source", target="websocket_out", kind="data"),
        ],
        "exposes": [{"port_id": "protocol_dat", "domain": "DAT", "node_id": "websocket_out"}],
        "consumes": [{"port_id": "websocket_endpoint", "domain": "DAT"}],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "websocket_diagnostics", "domain": "DAT"}],
        "safety": "device_dependent",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["websocket_source_present", "protocol_table_output"],
        "rollback_risks": ["device-source-required", "network-source-required"],
        "official_sources": [
            "https://docs.derivative.ca/WebSocket_DAT",
            "https://docs.derivative.ca/Table_DAT",
            "https://docs.derivative.ca/Null_DAT",
        ],
    },
    {
        "pattern_id": "mqtt_client_dat_protocol_bridge",
        "title": "MQTT Client DAT Protocol Bridge",
        "intent_tags": ["mqtt", "protocol", "dat", "diagnostics"],
        "profiles": ["dat_protocol"],
        "required_ops": ["mqttclientDAT", "tableDAT", "nullDAT"],
        "optional_ops": [],
        "concept_nodes": [
            ConceptNode(
                id="mqtt_source",
                label="MQTT broker client input",
                role="source",
                domain="DAT",
                op_type="mqttclientDAT",
                params={"active": True, "reconnect": True, "clamp": True, "maxlines": 256},
                evidence=["docs:mqttclientDAT"],
            ),
            ConceptNode(
                id="mqtt_diagnostics",
                label="MQTT diagnostics table",
                role="validator",
                domain="DAT",
                op_type="tableDAT",
                evidence=["docs:tableDAT"],
            ),
            ConceptNode(
                id="mqtt_out",
                label="Stable MQTT DAT output",
                role="output",
                domain="DAT",
                op_type="nullDAT",
                evidence=["docs:nullDAT"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="mqtt_source", target="mqtt_out", kind="data"),
        ],
        "exposes": [{"port_id": "protocol_dat", "domain": "DAT", "node_id": "mqtt_out"}],
        "consumes": [{"port_id": "mqtt_broker", "domain": "DAT"}],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "mqtt_diagnostics", "domain": "DAT"}],
        "safety": "device_dependent",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["mqtt_source_present", "protocol_table_output"],
        "rollback_risks": ["device-source-required", "network-source-required"],
        "official_sources": [
            "https://docs.derivative.ca/MQTT_Client_DAT",
            "https://docs.derivative.ca/Table_DAT",
            "https://docs.derivative.ca/Null_DAT",
        ],
    },
    {
        "pattern_id": "udp_in_dat_protocol_bridge",
        "title": "UDP In DAT Protocol Bridge",
        "intent_tags": ["udp", "protocol", "dat", "diagnostics"],
        "profiles": ["dat_protocol"],
        "required_ops": ["udpinDAT", "tableDAT", "nullDAT"],
        "optional_ops": ["udpoutDAT"],
        "concept_nodes": [
            ConceptNode(
                id="udp_source",
                label="UDP protocol input",
                role="source",
                domain="DAT",
                op_type="udpinDAT",
                params={
                    "active": True,
                    "protocol": "msging",
                    "format": "permessage",
                    "clamp": True,
                    "maxlines": 256,
                },
                evidence=["docs:udpinDAT"],
            ),
            ConceptNode(
                id="udp_diagnostics",
                label="UDP diagnostics table",
                role="validator",
                domain="DAT",
                op_type="tableDAT",
                evidence=["docs:tableDAT"],
            ),
            ConceptNode(
                id="udp_out",
                label="Stable UDP DAT output",
                role="output",
                domain="DAT",
                op_type="nullDAT",
                evidence=["docs:nullDAT"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="udp_source", target="udp_out", kind="data"),
        ],
        "exposes": [{"port_id": "protocol_dat", "domain": "DAT", "node_id": "udp_out"}],
        "consumes": [{"port_id": "udp_source", "domain": "DAT"}],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "udp_diagnostics", "domain": "DAT"}],
        "safety": "device_dependent",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["udp_source_present", "protocol_table_output"],
        "rollback_risks": ["device-source-required", "network-source-required"],
        "official_sources": [
            "https://docs.derivative.ca/UDP_In_DAT",
            "https://docs.derivative.ca/Table_DAT",
            "https://docs.derivative.ca/Null_DAT",
        ],
    },
    {
        "pattern_id": "dat_table_render_switch_top",
        "title": "DAT Table Render Switch TOP",
        "intent_tags": ["dat", "table", "switch", "top", "render", "stable-output"],
        "profiles": ["dat_protocol"],
        "required_ops": ["tableDAT", "constantTOP", "noiseTOP", "switchTOP", "nullTOP"],
        "optional_ops": [],
        "concept_nodes": [
            ConceptNode(
                id="switch_table",
                label="Switch selection table",
                role="source",
                domain="DAT",
                op_type="tableDAT",
                content={"text": "selected_index\tlabel\n0\tsource_a\n1\tsource_b\n"},
                evidence=["docs:tableDAT"],
            ),
            ConceptNode(
                id="render_source_a",
                label="Render source A",
                role="source",
                domain="TOP",
                op_type="constantTOP",
                evidence=["docs:constantTOP"],
            ),
            ConceptNode(
                id="render_source_b",
                label="Render source B",
                role="source",
                domain="TOP",
                op_type="noiseTOP",
                evidence=["docs:noiseTOP"],
            ),
            ConceptNode(
                id="render_switch",
                label="Render source switch",
                role="process",
                domain="TOP",
                op_type="switchTOP",
                params={
                    "index": {"expr": "min(1, max(0, int(op('${path:switch_table}')[1, 'selected_index'])))"}
                },
                evidence=["docs:switchTOP"],
            ),
            ConceptNode(
                id="stable_output",
                label="Stable TOP output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
                evidence=["docs:nullTOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="render_source_a", target="render_switch", kind="data"),
            ConceptEdge(source="render_source_b", target="render_switch", target_index=1, kind="data"),
            ConceptEdge(source="render_switch", target="stable_output", kind="data"),
            ConceptEdge(source="switch_table", target="render_switch", kind="reference"),
        ],
        "exposes": [
            {"port_id": "switch_table", "domain": "DAT", "node_id": "switch_table"},
            {"port_id": "stable_top", "domain": "TOP", "node_id": "stable_output"},
        ],
        "consumes": [],
        "parameters": [
            {
                "name": "switch_index",
                "target_node_id": "render_switch",
                "target_param": "index",
                "value_kind": "int",
                "default": 0,
                "control_type": "table",
            }
        ],
        "layout": {"column": 1},
        "debug_outputs": [
            {"node": "switch_table", "domain": "DAT"},
            {"node": "stable_output", "domain": "TOP"},
        ],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "render_switch_table_present",
            "render_switch_index_binding",
            "render_switch_output_present",
        ],
        "rollback_risks": [],
        "official_sources": [
            "https://docs.derivative.ca/Table_DAT",
            "https://docs.derivative.ca/Constant_TOP",
            "https://docs.derivative.ca/Noise_TOP",
            "https://docs.derivative.ca/Switch_TOP",
            "https://docs.derivative.ca/Null_TOP",
        ],
    },
    {
        "pattern_id": "dat_execute_table_change_callback",
        "title": "DAT Execute Table-Change Callback",
        "intent_tags": ["dat", "execute", "callback", "table-change", "diagnostics"],
        "profiles": ["dat_protocol"],
        "required_ops": ["tableDAT", "datexecuteDAT", "textDAT", "nullDAT"],
        "optional_ops": [],
        "concept_nodes": [
            ConceptNode(
                id="watched_table",
                label="Watched diagnostics table",
                role="source",
                domain="DAT",
                op_type="tableDAT",
                evidence=["docs:tableDAT"],
            ),
            ConceptNode(
                id="callback_code",
                label="Table-change callback reference",
                role="validator",
                domain="DAT",
                op_type="textDAT",
                content={
                    "text": (
                        "tdpilot_callback_guard = False\n\n"
                        "def onTableChange(dat, prevDAT, info):\n"
                        "    global tdpilot_callback_guard\n"
                        "    if tdpilot_callback_guard:\n"
                        "        return\n"
                        "    if info is None:\n"
                        "        return\n"
                        "    tdpilot_callback_guard = True\n"
                        "    try:\n"
                        "        diagnostic = op('${path:callback_out}')\n"
                        "        if diagnostic is not None:\n"
                        "            _tdpilot_callback_rows = diagnostic.numRows\n"
                        "        return\n"
                        "    finally:\n"
                        "        tdpilot_callback_guard = False\n"
                    )
                },
                evidence=["docs:textDAT", "docs:datexecuteDAT"],
            ),
            ConceptNode(
                id="table_change_exec",
                label="DAT Execute table-change monitor",
                role="control",
                domain="DAT",
                op_type="datexecuteDAT",
                params={
                    "active": True,
                    "dat": "${path:watched_table}",
                    "tablechange": True,
                    "rowchange": False,
                    "colchange": False,
                    "cellchange": False,
                    "sizechange": False,
                },
                content={
                    "text": (
                        "tdpilot_callback_guard = False\n\n"
                        "def onTableChange(dat, prevDAT, info):\n"
                        "    global tdpilot_callback_guard\n"
                        "    if tdpilot_callback_guard:\n"
                        "        return\n"
                        "    if info is None:\n"
                        "        return\n"
                        "    tdpilot_callback_guard = True\n"
                        "    try:\n"
                        "        diagnostic = op('${path:callback_out}')\n"
                        "        if diagnostic is not None:\n"
                        "            _tdpilot_callback_rows = diagnostic.numRows\n"
                        "        return\n"
                        "    finally:\n"
                        "        tdpilot_callback_guard = False\n"
                    )
                },
                generated_code={
                    "block_id": "dat_execute_table_change_callback",
                    "language": "python",
                    "target_op": "${path:table_change_exec}",
                    "target_param": "text",
                    "source_kind": "generated",
                    "source_refs": ["${path:table_change_exec}"],
                    "static_checks": ["python_syntax", "dat_execute_table_change_callback"],
                    "runtime_checks": ["callback_guard_present", "diagnostic_output_present"],
                    "expected_outputs": ["${path:callback_out}"],
                    "risk_flags": ["validate-python-callback"],
                    "official_sources": ["https://docs.derivative.ca/DAT_Execute_DAT"],
                },
                evidence=["docs:datexecuteDAT"],
            ),
            ConceptNode(
                id="callback_out",
                label="Stable callback DAT output",
                role="output",
                domain="DAT",
                op_type="nullDAT",
                evidence=["docs:nullDAT"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="watched_table", target="callback_out", kind="data"),
            ConceptEdge(source="watched_table", target="table_change_exec", kind="reference"),
        ],
        "exposes": [{"port_id": "callback_dat", "domain": "DAT", "node_id": "callback_out"}],
        "consumes": [],
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "callback_out", "domain": "DAT"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": [
            "protocol_table_output",
            "dat_execute_callback_present",
            "callback_guard_present",
        ],
        "rollback_risks": ["validate-python-callback"],
        "official_sources": [
            "https://docs.derivative.ca/Table_DAT",
            "https://docs.derivative.ca/DAT_Execute_DAT",
            "https://docs.derivative.ca/Text_DAT",
            "https://docs.derivative.ca/Null_DAT",
        ],
    },
    {
        "pattern_id": "ndi_in_to_post_fx_output",
        "title": "NDI In To Post-FX Output",
        "intent_tags": ["ndi", "network-video", "post-fx", "top", "output"],
        "profiles": ["video_io"],
        "required_ops": ["ndiinTOP", "levelTOP", "nullTOP"],
        "optional_ops": ["ndiDAT", "audiondiCHOP"],
        "concept_nodes": [
            ConceptNode(
                id="ndi_source",
                label="NDI video input",
                role="source",
                domain="TOP",
                op_type="ndiinTOP",
                params={"active": False},
                evidence=["docs:ndiinTOP"],
            ),
            ConceptNode(
                id="post_fx",
                label="Post-FX level stage",
                role="process",
                domain="TOP",
                op_type="levelTOP",
                params={"opacity": 1.0},
                evidence=["docs:levelTOP"],
            ),
            ConceptNode(
                id="stable_output",
                label="Stable TOP output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
                evidence=["docs:nullTOP"],
            ),
        ],
        "concept_edges": [
            ConceptEdge(source="ndi_source", target="post_fx", kind="data"),
            ConceptEdge(source="post_fx", target="stable_output", kind="data"),
        ],
        "exposes": [{"port_id": "stable_top", "domain": "TOP", "node_id": "stable_output"}],
        "consumes": [{"port_id": "ndi_source", "domain": "TOP"}],
        "parameters": [{"name": "ndi_source_name", "target_node_id": "ndi_source", "target_param": "name"}],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "stable_output", "domain": "TOP"}],
        "safety": "device_dependent",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["ndi_source_present", "post_fx_stage", "top_output_present"],
        "rollback_risks": ["device-source-required", "network-video-source-required"],
        "official_sources": [
            "https://docs.derivative.ca/NDI_In_TOP",
            "https://docs.derivative.ca/Level_TOP",
            "https://docs.derivative.ca/Null_TOP",
        ],
    },
    {
        "pattern_id": "debug_output_conventions",
        "title": "Stable Output And Debug Notes",
        "intent_tags": ["debug", "stable-output", "diagnostics"],
        "profiles": ["concept_compiled"],
        "required_ops": ["textDAT"],
        "optional_ops": ["nullTOP", "nullCHOP"],
        "concept_nodes": [
            ConceptNode(
                id="debug_notes",
                label="Debug notes",
                role="validator",
                domain="DAT",
                op_type="textDAT",
                evidence=["docs:textDAT"],
            )
        ],
        "concept_edges": [],
        "exposes": [{"port_id": "debug_dat", "domain": "DAT", "node_id": "debug_notes"}],
        "consumes": [{"port_id": "stable_top", "domain": "TOP"}],
        "parameters": [],
        "layout": {"column": 3},
        "debug_outputs": [{"node": "debug_notes", "domain": "DAT"}],
        "safety": "safe_live",
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["output_node_present"],
        "rollback_risks": [],
        "official_sources": ["https://docs.derivative.ca/Text_DAT"],
    },
]


__all__ = [
    "docs_evidence_for_patterns",
    "load_pattern_registry",
    "load_pattern_registry_from_json",
    "pattern_id_aliases",
    "patterns_by_id",
]
