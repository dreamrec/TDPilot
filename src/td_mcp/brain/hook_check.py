"""Deterministic Claude hook checks for TDPilot brain workflows."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 support.
    tomllib = None  # type: ignore[assignment]

from td_mcp.brain.atlas_audit import audit_brain_atlas
from td_mcp.brain.plugin_surface import audit_plugin_surface
from td_mcp.brain.skill_audit import audit_brain_skills

BRAIN_TRANSACTION_TOOLS = ("td_brain_execute", "td_transaction_apply")
GIT_TIMEOUT_SECONDS = 5
SOURCE_REPO_MARKERS = (
    ".claude/settings.json",
    "mcp/manifest.json",
    "scripts/audit_brain_atlas.py",
    "scripts/audit_brain_skills.py",
    "scripts/audit_plugin_surface.py",
    "src/td_mcp/brain/hook_check.py",
)
RELEASE_RELEVANT_PREFIXES = (
    ".agents/",
    ".claude/hooks/",
    ".claude/settings.json",
    ".claude-plugin/",
    ".codex/",
    "AGENTS.md",
    "agents/",
    "hooks/",
    "mcp/manifest.json",
    "plugins/tdpilot/",
    "scripts/audit_brain_atlas.py",
    "scripts/audit_brain_skills.py",
    "scripts/audit_plugin_surface.py",
    "scripts/brain_live_smoke.py",
    "skills/tdpilot-brain-",
    "src/td_mcp/brain/",
    "src/td_mcp/knowledge/cards/operators/",
    "src/td_mcp/registry/tools_brain.py",
    "tests/brain/",
    "tests/test_brain_plugin_packaging.py",
    "tests/test_brain_skill_quality.py",
)


def evaluate_post_tool_use(payload: dict[str, Any]) -> dict[str, Any]:
    """Return Claude hook JSON for brain transaction PostToolUse events."""
    tool_name = str(payload.get("tool_name") or payload.get("tool") or payload.get("name") or "")
    if not _is_brain_transaction_tool(tool_name):
        return _silent()

    response = payload.get("tool_response")
    if not isinstance(response, dict):
        response = payload.get("tool_result") if isinstance(payload.get("tool_result"), dict) else {}
    result = _transaction_result(response)
    issues = _transaction_issues(response, result)
    context = _transaction_context(response, result, issues)
    output = _context("PostToolUse", context)
    critical = [issue for issue in issues if issue.startswith("critical:")]
    if critical:
        output["decision"] = "block"
        output["reason"] = "; ".join(issue.removeprefix("critical:") for issue in critical)
    return output


def evaluate_release_stop(
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    """Return Claude hook JSON for Stop events when release surfaces changed."""
    if payload.get("stop_hook_active") is True:
        return _silent()

    project_cwd = root or payload.get("cwd")
    if not project_cwd:
        return _silent()
    repo_root = _resolve_tdpilot_source_root(Path(project_cwd))
    if repo_root is None:
        return _silent()

    changed = changed_files if changed_files is not None else _changed_files(repo_root)
    if changed is None:
        return _silent()
    relevant = [path for path in changed if _release_relevant(path)]
    if not relevant:
        return _silent()

    try:
        skill_report = audit_brain_skills(repo_root)
        plugin_report = audit_plugin_surface(repo_root)
        atlas_report = audit_brain_atlas(repo_root)
    except Exception:  # noqa: BLE001 - a Stop hook must fail open.
        return _silent()
    messages = [
        f"TDPilot release hook: {len(relevant)} release-relevant file(s) changed.",
        "skill audit ok" if skill_report["ok"] else "skill audit failed",
        "plugin surface audit ok" if plugin_report["ok"] else "plugin surface audit failed",
        "atlas audit ok" if atlas_report["ok"] else "atlas audit failed",
        "Run before handoff: uv run pytest -q; uv run python scripts/brain_live_smoke.py --live --timeout 5",
    ]
    output = _context("Stop", " ".join(messages))
    failures = []
    if not skill_report["ok"]:
        failures.append("skill audit failed")
    if not plugin_report["ok"]:
        failures.append("plugin surface audit failed")
    if not atlas_report["ok"]:
        failures.append("atlas audit failed")
    if failures:
        output["decision"] = "block"
        output["reason"] = "; ".join(failures)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("post-tool-use", "release-stop"))
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}

    if args.mode == "post-tool-use":
        output = evaluate_post_tool_use(payload)
    else:
        output = evaluate_release_stop(payload, root=args.root)
    if output:
        print(json.dumps(output, separators=(",", ":")))
    return 0


def _transaction_result(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    if isinstance(result, dict):
        return result
    if isinstance(response.get("transaction_result"), dict):
        return response["transaction_result"]
    return response


def _transaction_issues(response: dict[str, Any], result: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    status = str(result.get("status") or "")
    validation_failed = bool(result.get("validation_failed"))
    if response.get("success") is False:
        issues.append("critical:tool returned success=false")
    if result.get("needs_manual_recovery"):
        issues.append("critical:needs_manual_recovery is true")
    if validation_failed:
        issues.append("critical:validation_failed is true")
    if status in {"broken", "rolled_back", "blocked"}:
        issues.append(f"critical:transaction status is {status}")
    if response.get("learned_memory_id") and (validation_failed or status not in {"clean", "warnings"}):
        issues.append("critical:learned memory from failed validation")
    if status not in {"clean", "warnings", "dry_run"} and status:
        issues.append(f"warning:unexpected status {status}")
    if status != "dry_run" and not isinstance(result.get("validation_report"), dict):
        issues.append("warning:missing validation_report")
    if result.get("rollback_performed"):
        issues.append("warning:rollback_performed is true")
    return issues


def _transaction_context(response: dict[str, Any], result: dict[str, Any], issues: list[str]) -> str:
    validation = result.get("validation_report") if isinstance(result.get("validation_report"), dict) else {}
    parts = [
        "TDPilot brain hook:",
        f"status={result.get('status', 'unknown')}",
        "validation ok"
        if validation.get("ok") is True and not result.get("validation_failed")
        else "validation needs review",
    ]
    if result.get("before_snapshot_id"):
        parts.append(f"snapshot={result['before_snapshot_id']}")
    if result.get("failed_op") is not None:
        parts.append(f"failed_op={result['failed_op']}")
    if result.get("failed_reason"):
        parts.append(f"failed_reason={result['failed_reason']}")
    if response.get("learned_memory_id"):
        parts.append(f"learned_memory_id={response['learned_memory_id']}")
    if issues:
        parts.append("issues=" + ", ".join(issues))
    return " ".join(str(part) for part in parts)


def _is_brain_transaction_tool(tool_name: str) -> bool:
    return any(tool_name == name or tool_name.endswith(f"__{name}") for name in BRAIN_TRANSACTION_TOOLS)


def _resolve_tdpilot_source_root(project_cwd: Path) -> Path | None:
    """Resolve and authenticate the source repository targeted by a Stop hook."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_cwd), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        root = Path(proc.stdout.strip()).expanduser().resolve()
    except (OSError, subprocess.SubprocessError):
        return None
    return root if _is_tdpilot_source_repo(root) else None


def _is_tdpilot_source_repo(root: Path) -> bool:
    if not root.is_dir() or not all((root / marker).is_file() for marker in SOURCE_REPO_MARKERS):
        return False
    if _project_name(root / "pyproject.toml") != "tdpilot":
        return False
    try:
        manifest = json.loads((root / "mcp" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(manifest, dict) and manifest.get("slug") == "tdpilot"


def _project_name(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    if tomllib is not None:
        try:
            project = tomllib.loads(text).get("project")
        except tomllib.TOMLDecodeError:
            return None
        return str(project.get("name")) if isinstance(project, dict) and project.get("name") else None
    project_section = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", text)
    if project_section is None:
        return None
    match = re.search(r'(?m)^name\s*=\s*["\']([^"\']+)["\']\s*$', project_section.group(1))
    return match.group(1) if match else None


def _changed_files(root: Path) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    changed: list[str] = []
    for line in proc.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            changed.append(path)
    return changed


def _release_relevant(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in RELEASE_RELEVANT_PREFIXES)


def _context(event_name: str, message: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": message[:9000],
        }
    }


def _silent() -> dict[str, Any]:
    return {"suppressOutput": True}


if __name__ == "__main__":
    raise SystemExit(main())
