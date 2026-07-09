from __future__ import annotations

from td_mcp.brain.llm_contract import LLM_CORPUS_CONTRACT, review_draft_candidate_graph
from td_mcp.models.brain import CompiledVisualTaskSpec


def _operator_card(op_type: str) -> dict:
    family = next(
        (
            suffix
            for suffix in ("COMP", "CHOP", "SOP", "POP", "DAT", "MAT", "TOP")
            if op_type.endswith(suffix)
        ),
        "TOP",
    )
    return {
        "card_type": "operator",
        "op_type": op_type,
        "family": family,
        "display_name": op_type,
        "docs_url": f"https://docs.derivative.ca/{op_type}",
        "summary": f"{op_type} official operator docs.",
    }


class FakeCardIndex:
    def __init__(
        self,
        known: set[str],
        key_params: dict[str, list] | None = None,
        docs_url_overrides: dict[str, str] | None = None,
    ):
        self.known = known
        self.key_params = key_params or {}
        self.docs_url_overrides = docs_url_overrides or {}

    def get_operator(self, op_type: str):
        if op_type in self.known:
            card = _operator_card(op_type)
            if op_type in self.key_params:
                card["key_params"] = self.key_params[op_type]
            if op_type in self.docs_url_overrides:
                card["docs_url"] = self.docs_url_overrides[op_type]
            return card
        return None


def _compiled() -> CompiledVisualTaskSpec:
    return CompiledVisualTaskSpec(
        intent="Build a recursive feedback trail",
        domains=["TOP"],
        candidate_profiles=["feedback"],
        candidate_operator_families=["TOP"],
        required_capabilities=["feedback_loop"],
        validation_needs=["feedback_output_readback"],
        grounding_evidence=["compiler:feedback-loop"],
    )


def _valid_draft() -> dict:
    return {
        "label": "Draft recursive feedback",
        "profiles": ["feedback"],
        "concepts": [
            {
                "id": "src",
                "label": "Noise source",
                "role": "source",
                "domain": "TOP",
                "op_type": "noiseTOP",
            },
            {
                "id": "feedback",
                "label": "Feedback buffer",
                "role": "feedback",
                "domain": "TOP",
                "op_type": "feedbackTOP",
                "params": {"top": "/project1/out1"},
            },
            {
                "id": "out",
                "label": "Stable output",
                "role": "output",
                "domain": "TOP",
                "op_type": "nullTOP",
            },
        ],
        "edges": [
            {"source": "src", "target": "feedback", "kind": "data"},
            {"source": "feedback", "target": "out", "kind": "data"},
        ],
        "required_ops": ["noiseTOP", "feedbackTOP", "nullTOP"],
        "validation_needs": ["feedback_output_readback"],
        "explanation": "Use noise as source, keep recursive feedback, expose stable output.",
    }


def test_contract_states_llm_suggests_and_validators_decide():
    assert LLM_CORPUS_CONTRACT["llm_role"] == "suggest_draft_intent_and_alternatives"
    assert LLM_CORPUS_CONTRACT["validator_role"] == "decide_accept_reject_or_rewrite"
    assert "official_docs" in LLM_CORPUS_CONTRACT["required_grounding"]
    assert "live_td" in LLM_CORPUS_CONTRACT["proof_layers"]
    assert LLM_CORPUS_CONTRACT["param_verification_tiers"] == [
        "registry_contract",
        "atlas_name_verified",
        "unverified_stripped",
    ]


def test_valid_draft_graph_is_accepted_as_grounded_candidate():
    compiled = _compiled()
    review = review_draft_candidate_graph(
        _valid_draft(),
        compiled_task=compiled,
        available_ops={"noiseTOP", "feedbackTOP", "nullTOP"},
        card_index=FakeCardIndex({"noiseTOP", "feedbackTOP", "nullTOP"}),
    )

    assert review.status == "accepted"
    assert review.accepted is True
    assert review.candidate_graph is not None
    assert review.candidate_graph.compiled_task_id == compiled.id
    assert review.candidate_graph.required_ops == ["noiseTOP", "feedbackTOP", "nullTOP"]
    assert "draft-review:accepted" in review.grounding_evidence
    assert "docs:feedbackTOP" in review.candidate_graph.grounding_evidence
    assert review.score >= 0.7


def test_draft_graph_rejects_missing_docs_and_unavailable_ops():
    review = review_draft_candidate_graph(
        _valid_draft(),
        compiled_task=_compiled(),
        available_ops={"noiseTOP", "nullTOP"},
        card_index=FakeCardIndex({"noiseTOP", "nullTOP"}),
    )

    assert review.status == "rejected"
    assert review.accepted is False
    assert review.candidate_graph is None
    assert "missing_docs:feedbackTOP" in review.rejection_reasons
    assert "unavailable_op:feedbackTOP" in review.rejection_reasons


def test_draft_graph_rewrites_unverified_params_before_acceptance():
    # Param-gating polarity flip: absence from the hand ParamSemantics registry
    # alone no longer strips — the official card key_params (atlas name tier)
    # can also verify a name. "hallucinateddecay" is verifiable by NEITHER tier
    # (not in the registry and this card has no key_params), so the strip-not-
    # reject contract for truly-unknown params holds unchanged.
    draft = _valid_draft()
    draft["concepts"][1]["params"] = {
        "top": "/project1/out1",
        "hallucinateddecay": 0.5,
    }

    review = review_draft_candidate_graph(
        draft,
        compiled_task=_compiled(),
        available_ops={"noiseTOP", "feedbackTOP", "nullTOP"},
        card_index=FakeCardIndex({"noiseTOP", "feedbackTOP", "nullTOP"}),
    )

    assert review.status == "rewritten"
    assert review.accepted is True
    assert "removed_unverified_param:feedbackTOP.hallucinateddecay" in review.rewrites
    assert review.candidate_graph is not None
    feedback = next(node for node in review.candidate_graph.concepts if node.id == "feedback")
    assert feedback.params == {"top": "/project1/out1"}


def test_atlas_card_key_params_verify_non_registry_param_names():
    """Polarity flip tier 2: a name outside the hand registry survives when the
    operator's OFFICIAL docs card lists it in key_params. The value carries no
    static contract — it is checked by the post-apply live validation layer."""
    draft = _valid_draft()
    draft["concepts"][1]["params"] = {
        "top": "/project1/out1",  # tier 1: registry contract
        "customdecay": 0.5,  # tier 2: atlas name only (not in registry)
    }

    review = review_draft_candidate_graph(
        draft,
        compiled_task=_compiled(),
        available_ops={"noiseTOP", "feedbackTOP", "nullTOP"},
        card_index=FakeCardIndex(
            {"noiseTOP", "feedbackTOP", "nullTOP"},
            key_params={"feedbackTOP": [{"name": "customdecay"}]},
        ),
    )

    assert review.status == "accepted"
    assert review.rewrites == []
    assert review.candidate_graph is not None
    feedback = next(node for node in review.candidate_graph.concepts if node.id == "feedback")
    assert feedback.params == {"top": "/project1/out1", "customdecay": 0.5}
    assert "param-verified:registry:feedbackTOP.top" in review.grounding_evidence
    assert "param-verified:atlas:feedbackTOP.customdecay" in review.grounding_evidence


def test_unofficial_card_source_does_not_name_verify_params():
    """The atlas name tier requires an official Derivative docs URL: a card with
    key_params but an unofficial source cannot rescue an out-of-registry name."""
    draft = _valid_draft()
    draft["concepts"][1]["params"] = {
        "top": "/project1/out1",
        "customdecay": 0.5,
    }

    review = review_draft_candidate_graph(
        draft,
        compiled_task=_compiled(),
        available_ops={"noiseTOP", "feedbackTOP", "nullTOP"},
        card_index=FakeCardIndex(
            {"noiseTOP", "feedbackTOP", "nullTOP"},
            key_params={"feedbackTOP": [{"name": "customdecay"}]},
            docs_url_overrides={"feedbackTOP": "https://example.com/Feedback_TOP"},
        ),
    )

    assert review.status == "rewritten"
    assert "removed_unverified_param:feedbackTOP.customdecay" in review.rewrites
    assert review.candidate_graph is not None
    feedback = next(node for node in review.candidate_graph.concepts if node.id == "feedback")
    assert feedback.params == {"top": "/project1/out1"}


def test_draft_graph_rejects_invalid_schema_before_scoring():
    review = review_draft_candidate_graph(
        {
            "label": "Broken draft",
            "profiles": ["feedback"],
            "concepts": [
                {
                    "id": "src",
                    "label": "Noise source",
                    "role": "source",
                    "domain": "TOP",
                    "op_type": "noiseTOP",
                }
            ],
            "edges": [{"source": "src", "target": "missing", "kind": "data"}],
        },
        compiled_task=_compiled(),
        available_ops={"noiseTOP"},
        card_index=FakeCardIndex({"noiseTOP"}),
    )

    assert review.status == "rejected"
    assert review.candidate_graph is None
    assert any(reason.startswith("invalid_schema:") for reason in review.rejection_reasons)
