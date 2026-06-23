"""Audit Codex/Claude/plugin distribution surfaces for the TDPilot brain."""

from __future__ import annotations

import asyncio
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
PERSONAL_PATH_RE = re.compile(
    r"/Users/[A-Za-z][A-Za-z0-9._-]*/|C:\\Users\\[A-Za-z]|/home/[a-z][a-z0-9_-]{2,}/"
)
HOSTED_LLM_DEPENDENCY_NAMES = {
    "anthropic",
    "cohere",
    "google-generativeai",
    "google-genai",
    "groq",
    "langchain",
    "llama-index",
    "mistralai",
    "openai",
    "together",
}
HOSTED_LLM_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+(openai|anthropic|cohere|mistralai|groq|together)\b|import\s+"
    r"(openai|anthropic|cohere|mistralai|groq|together)\b)",
    re.MULTILINE,
)
HOSTED_LLM_ENV_RE = re.compile(
    r"\b(?:OPENAI|ANTHROPIC|GOOGLE|COHERE|MISTRAL|OPENROUTER|TOGETHER|GROQ)_API_KEY\b"
)


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
    hook_report = _hook_report(repo_root, hooks)
    tool_count = _tool_count(repo_root)
    registry_tool_count = _registry_tool_count()
    local_first = _local_first_report(repo_root)

    return {
        "schema_version": 1,
        "ok": not missing
        and not mirror_mismatches
        and not personal_path_leaks
        and mcp_config["uses_plugin_root_placeholder"]
        and registry_tool_count == tool_count
        and local_first["ok"],
        "tool_count": tool_count,
        "registry_tool_count": registry_tool_count,
        "brain_skill_count": len(EXPECTED_BRAIN_SKILLS),
        "agent_count": len(EXPECTED_AGENTS),
        "hook_count": hook_report["hook_count"],
        "hooks": hook_report,
        "missing_artifacts": missing,
        "mirror_mismatches": mirror_mismatches,
        "personal_path_leaks": personal_path_leaks,
        "local_first": local_first,
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
        root / "hooks" / "run_hook.py",
        root / "plugins" / "tdpilot" / "hooks" / "hooks.json",
        root / "plugins" / "tdpilot" / "hooks" / "run_hook.py",
    ]
    paths.extend(root / "skills" / name / "SKILL.md" for name in EXPECTED_BRAIN_SKILLS)
    paths.extend(root / ".agents" / "skills" / name / "SKILL.md" for name in EXPECTED_BRAIN_SKILLS)
    paths.extend(
        root / "plugins" / "tdpilot" / "skills" / name / "SKILL.md" for name in EXPECTED_BRAIN_SKILLS
    )
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
            if (
                canonical.exists()
                and mirror.exists()
                and canonical.read_text(encoding="utf-8") != mirror.read_text(encoding="utf-8")
            ):
                mismatches.append(f"{mirror.relative_to(root)} differs from {canonical.relative_to(root)}")
    for agent in EXPECTED_AGENTS:
        canonical = root / "agents" / agent
        mirror = root / "plugins" / "tdpilot" / "agents" / agent
        if (
            canonical.exists()
            and mirror.exists()
            and canonical.read_text(encoding="utf-8") != mirror.read_text(encoding="utf-8")
        ):
            mismatches.append(f"{mirror.relative_to(root)} differs from {canonical.relative_to(root)}")
    root_hooks = root / "hooks" / "hooks.json"
    plugin_hooks = root / "plugins" / "tdpilot" / "hooks" / "hooks.json"
    if (
        root_hooks.exists()
        and plugin_hooks.exists()
        and root_hooks.read_text(encoding="utf-8") != plugin_hooks.read_text(encoding="utf-8")
    ):
        mismatches.append("plugins/tdpilot/hooks/hooks.json differs from hooks/hooks.json")
    root_hook_runner = root / "hooks" / "run_hook.py"
    plugin_hook_runner = root / "plugins" / "tdpilot" / "hooks" / "run_hook.py"
    if (
        root_hook_runner.exists()
        and plugin_hook_runner.exists()
        and root_hook_runner.read_text(encoding="utf-8") != plugin_hook_runner.read_text(encoding="utf-8")
    ):
        mismatches.append("plugins/tdpilot/hooks/run_hook.py differs from hooks/run_hook.py")
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


def _local_first_report(root: Path) -> dict[str, Any]:
    leaks: list[str] = []

    for dependency in _project_dependency_names(root / "pyproject.toml"):
        if dependency in HOSTED_LLM_DEPENDENCY_NAMES:
            leaks.append(f"pyproject.toml dependency {dependency}")

    source_root = root / "src" / "td_mcp"
    if source_root.exists():
        for path in sorted(source_root.rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in HOSTED_LLM_IMPORT_RE.finditer(text):
                package = next(group for group in match.groups() if group)
                leaks.append(f"{path.relative_to(root)} hosted SDK import {package}")
            for match in HOSTED_LLM_ENV_RE.finditer(text):
                leaks.append(f"{path.relative_to(root)} hosted API key dependency {match.group(0)}")

    return {
        "ok": not leaks,
        "hosted_llm_dependency_leaks": leaks,
    }


def _project_dependency_names(path: Path) -> list[str]:
    if not path.exists():
        return []

    try:
        import tomllib
    except ModuleNotFoundError:
        return _fallback_project_dependency_names(path.read_text(encoding="utf-8", errors="ignore"))

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {}) if isinstance(data, dict) else {}
    dependencies = list(project.get("dependencies") or [])
    optional = project.get("optional-dependencies") or {}
    if isinstance(optional, dict):
        for values in optional.values():
            dependencies.extend(values or [])
    return [_dependency_name(str(value)) for value in dependencies if _dependency_name(str(value))]


def _fallback_project_dependency_names(text: str) -> list[str]:
    return [
        name
        for value in re.findall(r'"([^"]+)"|\'([^\']+)\'', text)
        if (name := _dependency_name(value[0] or value[1]))
    ]


def _dependency_name(value: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", value)
    if not match:
        return ""
    return match.group(1).replace("_", "-").lower()


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


def _hook_report(root: Path, hooks: dict[str, Any]) -> dict[str, Any]:
    hook_groups = hooks.get("hooks", {}) if isinstance(hooks, dict) else {}
    text = json.dumps(hooks)
    runner_path = root / "hooks" / "run_hook.py"
    runner_text = runner_path.read_text(encoding="utf-8", errors="ignore") if runner_path.exists() else ""
    return {
        "hook_count": sum(len(value) for value in hook_groups.values() if isinstance(value, list)),
        "uses_hook_check_module": "td_mcp.brain.hook_check" in text
        or "td_mcp.brain.hook_check" in runner_text,
        "uses_hook_runner": "hooks/run_hook.py" in text,
        "has_post_tool_use_guard": "post-tool-use" in text and "PostToolUse" in hook_groups,
        "has_stop_release_guard": "release-stop" in text and "Stop" in hook_groups,
    }


def _tool_count(root: Path) -> int:
    manifest = _read_json(root / "mcp" / "manifest.json")
    surface = manifest.get("surface") if isinstance(manifest.get("surface"), dict) else {}
    return int(surface.get("tool_count") or manifest.get("tool_count") or len(manifest.get("tools") or []))


def _registry_tool_count() -> int | None:
    try:
        import td_mcp.server as server
    except Exception:
        return None

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        tools = asyncio.run(server.mcp.list_tools())
        return len(tools)
    return None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = ["audit_plugin_surface"]
