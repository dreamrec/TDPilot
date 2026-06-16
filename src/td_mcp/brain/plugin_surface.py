"""Audit Codex/Claude/plugin distribution surfaces for the TDPilot brain."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

EXPECTED_BRAIN_SKILLS = (
    "tdpilot-brain-builder",
    "tdpilot-brain-explorer",
    "tdpilot-brain-recovery",
    "tdpilot-brain-release",
    "tdpilot-brain-validator",
)
EXPECTED_AGENTS = (
    "td-brain-builder.md",
    "td-brain-explorer.md",
    "td-brain-validator.md",
    "td-release-auditor.md",
)
PERSONAL_PATH_RE = re.compile(r"/Users/[A-Za-z][A-Za-z0-9._-]*/|C:\\Users\\[A-Za-z]|/home/[a-z][a-z0-9_-]{2,}/")


def audit_plugin_surface(root: str | Path) -> dict[str, Any]:
    """Return a JSON-serializable report for v2 plugin packaging integrity."""
    repo_root = Path(root)
    missing = _missing_artifacts(repo_root)
    mirror_mismatches = _mirror_mismatches(repo_root)
    personal_path_leaks = _personal_path_leaks(repo_root)
    codex_manifest = _read_json(repo_root / "plugins" / "tdpilot" / ".codex-plugin" / "plugin.json")
    claude_manifest = _read_json(repo_root / ".claude-plugin" / "plugin.json")
    mcp_config = _mcp_config_report(repo_root)
    hooks = _read_json(repo_root / "hooks" / "hooks.json")
    hook_report = _hook_report(hooks)
    tool_count = _tool_count(repo_root)

    return {
        "schema_version": 1,
        "ok": not missing and not mirror_mismatches and not personal_path_leaks and mcp_config["uses_plugin_root_placeholder"],
        "tool_count": tool_count,
        "brain_skill_count": len(EXPECTED_BRAIN_SKILLS),
        "agent_count": len(EXPECTED_AGENTS),
        "hook_count": hook_report["hook_count"],
        "hooks": hook_report,
        "missing_artifacts": missing,
        "mirror_mismatches": mirror_mismatches,
        "personal_path_leaks": personal_path_leaks,
        "mcp_config": mcp_config,
        "codex_manifest": {
            "name": codex_manifest.get("name"),
            "version": codex_manifest.get("version"),
            "has_skills": codex_manifest.get("skills") == "./skills/",
            "has_agents": codex_manifest.get("agents") == "./agents/",
            "has_mcp_servers": codex_manifest.get("mcpServers") == "./.mcp.json",
        },
        "claude_manifest": {
            "name": claude_manifest.get("name"),
            "version": claude_manifest.get("version"),
            "has_skills": claude_manifest.get("skills") == "./skills/",
            "has_agents": claude_manifest.get("agents") == "./agents/",
            "has_hooks": claude_manifest.get("hooks") == "./hooks/hooks.json",
            "has_mcp_servers": claude_manifest.get("mcpServers") == "./.mcp.json",
        },
    }


def _missing_artifacts(root: Path) -> list[str]:
    paths: list[Path] = [
        root / "plugins" / "tdpilot" / ".codex-plugin" / "plugin.json",
        root / "plugins" / "tdpilot" / ".mcp.json",
        root / ".claude-plugin" / "plugin.json",
        root / ".claude-plugin" / "marketplace.json",
        root / ".agents" / "plugins" / "marketplace.json",
        root / "hooks" / "hooks.json",
        root / "plugins" / "tdpilot" / "hooks" / "hooks.json",
    ]
    paths.extend(root / "skills" / name / "SKILL.md" for name in EXPECTED_BRAIN_SKILLS)
    paths.extend(root / ".agents" / "skills" / name / "SKILL.md" for name in EXPECTED_BRAIN_SKILLS)
    paths.extend(root / "plugins" / "tdpilot" / "skills" / name / "SKILL.md" for name in EXPECTED_BRAIN_SKILLS)
    paths.extend(root / "agents" / name for name in EXPECTED_AGENTS)
    paths.extend(root / "plugins" / "tdpilot" / "agents" / name for name in EXPECTED_AGENTS)
    return [str(path.relative_to(root)) for path in paths if not path.exists()]


def _mirror_mismatches(root: Path) -> list[str]:
    mismatches: list[str] = []
    for name in EXPECTED_BRAIN_SKILLS:
        canonical = root / "skills" / name / "SKILL.md"
        for mirror in (
            root / ".agents" / "skills" / name / "SKILL.md",
            root / "plugins" / "tdpilot" / "skills" / name / "SKILL.md",
        ):
            if canonical.exists() and mirror.exists() and canonical.read_text(encoding="utf-8") != mirror.read_text(encoding="utf-8"):
                mismatches.append(f"{mirror.relative_to(root)} differs from {canonical.relative_to(root)}")
    for agent in EXPECTED_AGENTS:
        canonical = root / "agents" / agent
        mirror = root / "plugins" / "tdpilot" / "agents" / agent
        if canonical.exists() and mirror.exists() and canonical.read_text(encoding="utf-8") != mirror.read_text(encoding="utf-8"):
            mismatches.append(f"{mirror.relative_to(root)} differs from {canonical.relative_to(root)}")
    root_hooks = root / "hooks" / "hooks.json"
    plugin_hooks = root / "plugins" / "tdpilot" / "hooks" / "hooks.json"
    if root_hooks.exists() and plugin_hooks.exists() and root_hooks.read_text(encoding="utf-8") != plugin_hooks.read_text(encoding="utf-8"):
        mismatches.append("plugins/tdpilot/hooks/hooks.json differs from hooks/hooks.json")
    return mismatches


def _personal_path_leaks(root: Path) -> list[str]:
    leaks: list[str] = []
    search_roots = (
        root / "plugins" / "tdpilot",
        root / ".claude-plugin",
        root / ".agents",
        root / ".codex",
        root / "agents",
        root / "hooks",
        root / "skills",
    )
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in sorted(item for item in search_root.rglob("*") if item.is_file()):
            if path.suffix in {".tox", ".png", ".jpg", ".jpeg", ".zip"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if PERSONAL_PATH_RE.search(text):
                leaks.append(str(path.relative_to(root)))
    return leaks


def _mcp_config_report(root: Path) -> dict[str, Any]:
    path = root / "plugins" / "tdpilot" / ".mcp.json"
    data = _read_json(path)
    server = (data.get("mcpServers") or {}).get("touchdesigner", {}) if isinstance(data, dict) else {}
    args = server.get("args") or []
    return {
        "path": "plugins/tdpilot/.mcp.json",
        "command": server.get("command"),
        "args": args,
        "uses_plugin_root_placeholder": "${CLAUDE_PLUGIN_ROOT}" in args or "${CODEX_PLUGIN_ROOT}" in args,
    }


def _hook_report(hooks: dict[str, Any]) -> dict[str, Any]:
    hook_groups = hooks.get("hooks", {}) if isinstance(hooks, dict) else {}
    text = json.dumps(hooks)
    return {
        "hook_count": sum(len(value) for value in hook_groups.values() if isinstance(value, list)),
        "uses_hook_check_module": "td_mcp.brain.hook_check" in text,
        "has_post_tool_use_guard": "post-tool-use" in text and "PostToolUse" in hook_groups,
        "has_stop_release_guard": "release-stop" in text and "Stop" in hook_groups,
    }


def _tool_count(root: Path) -> int:
    manifest = _read_json(root / "mcp" / "manifest.json")
    surface = manifest.get("surface") if isinstance(manifest.get("surface"), dict) else {}
    return int(surface.get("tool_count") or manifest.get("tool_count") or len(manifest.get("tools") or []))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = ["audit_plugin_surface"]
