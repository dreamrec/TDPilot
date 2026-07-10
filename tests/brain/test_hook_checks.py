from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from td_mcp.brain import hook_check
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


def test_release_stop_hook_suppresses_when_no_release_files_changed():
    output = evaluate_release_stop(
        {"hook_event_name": "Stop"},
        root=ROOT,
        changed_files=["README.md", "docs/notes.md"],
    )

    assert output == {"suppressOutput": True}


def test_release_stop_hook_suppresses_reentry():
    output = evaluate_release_stop(
        {"hook_event_name": "Stop", "stop_hook_active": True},
        root=ROOT,
        changed_files=["hooks/hooks.json"],
    )

    assert output == {"suppressOutput": True}


def test_release_stop_hook_suppresses_for_foreign_repository(tmp_path):
    foreign_root = tmp_path / "foreign"
    (foreign_root / "hooks").mkdir(parents=True)
    (foreign_root / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(foreign_root)], check=True)

    output = evaluate_release_stop(
        {"hook_event_name": "Stop", "cwd": str(foreign_root)},
        changed_files=["hooks/hooks.json", "AGENTS.md"],
    )

    assert output == {"suppressOutput": True}


def test_release_stop_hook_suppresses_spoofed_or_malformed_markers(tmp_path):
    foreign_root = tmp_path / "spoofed-tdpilot"
    for relative_path in hook_check.SOURCE_REPO_MARKERS:
        path = foreign_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    (foreign_root / "pyproject.toml").write_text(
        '[project]\nname = "tdpilot"\nversion = "0.0.1"\n',
        encoding="utf-8",
    )
    (foreign_root / "mcp" / "manifest.json").write_text(
        '{"slug":"not-tdpilot"}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(foreign_root)], check=True)

    output = evaluate_release_stop(
        {"hook_event_name": "Stop", "cwd": str(foreign_root)},
        changed_files=["hooks/hooks.json"],
    )

    assert output == {"suppressOutput": True}


def test_release_stop_hook_fails_open_when_git_resolution_times_out(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=hook_check.GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(hook_check.subprocess, "run", timeout)

    output = evaluate_release_stop(
        {"hook_event_name": "Stop", "cwd": str(ROOT)},
        changed_files=["hooks/hooks.json"],
    )

    assert output == {"suppressOutput": True}


def test_release_stop_hook_resolves_git_top_level_from_nested_project_path():
    output = evaluate_release_stop(
        {"hook_event_name": "Stop"},
        root=ROOT / "tests" / "brain",
        changed_files=["hooks/hooks.json"],
    )

    assert output["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert "plugin surface audit ok" in output["hookSpecificOutput"]["additionalContext"]


def test_hooks_json_uses_deterministic_hook_module_and_is_mirrored():
    root_hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    plugin_hooks = json.loads(
        (ROOT / "plugins" / "tdpilot" / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )

    assert plugin_hooks == root_hooks
    hook_text = json.dumps(root_hooks)
    assert "hooks/run_hook.py" in hook_text
    assert "td_mcp.brain.hook_check" in (ROOT / "hooks" / "run_hook.py").read_text(encoding="utf-8")
    assert "PostToolUse" in root_hooks["hooks"]
    assert "Stop" not in root_hooks["hooks"]
    assert "CLAUDE_PROJECT_DIR" not in hook_text
    assert "CODEX_PROJECT_DIR" not in hook_text

    project_settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert "release-stop" in json.dumps(project_settings["hooks"]["Stop"])


def test_hook_runner_delegates_from_its_own_source_root():
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "hooks" / "run_hook.py"),
            "post-tool-use",
            "--root",
            str(ROOT),
        ],
        input=json.dumps(
            {
                "tool_name": "td_brain_execute",
                "tool_response": {
                    "success": True,
                    "result": {
                        "status": "clean",
                        "validation_failed": False,
                        "validation_report": {"ok": True},
                    },
                },
            }
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "validation ok" in payload["hookSpecificOutput"]["additionalContext"]


def test_hook_runner_never_executes_from_foreign_project_roots(tmp_path):
    foreign_root = tmp_path / "foreign"
    (foreign_root / "hooks").mkdir(parents=True)
    shutil.copy2(ROOT / "hooks" / "run_hook.py", foreign_root / "hooks" / "run_hook.py")
    (foreign_root / "src" / "td_mcp" / "brain").mkdir(parents=True)
    (foreign_root / "src" / "td_mcp" / "brain" / "hook_check.py").write_text(
        "raise RuntimeError('foreign code executed')\n",
        encoding="utf-8",
    )
    (foreign_root / "pyproject.toml").write_text(
        '[project]\nname = "foreign-project"\nversion = "0.0.1"\n',
        encoding="utf-8",
    )
    env = {
        "HOME": str(tmp_path / "empty-home"),
        "PATH": str(Path(sys.executable).parent),
        "CLAUDE_PROJECT_DIR": str(foreign_root),
        "CODEX_PROJECT_DIR": str(foreign_root),
        "PWD": str(foreign_root),
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(foreign_root / "hooks" / "run_hook.py"),
            "post-tool-use",
            "--root",
            str(foreign_root),
        ],
        cwd=foreign_root,
        env=env,
        input=json.dumps({"tool_name": "td_brain_execute"}),
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stdout == ""
    assert "foreign code executed" not in proc.stderr
