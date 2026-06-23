from __future__ import annotations

from td_mcp.brain import atlas_drafter
from td_mcp.models.brain import CandidateConceptGraph, ConceptNode


def _top_candidate(pattern_id: str, evidence: list[str]) -> CandidateConceptGraph:
    return CandidateConceptGraph(
        compiled_task_id="compiled-open-prompt",
        label=pattern_id,
        profiles=["generic"],
        pattern_ids=[pattern_id],
        concepts=[
            ConceptNode(
                id="source",
                label="Noise TOP source",
                role="source",
                domain="TOP",
                op_type="noiseTOP",
            ),
            ConceptNode(
                id="output",
                label="Stable TOP output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
            ),
        ],
        required_ops=["noiseTOP", "nullTOP"],
        expected_outputs=["TOP"],
        validation_needs=["top_output_present", "cheap_visual_metrics"],
        grounding_evidence=evidence,
        score=0.72,
        explanation="atlas_synthesis:test_candidate",
    )


def test_atlas_topology_ranking_uses_validation_feedback_before_order_tiebreaker():
    weak = _top_candidate(
        "atlas:synthesized:preview_top_weak_validation",
        [
            "docs:noiseTOP",
            "docs:nullTOP",
            "runtime-validation-missing:cheap_visual_metrics",
            "runtime-validation-failed-required:top_output_present",
        ],
    )
    strong = _top_candidate(
        "atlas:synthesized:preview_top_strong_validation",
        [
            "docs:noiseTOP",
            "docs:nullTOP",
            "runtime-validation-pass:cheap_visual_metrics",
            "runtime-validation-pass:top_output_present",
        ],
    )

    ranked = atlas_drafter._rank_synthesized_topology_results(
        [
            (1, atlas_drafter.AtlasDraftResult(accepted=True, candidate_graph=weak)),
            (2, atlas_drafter.AtlasDraftResult(accepted=True, candidate_graph=strong)),
        ],
        intent="build a visual TOP texture output",
    )

    assert ranked.candidate_graph is not None
    assert ranked.candidate_graph.pattern_ids == ["atlas:synthesized:preview_top_strong_validation"]
    assert ranked.candidate_graphs[0].pattern_ids == ["atlas:synthesized:preview_top_strong_validation"]
    assert ranked.candidate_graphs[1].pattern_ids == ["atlas:synthesized:preview_top_weak_validation"]
    assert "validation_feedback:readiness=" in ranked.candidate_graph.explanation
    assert any(
        marker.startswith("atlas-synthesis:validation-feedback:1:")
        and ":passed:2:missing:0:failed:0:failed_required:0" in marker
        for marker in ranked.grounding_evidence
    )
    assert any(
        marker.startswith("atlas-synthesis:validation-feedback:2:")
        and ":passed:0:missing:1:failed:0:failed_required:1" in marker
        for marker in ranked.grounding_evidence
    )
