from __future__ import annotations

import json
from pathlib import Path

from td_mcp.brain.hook_check import evaluate_post_tool_use, evaluate_release_stop

ROOT = Path(__file__).resolve().parent.parent.parent


def test_post_tool_use_hook_blocks_manual_recovery_result():
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "mcp__touchdesigner__td_brain_execute",
        "tool_response": {
            "success": False,
            "result": {
                "status": "broken",
                "needs_manual_recovery": True,
                "failed_op": 3,
                "failed_reason": "node/create failed",
                "before_snapshot_id": "snap-123",
            },
        },
    }

    output = evaluate_post_tool_use(payload)

    assert output["decision"] == "block"
    assert "needs_manual_recovery" in output["reason"]
    assert "snap-123" in output["hookSpecificOutput"]["additionalContext"]


def test_post_tool_use_hook_warns_when_clean_result_needs_review():
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "td_brain_execute",
        "tool_response": {
            "success": True,
            "result": {
                "status": "clean",
                "validation_failed": False,
                "rollback_performed": False,
                "validation_report": {"ok": True, "summary": "clean"},
            },
            "learned_memory_id": "mem-1",
        },
    }

    output = evaluate_post_tool_use(payload)

    assert "decision" not in output
    assert "validation ok" in output["hookSpecificOutput"]["additionalContext"]
    assert "mem-1" in output["hookSpecificOutput"]["additionalContext"]


def test_post_tool_use_hook_blocks_learning_from_failed_validation():
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "td_transaction_apply",
        "tool_response": {
            "success": True,
            "result": {
                "status": "warnings",
                "validation_failed": True,
                "validation_report": {"ok": False, "summary": "compile error"},
            },
            "learned_memory_id": "bad-memory",
        },
    }

    output = evaluate_post_tool_use(payload)

    assert output["decision"] == "block"
    assert "learned memory from failed validation" in output["reason"]


def test_release_stop_hook_runs_audits_for_relevant_files():
    output = evaluate_release_stop(
        {"hook_event_name": "Stop"},
        root=ROOT,
        changed_files=["plugins/tdpilot/.mcp.json", "skills/tdpilot-brain-release/SKILL.md"],
    )

    assert output["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert "skill audit ok" in output["hookSpecificOutput"]["additionalContext"]
    assert "plugin surface audit ok" in output["hookSpecificOutput"]["additionalContext"]
    assert "atlas audit ok" in output["hookSpecificOutput"]["additionalContext"]


def test_hooks_json_uses_deterministic_hook_module_and_is_mirrored():
    root_hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    plugin_hooks = json.loads(
        (ROOT / "plugins" / "tdpilot" / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )

    assert plugin_hooks == root_hooks
    hook_text = json.dumps(root_hooks)
    assert "td_mcp.brain.hook_check" in hook_text
    assert "PostToolUse" in root_hooks["hooks"]
    assert "Stop" in root_hooks["hooks"]
