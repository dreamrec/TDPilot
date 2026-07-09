"""Tests for the host-authored draft loop: td_brain_ground + td_brain_propose.

The LLM-as-planner flip: the HOST agent authors BrainPlan drafts, TDPilot
grounds them (td_brain_ground) and proves them (td_brain_propose ->
review_draft_candidate_graph -> plan cache -> td_brain_execute(plan_id=...)).
Follows the fixture style of tests/test_brain_tools.py (mcp_ctx fixture,
monkeypatched _tr helpers).
"""

from __future__ import annotations

import asyncio

import pytest
from conftest import RecordingTDClient

import td_mcp.server as server
from td_mcp.brain.planner import build_brain_plan
from td_mcp.models.brain import TransactionResult
from td_mcp.registry import resources, tools_brain


def _operator_card(op_type: str, summary: str | None = None) -> dict:
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
        "summary": summary or f"{op_type} official operator docs.",
        "key_params": [{"name": "top"}, {"name": "opacity"}],
        "common_gotchas": [f"{op_type} gotcha: check the docs page."],
    }


class SearchableCardIndex:
    """Card index stub with both exact lookup and text search."""

    def __init__(self, cards: dict[str, dict]):
        self.cards = cards

    def get_operator(self, op_type: str):
        return self.cards.get(op_type)

    def search(self, query: str, card_types=None, limit: int = 10):
        return list(self.cards.values())[:limit]


_FEEDBACK_OPS = ("noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP")


def _feedback_card_index() -> SearchableCardIndex:
    return SearchableCardIndex({op_type: _operator_card(op_type) for op_type in _FEEDBACK_OPS})


def _feedback_families_client() -> RecordingTDClient:
    return RecordingTDClient(
        responses={
            "families": {"families": {"TOP": ["noise", "feedback", "level", "composite", "null"]}},
            "nodes": {"nodes": []},
        }
    )


def _valid_feedback_draft() -> dict:
    return {
        "label": "Audio-agnostic recursive feedback trails",
        "profiles": ["feedback"],
        "concepts": [
            {
                "id": "src",
                "label": "Noise source",
                "role": "source",
                "domain": "TOP",
                "op_type": "noiseTOP",
                "params": {"period": 4.0},
            },
            {
                "id": "feedback",
                "label": "Feedback buffer",
                "role": "feedback",
                "domain": "TOP",
                "op_type": "feedbackTOP",
                "params": {"top": "${path:composite}"},
            },
            {
                "id": "decay",
                "label": "Trail decay",
                "role": "process",
                "domain": "TOP",
                "op_type": "levelTOP",
                "params": {"opacity": 0.92},
            },
            {
                "id": "composite",
                "label": "Composite merge",
                "role": "process",
                "domain": "TOP",
                "op_type": "compositeTOP",
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
            {"source": "src", "target": "composite", "kind": "data"},
            {"source": "feedback", "target": "decay", "kind": "data"},
            {"source": "decay", "target": "composite", "kind": "data"},
            {"source": "composite", "target": "feedback", "kind": "feedback"},
            {"source": "composite", "target": "out", "kind": "data"},
        ],
        "required_ops": list(_FEEDBACK_OPS),
        "validation_needs": ["feedback_output_readback"],
        "explanation": "Recursive feedback trail with registry-backed decay opacity.",
    }


@pytest.fixture
def quiet_tr(monkeypatch, td_client):
    """Silence telemetry helpers and route _get_client at the recording stub."""
    monkeypatch.setattr(tools_brain._tr, "_start_tool", lambda ctx, name: lambda: None)
    monkeypatch.setattr(tools_brain._tr, "_audit_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(tools_brain._tr, "_record_tool_error", lambda *args, **kwargs: None)
    monkeypatch.setattr(tools_brain._tr, "_get_client", lambda ctx: td_client)
    return td_client


def test_ground_and_propose_are_registered_with_mcp_metadata():
    tools = asyncio.run(server.mcp.list_tools())
    by_name = {tool.name: tool for tool in tools}

    for name in ("td_brain_ground", "td_brain_propose"):
        assert name in by_name
        tool = by_name[name]
        assert tool.title
        assert tool.description.startswith("Use this when")
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.openWorldHint is True
        assert tool.meta["anthropic/alwaysLoad"] is True


def test_ground_returns_full_pack_when_td_is_unreachable(quiet_tr, service_container, mcp_ctx):
    def _unreachable(endpoint: str, body: dict) -> dict:
        raise RuntimeError("TD not reachable")

    quiet_tr.handler = _unreachable
    service_container.card_index = SearchableCardIndex(
        {
            op_type: _operator_card(op_type)
            for op_type in (
                "audiofileinCHOP",
                "analyzeCHOP",
                "mathCHOP",
                "nullCHOP",
                *_FEEDBACK_OPS,
            )
        }
    )

    result = asyncio.run(tools_brain.td_brain_ground(mcp_ctx, "audio reactive feedback trails"))

    assert result["success"] is True
    pack = result["grounding_pack"]
    for key in (
        "task_features",
        "corpus_evidence",
        "candidate_operators",
        "param_semantics",
        "operator_availability",
        "live_state",
        "exemplars",
        "authoring_contract",
    ):
        assert key in pack, f"grounding pack missing {key}"

    # Intent routes through compile_visual_task: both profiles detected.
    profiles = pack["task_features"]["candidate_profiles"]
    assert "audio_reactive" in profiles
    assert "feedback" in profiles

    # TD absent: availability and live state degrade gracefully instead of failing.
    assert pack["operator_availability"]["available"] is False
    assert pack["operator_availability"]["reason"]
    assert pack["live_state"]["available"] is False
    assert pack["live_state"]["reason"]

    # Candidate cards carry the per-card authoring facts.
    cards_by_op = {card["op_type"]: card for card in pack["candidate_operators"]}
    assert "feedbackTOP" in cards_by_op
    assert cards_by_op["feedbackTOP"]["gotchas"]
    assert cards_by_op["feedbackTOP"]["summary"]
    assert len(pack["candidate_operators"]) <= 12

    # Param contracts are serialized per candidate operator.
    assert "feedbackTOP" in pack["param_semantics"]
    top_contract = next(entry for entry in pack["param_semantics"]["feedbackTOP"] if entry["name"] == "top")
    assert top_contract["value_kind"] == "op_ref"

    # The contract teaches the exact next-tool loop.
    contract = pack["authoring_contract"]
    assert "td_brain_propose" in contract["loop"]
    assert "td_brain_execute" in contract["loop"]
    assert contract["draft_schema"]["label"]
    assert isinstance(pack["exemplars"], list)


def test_ground_respects_include_live_state_toggle(quiet_tr, service_container, mcp_ctx):
    service_container.card_index = _feedback_card_index()

    result = asyncio.run(tools_brain.td_brain_ground(mcp_ctx, "feedback trails", include_live_state=False))

    assert result["success"] is True
    assert result["grounding_pack"]["live_state"]["available"] is False


def test_propose_valid_draft_caches_plan_for_plan_id_execution(
    quiet_tr, service_container, mcp_ctx, monkeypatch
):
    quiet_tr.responses = _feedback_families_client().responses
    service_container.card_index = _feedback_card_index()

    result = asyncio.run(
        tools_brain.td_brain_propose(
            mcp_ctx,
            _valid_feedback_draft(),
            intent="Build a recursive feedback trail",
        )
    )

    assert result["success"] is True
    plan_id = result["plan_id"]
    assert plan_id
    summary = result["plan_summary"]
    assert summary["operation_count"] > 0
    assert summary["stripped_params"] == []
    assert "feedbackTOP" in summary["operators"]
    assert result["plan"]["blocked_questions"] == []
    assert "planner:host_authored_draft" in result["plan"]["grounding_evidence"]

    # The plan is cached server-side under td://project/state.
    cached = resources.get_cached_resource("td://project/state")
    assert cached is not None
    assert cached["latest_brain_plan"]["id"] == plan_id

    # plan_id round-trips into td_brain_execute without echoing the plan.
    tx_result = TransactionResult(
        plan_id="patch-1",
        status="dry_run",
        validation_failed=False,
        rollback_performed=False,
    )

    async def fake_run_transaction(*args, **kwargs):
        return tx_result

    monkeypatch.setattr(tools_brain, "_run_transaction", fake_run_transaction)
    monkeypatch.setattr(tools_brain, "_export_trace_safely", lambda **kwargs: None)
    monkeypatch.setattr(tools_brain, "_cache_transaction", lambda *args, **kwargs: None)

    exec_result = asyncio.run(
        tools_brain.td_brain_execute(mcp_ctx, plan_id=plan_id, transaction_policy="dry_run")
    )

    assert exec_result["success"] is True
    assert exec_result["trace"]["plan_id"] == plan_id


def test_propose_invalid_draft_returns_machine_readable_rejections(quiet_tr, service_container, mcp_ctx):
    quiet_tr.responses = _feedback_families_client().responses
    service_container.card_index = _feedback_card_index()
    draft = _valid_feedback_draft()
    draft["edges"].append({"source": "src", "target": "missing_concept", "kind": "data"})

    result = asyncio.run(tools_brain.td_brain_propose(mcp_ctx, draft))

    assert result["success"] is False
    assert result["rejections"], "rejections must be non-empty and machine-readable"
    first = result["rejections"][0]
    assert first["code"] == "invalid_schema"
    assert first["fix"]
    assert result["review"]["accepted"] is False


def test_propose_rejects_operators_without_docs_or_availability(quiet_tr, service_container, mcp_ctx):
    quiet_tr.responses = {
        "families": {"families": {"TOP": ["noise", "null"]}},
        "nodes": {"nodes": []},
    }
    service_container.card_index = SearchableCardIndex(
        {op_type: _operator_card(op_type) for op_type in ("noiseTOP", "nullTOP")}
    )

    result = asyncio.run(tools_brain.td_brain_propose(mcp_ctx, _valid_feedback_draft()))

    assert result["success"] is False
    codes = {item["code"] for item in result["rejections"]}
    assert "missing_docs" in codes
    assert "unavailable_op" in codes
    subjects = {item["subject"] for item in result["rejections"]}
    assert "feedbackTOP" in subjects


def test_propose_surfaces_stripped_params_loudly(quiet_tr, service_container, mcp_ctx):
    """Out-of-registry param values are STRIPPED by the review gate (test-encoded
    contract in tests/brain/test_llm_contract.py) — propose must surface them in
    plan_summary.stripped_params instead of changing that polarity."""
    quiet_tr.responses = _feedback_families_client().responses
    service_container.card_index = _feedback_card_index()
    draft = _valid_feedback_draft()
    draft["concepts"][1]["params"] = {
        "top": "${path:composite}",
        "hallucinateddecay": 0.5,
    }

    result = asyncio.run(tools_brain.td_brain_propose(mcp_ctx, draft))

    assert result["success"] is True
    assert (
        "removed_unverified_param:feedbackTOP.hallucinateddecay" in result["plan_summary"]["stripped_params"]
    )


def test_blocked_open_prompt_plan_points_to_the_ground_propose_loop():
    client = RecordingTDClient(
        responses={
            "families": {"families": {"TOP": ["noise"]}},
            "nodes": {"nodes": []},
        }
    )
    index = SearchableCardIndex({"noiseTOP": _operator_card("noiseTOP")})

    plan = asyncio.run(
        build_brain_plan(
            client,
            intent="ceremonial clock sculpture with memory ribbons and quiet stage cues",
            target_root="/project1",
            card_index=index,
        )
    )

    assert plan.blocked_questions
    assert "td_brain_ground" in plan.blocked_questions[0]
    assert "td_brain_propose" in plan.blocked_questions[0]
