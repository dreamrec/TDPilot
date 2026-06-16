from __future__ import annotations

import asyncio

import td_mcp.server as server
from td_mcp.brain.cockpit import build_cockpit_payload


def test_brain_tools_are_registered_with_mcp_metadata():
    tools = asyncio.run(server.mcp.list_tools())
    by_name = {tool.name: tool for tool in tools}

    for name in ("td_brain_plan", "td_brain_execute", "td_transaction_apply", "td_cockpit_render"):
        assert name in by_name
        assert by_name[name].title
        assert by_name[name].description.startswith("Use this when")

    assert by_name["td_brain_plan"].annotations.readOnlyHint is True
    assert by_name["td_brain_execute"].annotations.destructiveHint is True
    assert by_name["td_transaction_apply"].annotations.destructiveHint is True
    assert by_name["td_cockpit_render"].annotations.readOnlyHint is True
    assert by_name["td_cockpit_render"].annotations.destructiveHint is False
    assert by_name["td_cockpit_render"].meta["ui"]["resourceUri"] == "ui://tdpilot/cockpit.html"
    assert by_name["td_cockpit_render"].meta["openai/outputTemplate"] == "ui://tdpilot/cockpit.html"


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
    assert payload["transaction"]["status"] == "clean"
    assert payload["transaction"]["snapshot_id"] == "snap-1"
    assert payload["validation"]["status"] == "passed"
    assert payload["rollback"]["needs_manual_recovery"] is False
    assert payload["trace"]["trace_id"] == "trace-1"


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
