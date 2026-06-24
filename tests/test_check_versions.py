from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_check_versions_module():
    path = ROOT / "scripts" / "check_versions.py"
    spec = importlib.util.spec_from_file_location("check_versions", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_minimal_version_tree(root: Path, *, version: str = "2.0.1", tool_count: int = 111) -> None:
    (root / "src" / "td_mcp").mkdir(parents=True, exist_ok=True)
    (root / "src" / "td_mcp" / "__init__.py").write_text(
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (root / "src" / "td_mcp" / "release_gates.py").write_text(
        f"EXPECTED_MIN_TOOL_COUNT: int = {tool_count}\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(f'version = "{version}"\n', encoding="utf-8")
    _write_json(root / "npm" / "package.json", {"version": version})
    _write_json(root / ".claude-plugin" / "plugin.json", {"version": version})
    _write_json(root / ".claude-plugin" / "marketplace.json", {"version": version})
    _write_json(root / "mcp" / "manifest.json", {"version": version, "surface": {"tool_count": tool_count}})
    _write_json(root / "plugins" / "tdpilot" / ".codex-plugin" / "plugin.json", {"version": version})
    (root / "td_component").mkdir(parents=True, exist_ok=True)
    (root / "td_component" / "mcp_webserver_callbacks.py").write_text(
        f'API_VERSION = "{version}"\n',
        encoding="utf-8",
    )
    (root / "plugin_README.md").write_text(
        (
            f"TDPilot v{version} provides {tool_count} MCP tools\n"
            f"- **tdpilot-core** — Core patching discipline: {tool_count}-tool reference\n"
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        (
            f"# TDPilot Runtime v{version}\n"
            f"[![MCP tools](https://img.shields.io/badge/MCP%20tools-{tool_count}-blueviolet)]\n"
            f"That installs all **{tool_count} MCP tools**.\n"
            f"- {tool_count}-tool runtime surface\n"
            f"\n## What's New In {version}\n"
            f"\n## Tool Map ({tool_count} Tools)\n"
        ),
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "API_REFERENCE.md").write_text(
        f"Auto-generated from TDPilot v{version}\n",
        encoding="utf-8",
    )
    (root / "docs" / "MANUAL.md").write_text(f"# TDPilot v{version}\n", encoding="utf-8")
    (root / "docs" / "TDPILOT_EFFECTIVENESS_ROADMAP.md").write_text(
        f"- {tool_count} local MCP tools\n",
        encoding="utf-8",
    )
    (root / "npm" / "README.md").write_text(
        (
            f"# TDPilot v{version}\n"
            f"[![MCP tools](https://img.shields.io/badge/MCP%20tools-{tool_count}-blueviolet)]\n"
            f"AI copilot for TouchDesigner — {tool_count} tools for full live control\n"
        ),
        encoding="utf-8",
    )
    (root / "skills" / "tdpilot-core").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "tdpilot-core" / "SKILL.md").write_text(
        (
            "---\n"
            "description: >\n"
            f"  Core patching discipline for TDPilot v{version}.\n"
            "---\n"
            f"# TDPilot Core v{version}\n"
        ),
        encoding="utf-8",
    )
    (root / "skills" / "tdpilot-production").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "tdpilot-production" / "SKILL.md").write_text(
        (
            "---\n"
            "description: >\n"
            f"  Production-grade TouchDesigner MCP workflow for TDPilot v{version}.\n"
            "---\n"
            f"# TDPilot Production v{version}\n"
        ),
        encoding="utf-8",
    )
    (root / "plugins" / "tdpilot" / "skills" / "tdpilot-core").mkdir(parents=True, exist_ok=True)
    (root / "plugins" / "tdpilot" / "skills" / "tdpilot-core" / "SKILL.md").write_text(
        (
            "---\n"
            "description: >\n"
            f"  Core patching discipline for TDPilot v{version}.\n"
            "---\n"
            f"# TDPilot Core v{version}\n"
        ),
        encoding="utf-8",
    )
    (root / "plugins" / "tdpilot" / "skills" / "tdpilot-production").mkdir(parents=True, exist_ok=True)
    (root / "plugins" / "tdpilot" / "skills" / "tdpilot-production" / "SKILL.md").write_text(
        (
            "---\n"
            "description: >\n"
            f"  Production-grade TouchDesigner MCP workflow for TDPilot v{version}.\n"
            "---\n"
            f"# TDPilot Production v{version}\n"
        ),
        encoding="utf-8",
    )


def test_check_versions_fails_when_codex_plugin_manifest_drifts(tmp_path, monkeypatch, capsys):
    module = _load_check_versions_module()
    _write_minimal_version_tree(tmp_path)
    _write_json(tmp_path / "plugins" / "tdpilot" / ".codex-plugin" / "plugin.json", {"version": "2.0.0"})
    monkeypatch.setattr(module, "ROOT", tmp_path)

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "plugins/tdpilot/.codex-plugin/plugin.json says 2.0.0, expected 2.0.1" in output


def test_check_versions_fails_when_readme_runtime_title_drifts(tmp_path, monkeypatch, capsys):
    module = _load_check_versions_module()
    _write_minimal_version_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        "# TDPilot Runtime v2.0.0\n\n## What's New In 2.0.1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "README.md title: README.md says 2.0.0, expected 2.0.1" in output


def test_check_versions_fails_when_skill_frontmatter_drifts(tmp_path, monkeypatch, capsys):
    module = _load_check_versions_module()
    _write_minimal_version_tree(tmp_path)
    (tmp_path / "skills" / "tdpilot-core" / "SKILL.md").write_text(
        ("---\ndescription: >\n  Core patching discipline for TDPilot v2.0.0.\n---\n# TDPilot Core v2.0.1\n"),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "skills/tdpilot-core/SKILL.md frontmatter: skills/tdpilot-core/SKILL.md says 2.0.0" in output


def test_check_versions_fails_when_readme_tool_count_drifts(tmp_path, monkeypatch, capsys):
    module = _load_check_versions_module()
    _write_minimal_version_tree(tmp_path)
    (tmp_path / "README.md").write_text(
        (
            "# TDPilot Runtime v2.0.1\n"
            "[![MCP tools](https://img.shields.io/badge/MCP%20tools-110-blueviolet)]\n"
            "That installs all **111 MCP tools**.\n"
            "- 111-tool runtime surface\n"
            "\n## What's New In 2.0.1\n"
            "\n## Tool Map (111 Tools)\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "README.md MCP tools badge: README.md says 110, expected 111" in output


def test_check_versions_fails_when_npm_badge_tool_count_drifts(tmp_path, monkeypatch, capsys):
    module = _load_check_versions_module()
    _write_minimal_version_tree(tmp_path)
    (tmp_path / "npm" / "README.md").write_text(
        (
            "# TDPilot v2.0.1\n"
            "[![MCP tools](https://img.shields.io/badge/MCP%20tools-110-blueviolet)]\n"
            "AI copilot for TouchDesigner — 111 tools for full live control\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "npm/README.md MCP tools badge: npm/README.md says 110, expected 111" in output


def test_check_versions_fails_when_roadmap_tool_count_drifts(tmp_path, monkeypatch, capsys):
    module = _load_check_versions_module()
    _write_minimal_version_tree(tmp_path)
    (tmp_path / "docs" / "TDPILOT_EFFECTIVENESS_ROADMAP.md").write_text(
        "- 110 local MCP tools\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "docs/TDPILOT_EFFECTIVENESS_ROADMAP.md tool count" in output
