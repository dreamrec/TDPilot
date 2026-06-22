from __future__ import annotations

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain.corpus_bridge import build_corpus_evidence
from td_mcp.brain.planner import build_brain_plan


def _operator_card(op_type: str, summary: str, *, params: list[str] | None = None) -> dict:
    family = next(
        (suffix for suffix in ("COMP", "CHOP", "SOP", "POP", "DAT", "MAT", "TOP") if op_type.endswith(suffix)),
        "TOP",
    )
    return {
        "card_type": "operator",
        "op_type": op_type,
        "family": family,
        "display_name": op_type,
        "docs_url": f"https://docs.derivative.ca/{op_type}",
        "summary": summary,
        "key_params": [{"name": name, "type": "Float", "note": f"{name} control"} for name in params or []],
        "key_concepts": ["feedback", "operator evidence"] if "feedback" in summary.lower() else [],
    }


class SearchableCardIndex:
    def __init__(self, cards: dict[str, dict]):
        self.cards = cards
        self.search_calls: list[dict] = []

    def get_operator(self, op_type: str):
        return self.cards.get(op_type)

    def search(
        self,
        query: str,
        card_types: list[str] | None = None,
        family: str | None = None,
        limit: int = 10,
    ):
        self.search_calls.append(
            {"query": query, "card_types": card_types, "family": family, "limit": limit}
        )
        haystack = query.lower()
        hits = []
        for card in self.cards.values():
            text = " ".join(
                str(card.get(key, "")) for key in ("op_type", "display_name", "summary")
            ).lower()
            if any(token in text for token in haystack.split()):
                hits.append(card)
        hits.append(
            {
                "card_type": "operator",
                "op_type": "blogTOP",
                "summary": "Third-party blog mirror with no official citation.",
            }
        )
        return hits[:limit]


def test_corpus_bridge_returns_exact_search_and_local_rerank_records():
    cards = {
        "feedbackTOP": _operator_card(
            "feedbackTOP",
            "Recursive feedback trails with target TOP reset and decay.",
            params=["top", "reset", "resetpulse"],
        ),
        "levelTOP": _operator_card(
            "levelTOP",
            "Image level correction for feedback decay and brightness shaping.",
            params=["opacity", "brightness"],
        ),
    }
    index = SearchableCardIndex(cards)

    records = build_corpus_evidence(
        intent="build recursive feedback trails with decay",
        operators=["feedbackTOP", "levelTOP"],
        card_index=index,
    )

    evidence_ids = [record.evidence_id for record in records]
    assert "corpus:exact:feedbackTOP" in evidence_ids
    assert "corpus:exact:levelTOP" in evidence_ids
    assert "corpus:search:feedbackTOP" in evidence_ids
    assert all(record.docs_url.startswith("https://docs.derivative.ca/") for record in records)
    assert all(0.0 <= record.score <= 1.0 for record in records)
    feedback_exact = next(record for record in records if record.evidence_id == "corpus:exact:feedbackTOP")
    assert feedback_exact.key_params == ["top", "reset", "resetpulse"]
    assert feedback_exact.matched_terms
    assert "corpus:search:blogTOP" not in evidence_ids
    assert index.search_calls


@pytest.mark.asyncio
async def test_feedback_plan_carries_structured_corpus_evidence_when_docs_are_enabled():
    operators = ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"]
    cards = {
        op_type: _operator_card(op_type, f"{op_type} official feedback planning docs")
        for op_type in operators
    }
    client = FakeTDClient(
        scripted={
            "families": {"families": {"TOP": operators}},
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="build a clean feedback displacement loop",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=SearchableCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert any(record.op_type == "feedbackTOP" for record in plan.corpus_evidence)
    assert any(record.source == "docs_search" for record in plan.corpus_evidence)
    assert "corpus:exact:feedbackTOP" in plan.grounding_evidence
    assert any(item.startswith("corpus:search:") for item in plan.grounding_evidence)


@pytest.mark.asyncio
async def test_plan_omits_corpus_evidence_when_docs_are_disabled():
    operators = ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"]
    cards = {
        op_type: _operator_card(op_type, f"{op_type} official feedback planning docs")
        for op_type in operators
    }
    index = SearchableCardIndex(cards)
    client = FakeTDClient(
        scripted={
            "families": {"families": {"TOP": operators}},
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="build a clean feedback displacement loop",
        target_root="/project1",
        include_docs=False,
        card_index=index,
    )

    assert plan.corpus_evidence == []
    assert not any(item.startswith("corpus:") for item in plan.grounding_evidence)
    assert index.search_calls == []


@pytest.mark.asyncio
async def test_compiler_plan_carries_corpus_evidence_for_selected_candidate_ops():
    operators = {
        "audiofileinCHOP",
        "analyzeCHOP",
        "mathCHOP",
        "nullCHOP",
        "noiseTOP",
        "feedbackTOP",
        "levelTOP",
        "compositeTOP",
        "nullTOP",
        "baseCOMP",
        "containerCOMP",
        "sliderCOMP",
        "buttonCOMP",
        "panelCHOP",
        "textDAT",
        "annotateCOMP",
        "infoCHOP",
        "errorDAT",
    }
    cards = {
        op_type: _operator_card(op_type, f"{op_type} official audio feedback control docs")
        for op_type in operators
    }
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP", "panelCHOP", "infoCHOP"],
                    "TOP": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "containerCOMP", "sliderCOMP", "buttonCOMP", "annotateCOMP"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=SearchableCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.concept_graph.profile == "concept_compiled"
    assert "corpus:exact:feedbackTOP" in plan.grounding_evidence
    assert "corpus:exact:audiofileinCHOP" in plan.grounding_evidence
    assert any(record.op_type == "panelCHOP" for record in plan.corpus_evidence)
