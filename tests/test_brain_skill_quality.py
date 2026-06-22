from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from td_mcp.brain.skill_audit import audit_brain_skills

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_BRAIN_SKILLS = {
    "tdpilot-brain-explorer",
    "tdpilot-brain-builder",
    "tdpilot-brain-validator",
    "tdpilot-brain-recovery",
    "tdpilot-brain-release",
}


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(?P<body>.*?)\n---\n", text, flags=re.DOTALL)
    assert match, f"{path} missing YAML frontmatter"
    fields: dict[str, str] = {}
    key = None
    for line in match.group("body").splitlines():
        if not line.strip():
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip('"')
            continue
        if key:
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def _brain_skill_paths(root: Path) -> dict[str, Path]:
    paths = {}
    for path in root.glob("tdpilot-brain-*/SKILL.md"):
        name = _frontmatter(path)["name"]
        paths[name] = path
    return paths


def test_root_and_plugin_brain_skills_are_complete_and_trigger_optimized():
    for skill_root in (ROOT / "skills", ROOT / ".agents" / "skills", ROOT / "plugins" / "tdpilot" / "skills"):
        skills = _brain_skill_paths(skill_root)
        assert EXPECTED_BRAIN_SKILLS.issubset(skills), (
            f"{skill_root} missing {EXPECTED_BRAIN_SKILLS - set(skills)}"
        )

        for name in EXPECTED_BRAIN_SKILLS:
            meta = _frontmatter(skills[name])
            description = re.sub(r"\s+", " ", meta["description"]).strip(" >")
            assert description.startswith("Use when "), f"{name} description must be trigger-only"
            assert len(description) <= 500, f"{name} description is too long for discovery"
            assert not re.search(
                r"\b(observe|ground|execute|learn|workflow|transaction rollback defaults)\b",
                description,
                flags=re.IGNORECASE,
            ), f"{name} description summarizes process instead of trigger conditions"


def test_brain_explorer_is_packaged_for_codex_and_claude():
    assert (ROOT / ".agents" / "skills" / "tdpilot-brain-explorer" / "SKILL.md").exists()
    assert (ROOT / ".codex" / "agents" / "td-brain-explorer.toml").exists()
    assert (ROOT / "agents" / "td-brain-explorer.md").exists()
    assert (ROOT / "plugins" / "tdpilot" / "agents" / "td-brain-explorer.md").exists()
    assert "tdpilot-brain-explorer" in (
        ROOT / "plugins" / "tdpilot" / ".codex-plugin" / "plugin.json"
    ).read_text(encoding="utf-8")


def test_codex_repository_skills_match_canonical_root_skills():
    for name in EXPECTED_BRAIN_SKILLS:
        canonical = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        codex = (ROOT / ".agents" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert codex == canonical


def test_brain_builder_teaches_reviewed_atlas_concept_to_node_workflow():
    for skill_root in (ROOT / "skills", ROOT / ".agents" / "skills", ROOT / "plugins" / "tdpilot" / "skills"):
        text = (skill_root / "tdpilot-brain-builder" / "SKILL.md").read_text(encoding="utf-8")

        assert "Concept-to-node Atlas Workflow" in text
        assert "656-card reviewed operator atlas" in text
        assert "zero-concept backlog" in text
        assert "Official Derivative" in text
        assert "choose the smallest operator chain" in text


def test_brain_builder_teaches_compiler_pattern_availability_validation_workflow():
    for skill_root in (ROOT / "skills", ROOT / ".agents" / "skills", ROOT / "plugins" / "tdpilot" / "skills"):
        text = (skill_root / "tdpilot-brain-builder" / "SKILL.md").read_text(encoding="utf-8")

        assert "Compiler-Backed Planning Workflow" in text
        assert "compiled_task" in text
        assert "candidate_graphs" in text
        assert "pattern resolver" in text
        assert "availability matrix" in text
        assert "parameter semantics" in text
        assert "validation probes" in text
        assert "assembly macros" in text


def test_agents_md_points_codex_to_brain_skills():
    agents_md = ROOT / "AGENTS.md"
    assert agents_md.exists()
    text = agents_md.read_text(encoding="utf-8")
    assert "tdpilot-brain-explorer" in text
    assert "td_brain_plan" in text
    assert "scripts/audit_plugin_surface.py" in text


def test_brain_skill_audit_enforces_pressure_scenarios_and_common_mistakes():
    report = audit_brain_skills(ROOT)

    assert report["ok"] is True
    assert report["skill_count"] == len(EXPECTED_BRAIN_SKILLS)
    assert report["pressure_scenario_count"] >= 10
    for skill in report["skills"]:
        assert skill["ok"], f"{skill['name']} failed audit: {skill['issues']}"
        assert skill["pressure_scenarios"] >= 2
        assert "Core Rule" in skill["sections"]
        assert "Pressure Scenarios" in skill["sections"]
        assert "Common Mistakes" in skill["sections"]


def test_audit_brain_skills_cli_outputs_json_report():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_brain_skills.py", "--root", str(ROOT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["pressure_scenario_count"] >= 10


def test_release_skill_includes_plugin_surface_audit_gate():
    for skill_root in (ROOT / "skills", ROOT / ".agents" / "skills", ROOT / "plugins" / "tdpilot" / "skills"):
        text = (skill_root / "tdpilot-brain-release" / "SKILL.md").read_text(encoding="utf-8")

        assert "uv run python scripts/audit_plugin_surface.py" in text
        assert "scripts/check_release_gates.py" in text
        assert "--plugin-surface-report" in text
        assert "--require-plugin-surface" in text
        assert "--brain-live-smoke-report" in text
        assert "--require-live-smoke" in text
