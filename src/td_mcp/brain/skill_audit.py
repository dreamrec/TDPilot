"""Static quality audit for shipped TDPilot brain skills."""

from __future__ import annotations

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

REQUIRED_SECTIONS = ("Core Rule", "Pressure Scenarios", "Common Mistakes")


def audit_brain_skills(root: str | Path) -> dict[str, Any]:
    """Return a JSON-serializable audit report for canonical brain skills."""
    repo_root = Path(root)
    skills = [
        _audit_one_skill(repo_root / "skills" / name / "SKILL.md", name) for name in EXPECTED_BRAIN_SKILLS
    ]
    pressure_count = sum(item["pressure_scenarios"] for item in skills)
    missing = [item["name"] for item in skills if item["missing"]]
    return {
        "schema_version": 1,
        "ok": all(item["ok"] for item in skills),
        "skill_count": len(skills),
        "pressure_scenario_count": pressure_count,
        "missing_skills": missing,
        "required_sections": list(REQUIRED_SECTIONS),
        "skills": skills,
    }


def _audit_one_skill(path: Path, expected_name: str) -> dict[str, Any]:
    issues: list[str] = []
    if not path.exists():
        return {
            "name": expected_name,
            "path": str(path),
            "missing": True,
            "ok": False,
            "sections": [],
            "pressure_scenarios": 0,
            "issues": ["missing SKILL.md"],
        }

    text = path.read_text(encoding="utf-8")
    sections = _sections(text)
    pressure_scenarios = _pressure_scenario_count(text)
    for section in REQUIRED_SECTIONS:
        if section not in sections:
            issues.append(f"missing section: {section}")
    if pressure_scenarios < 2:
        issues.append("Pressure Scenarios must include at least 2 bullets beginning with '- Pressure:'")
    if "td_brain_plan" not in text and expected_name in {"tdpilot-brain-builder", "tdpilot-brain-validator"}:
        issues.append("must mention td_brain_plan")
    if expected_name == "tdpilot-brain-release" and "scripts/audit_brain_skills.py" not in text:
        issues.append("release skill must include the brain skill audit command")

    return {
        "name": expected_name,
        "path": str(path),
        "missing": False,
        "ok": not issues,
        "sections": sections,
        "pressure_scenarios": pressure_scenarios,
        "issues": issues,
    }


def _sections(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.MULTILINE)]


def _pressure_scenario_count(text: str) -> int:
    match = re.search(r"^## Pressure Scenarios\s*$([\s\S]*?)(?:^##\s+|\Z)", text, flags=re.MULTILINE)
    if not match:
        return 0
    return len(re.findall(r"^\s*-\s+Pressure:", match.group(1), flags=re.MULTILINE))


__all__ = ["EXPECTED_BRAIN_SKILLS", "REQUIRED_SECTIONS", "audit_brain_skills"]
