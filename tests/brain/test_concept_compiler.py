from __future__ import annotations

from td_mcp.brain.concept_compiler import build_candidate_graphs, compile_visual_task
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
    assert {"audio_reactive", "feedback", "panel_ui"}.issubset(set(compiled.candidate_profiles))
    assert {"audio_analysis", "feedback_loop", "panel_controls", "debug_output"}.issubset(
        set(compiled.required_capabilities)
    )
    assert "docs:audiofileinCHOP" in compiled.grounding_evidence
    assert "docs:feedbackTOP" in compiled.grounding_evidence
    assert "docs:panelCHOP" in compiled.grounding_evidence


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


def test_candidate_graph_composes_seed_patterns_and_docs_grounded_required_ops():
    compiled = compile_visual_task(
        "Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(ALL_SEED_OPS),
    )
    candidates = build_candidate_graphs(compiled, patterns=load_pattern_registry())

    assert len(candidates) == 1
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
    assert any(edge.kind == "control" and edge.source == "audio_out" for edge in candidate.edges)
    assert all(f"docs:{op_type}" in candidate.grounding_evidence for op_type in candidate.required_ops)
