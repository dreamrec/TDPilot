"""Small Phase 1 pattern registry for concept-to-node planning."""

from __future__ import annotations

from td_mcp.models.brain import BrainPattern, ConceptEdge, ConceptNode


def load_pattern_registry() -> list[BrainPattern]:
    """Load the built-in Phase 1 seed patterns."""
    return [BrainPattern(**item) for item in _DEFAULT_PATTERNS]


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
    return list(dict.fromkeys(evidence))


_DEFAULT_PATTERNS = [
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
                evidence=["docs:analyzeCHOP"],
            ),
            ConceptNode(
                id="audio_math",
                label="Range shaping",
                role="process",
                domain="CHOP",
                op_type="mathCHOP",
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
        "parameters": [],
        "layout": {"column": 0},
        "debug_outputs": [{"node": "audio_out", "domain": "CHOP"}],
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["audio_source_present", "analysis_stage", "range_mapping"],
        "rollback_risks": [],
        "official_sources": [
            "https://docs.derivative.ca/Audio_File_In_CHOP",
            "https://docs.derivative.ca/Analyze_CHOP",
            "https://docs.derivative.ca/Math_CHOP",
            "https://docs.derivative.ca/Null_CHOP",
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
        "parameters": [],
        "layout": {"column": 1},
        "debug_outputs": [{"node": "stable_output", "domain": "TOP"}],
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["feedback_cycle", "decay_control", "cheap_visual_metrics"],
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
            ConceptEdge(source="panel_slider", target="panel_reader", kind="reference"),
            ConceptEdge(source="panel_button", target="panel_reader", kind="reference"),
            ConceptEdge(source="panel_reader", target="panel_out", kind="data"),
        ],
        "parameters": [],
        "layout": {"column": 2},
        "debug_outputs": [{"node": "panel_out", "domain": "CHOP"}],
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["panel_components_present", "panel_state_reader", "control_output"],
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
        "parameters": [],
        "layout": {"column": 3},
        "debug_outputs": [{"node": "debug_notes", "domain": "DAT"}],
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["output_node_present"],
        "rollback_risks": [],
        "official_sources": ["https://docs.derivative.ca/Text_DAT"],
    },
]


__all__ = ["docs_evidence_for_patterns", "load_pattern_registry", "patterns_by_id"]
