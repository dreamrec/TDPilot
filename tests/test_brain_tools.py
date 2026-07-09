from __future__ import annotations

import asyncio

import td_mcp.server as server
from td_mcp.brain.cockpit import build_cockpit_payload
from td_mcp.models.brain import BrainPlan, ConceptGraph, TransactionResult, VisualTaskSpec
from td_mcp.models.patch import PatchPlan, ValidationPlan
from td_mcp.registry import tools_brain


def test_brain_tools_are_registered_with_mcp_metadata():
    tools = asyncio.run(server.mcp.list_tools())
    by_name = {tool.name: tool for tool in tools}

    for name in ("td_brain_plan", "td_brain_execute", "td_transaction_apply", "td_cockpit_render"):
        assert name in by_name
        assert by_name[name].title
        # Batch F2 disambiguation prefixed some of these descriptions with a
        # role tag ("DEFAULT planning entry point:", "Low-level executor:", …),
        # so they no longer *start* with "Use this when". The house-style
        # usage-oriented phrasing is preserved mid-sentence — assert on that.
        assert "use this when" in (by_name[name].description or "").lower()

    assert by_name["td_brain_plan"].annotations.readOnlyHint is True
    assert by_name["td_brain_execute"].annotations.destructiveHint is True
    assert by_name["td_transaction_apply"].annotations.destructiveHint is True
    assert by_name["td_cockpit_render"].annotations.readOnlyHint is True
    assert by_name["td_cockpit_render"].annotations.destructiveHint is False
    assert by_name["td_cockpit_render"].meta["ui"]["resourceUri"] == "ui://tdpilot/cockpit.html"
    assert by_name["td_cockpit_render"].meta["openai/outputTemplate"] == "ui://tdpilot/cockpit.html"


def test_legacy_patch_surfaces_guide_tool_choice_to_brain_loop():
    tools = asyncio.run(server.mcp.list_tools())
    by_name = {tool.name: tool for tool in tools}

    legacy_plan_tools = ("td_plan_patch", "td_patch_plan", "td_patch_preview")
    for name in legacy_plan_tools:
        assert "td_brain_plan" in (by_name[name].description or "")
        assert by_name[name].annotations.readOnlyHint is True
        assert by_name[name].annotations.destructiveHint is False

    assert "td_brain_execute" in (by_name["td_patch_apply"].description or "")
    assert by_name["td_patch_apply"].annotations.destructiveHint is True
    assert by_name["td_patch_apply"].annotations.readOnlyHint is False


def test_cockpit_html_resource_is_registered_for_mcp_apps():
    resources = asyncio.run(server.mcp.list_resources())
    by_uri = {str(resource.uri): resource for resource in resources}

    assert "ui://tdpilot/cockpit.html" in by_uri
    resource = by_uri["ui://tdpilot/cockpit.html"]
    assert resource.mimeType == "text/html;profile=mcp-app"
    assert resource.name == "tdpilot_cockpit"


def test_cockpit_payload_summarizes_brain_plan_transaction_and_validation():
    plan = {
        "id": "brain-1",
        "task": {"intent": "Build feedback loop", "target_root": "/project1", "output_top": "/project1/out1"},
        "concept_graph": {
            "id": "graph-1",
            "profile": "feedback",
            "nodes": [{"id": "src", "label": "source", "operator": "noiseTOP"}],
            "edges": [{"source": "src", "target": "fb", "kind": "image-flow"}],
            "operators": ["noiseTOP", "feedbackTOP", "levelTOP", "nullTOP"],
        },
        "patch_plan": {"operations": [{"kind": "create_node"}, {"kind": "connect"}]},
        "validation_profile": "structural_visual_safe",
        "risk_flags": ["feedback-static-warning-review"],
        "blocked_questions": [],
        "missing_facts": [],
        "substitution_explanations": [
            {
                "missing_op": "audiofileinCHOP",
                "replacement_target": "audio_device_to_analysis_chop",
                "replacement_ops": ["audiodeviceinCHOP"],
                "confidence": "medium",
                "requires_approval": True,
                "approval_state": "approved",
                "approval_evidence": ["device-source-declared:audio_device"],
                "availability_reason": "missing from live family list",
                "tradeoffs": ["uses a live audio input device instead of a deterministic audio file"],
                "official_sources": [
                    "https://docs.derivative.ca/Audio_File_In_CHOP",
                    "https://docs.derivative.ca/Audio_Device_In_CHOP",
                ],
                "summary": "audiofileinCHOP is unavailable; using audiodeviceinCHOP.",
            }
        ],
        "corpus_evidence": [
            {
                "evidence_id": "corpus:exact:feedbackTOP",
                "source": "exact_operator",
                "op_type": "feedbackTOP",
                "family": "TOP",
                "display_name": "Feedback TOP",
                "docs_url": "https://docs.derivative.ca/Feedback_TOP",
                "summary": "Feedback TOP official docs summary.",
                "key_params": ["top", "reset"],
                "key_concepts": ["feedback effects"],
                "matched_terms": ["feedback"],
                "query": "feedbackTOP",
                "score": 0.92,
            }
        ],
    }
    transaction = {
        "status": "clean",
        "validation_failed": False,
        "rollback_performed": False,
        "needs_manual_recovery": False,
        "before_snapshot_id": "snap-1",
        "validation_report": {
            "status": "passed",
            "issues": [{"severity": "info", "message": "graph ok"}],
        },
    }

    payload = build_cockpit_payload(plan=plan, transaction_result=transaction, trace={"trace_id": "trace-1"})

    assert payload["schema_version"] == 1
    assert payload["mode"] == "render_only"
    assert payload["plan"]["id"] == "brain-1"
    assert payload["plan"]["profile"] == "feedback"
    assert payload["plan"]["operator_count"] == 4
    assert payload["plan"]["operation_count"] == 2
    assert payload["plan"]["corpus_evidence"][0]["evidence_id"] == "corpus:exact:feedbackTOP"
    assert payload["plan"]["corpus_evidence"][0]["docs_url"] == "https://docs.derivative.ca/Feedback_TOP"
    assert payload["plan"]["substitution_explanations"][0]["missing_op"] == "audiofileinCHOP"
    assert payload["plan"]["substitution_explanations"][0]["replacement_ops"] == ["audiodeviceinCHOP"]
    assert payload["plan"]["substitution_explanations"][0]["approval_state"] == "approved"
    assert payload["transaction"]["status"] == "clean"
    assert payload["transaction"]["snapshot_id"] == "snap-1"
    assert payload["validation"]["status"] == "passed"
    assert payload["rollback"]["needs_manual_recovery"] is False
    assert payload["trace"]["trace_id"] == "trace-1"


def test_cockpit_payload_reads_real_brain_plan_concepts_and_grounding_evidence():
    plan = {
        "id": "brain-2",
        "task": {"intent": "Build feedback loop", "target_root": "/project1"},
        "concept_graph": {
            "profile": "feedback",
            "concepts": [
                {"id": "source", "label": "Noise source", "role": "source", "op_type": "noiseTOP"},
                {"id": "out", "label": "Stable output", "role": "output", "op_type": "nullTOP"},
            ],
            "edges": [{"source": "source", "target": "out", "kind": "data"}],
            "operators": ["noiseTOP", "nullTOP"],
        },
        "patch_plan": {"operations": [{"kind": "create_node"}]},
        "grounding_evidence": ["profile:feedback", "corpus:exact:noiseTOP"],
    }

    payload = build_cockpit_payload(plan=plan)

    assert payload["plan"]["concept_nodes"][0]["id"] == "source"
    assert payload["plan"]["concept_edges"][0]["target"] == "out"
    assert payload["plan"]["grounding_evidence"] == ["profile:feedback", "corpus:exact:noiseTOP"]


def test_brain_prompts_are_registered():
    prompts = asyncio.run(server.mcp.list_prompts())
    names = {prompt.name for prompt in prompts}

    assert {
        "td_brain_build",
        "td_brain_debug",
        "td_brain_validate",
        "td_snapshot_before_edit",
        "td_recover_network",
        "td_learn_validated_technique",
    }.issubset(names)


def _minimal_brain_plan() -> BrainPlan:
    task = VisualTaskSpec(intent="Build a feedback loop", target_root="/project1")
    patch = PatchPlan(
        target_root="/project1",
        source="operations",
        operations=[],
        undo_label="brain transaction",
        validation_plan=ValidationPlan(target_root="/project1"),
    )
    graph = ConceptGraph(task=task, profile="feedback", concepts=[], edges=[], operators=["feedbackTOP"])
    return BrainPlan(task=task, concept_graph=graph, patch_plan=patch)


def test_brain_execute_does_not_learn_when_validation_failed(monkeypatch, mcp_ctx):
    learned_calls = []
    tx_result = TransactionResult(
        plan_id="patch-1",
        status="warnings",
        validation_failed=True,
        rollback_performed=False,
    )

    async def fake_run_transaction(*args, **kwargs):
        return tx_result

    async def fake_learn_trace(*args, **kwargs):
        learned_calls.append((args, kwargs))
        return "memory-1"

    monkeypatch.setattr(tools_brain._tr, "_start_tool", lambda ctx, name: lambda: None)
    monkeypatch.setattr(tools_brain._tr, "_audit_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(tools_brain, "_run_transaction", fake_run_transaction)
    monkeypatch.setattr(tools_brain, "_learn_brain_trace", fake_learn_trace)
    monkeypatch.setattr(tools_brain, "_export_trace_safely", lambda **kwargs: None)
    monkeypatch.setattr(tools_brain, "_cache_transaction", lambda *args, **kwargs: None)

    result = asyncio.run(
        tools_brain.td_brain_execute(
            mcp_ctx,
            _minimal_brain_plan().model_dump(mode="json"),
            transaction_policy="no_rollback",
            learn_on_success=True,
        )
    )

    assert learned_calls == []
    assert result["learned_memory_id"] is None
    assert result["trace"]["validation_ok"] is False


def test_brain_execute_requires_exactly_one_of_plan_or_plan_id(monkeypatch, mcp_ctx):
    monkeypatch.setattr(tools_brain._tr, "_start_tool", lambda ctx, name: lambda: None)

    neither = asyncio.run(tools_brain.td_brain_execute(mcp_ctx))
    assert neither["success"] is False
    assert neither["error"]["code"] == "INVALID_INPUT"

    both = asyncio.run(
        tools_brain.td_brain_execute(
            mcp_ctx,
            plan=_minimal_brain_plan().model_dump(mode="json"),
            plan_id="brain-anything",
        )
    )
    assert both["success"] is False
    assert both["error"]["code"] == "INVALID_INPUT"


def test_brain_execute_plan_id_resolves_the_cached_plan(monkeypatch, mcp_ctx):
    """plan_id passthrough: the host can execute the latest td_brain_plan
    result without echoing the full multi-KB plan back through its context."""
    brain_plan = _minimal_brain_plan()
    plan_dump = brain_plan.model_dump(mode="json")
    tx_result = TransactionResult(
        plan_id="patch-1",
        status="dry_run",
        validation_failed=False,
        rollback_performed=False,
    )

    async def fake_run_transaction(*args, **kwargs):
        return tx_result

    monkeypatch.setattr(tools_brain._tr, "_start_tool", lambda ctx, name: lambda: None)
    monkeypatch.setattr(tools_brain._tr, "_audit_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(tools_brain, "_run_transaction", fake_run_transaction)
    monkeypatch.setattr(tools_brain, "_export_trace_safely", lambda **kwargs: None)
    monkeypatch.setattr(tools_brain, "_cache_transaction", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tools_brain,
        "get_cached_resource",
        lambda uri: {"latest_brain_plan": plan_dump} if uri == "td://project/state" else None,
    )

    result = asyncio.run(
        tools_brain.td_brain_execute(mcp_ctx, plan_id=plan_dump["id"], transaction_policy="dry_run")
    )

    assert result["success"] is True
    assert result["trace"]["plan_id"] == plan_dump["id"]


def test_brain_execute_plan_id_miss_is_a_recoverable_error(monkeypatch, mcp_ctx):
    monkeypatch.setattr(tools_brain._tr, "_start_tool", lambda ctx, name: lambda: None)
    monkeypatch.setattr(tools_brain, "get_cached_resource", lambda uri: None)

    result = asyncio.run(tools_brain.td_brain_execute(mcp_ctx, plan_id="brain-stale-id"))

    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_INPUT"
    assert "td_brain_plan" in result["error"]["message"]
