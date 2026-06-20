from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from td_mcp.brain.live_smoke import build_live_smoke_report, live_smoke_scenarios

ROOT = Path(__file__).resolve().parent.parent.parent


class _SparseLiveClient:
    async def health_check(self):
        return {"status": "ok", "api_version": "test"}

    async def request(self, endpoint: str, params: dict | None = None):
        if endpoint == "families":
            return {
                "families": {
                    "TOP": ["null"],
                    "CHOP": ["null"],
                    "COMP": ["base"],
                    "POP": ["null"],
                    "DAT": ["text"],
                }
            }
        if endpoint == "nodes":
            return {"nodes": []}
        return {}


class _AllScenarioCards:
    def __init__(self) -> None:
        self.known = {op for scenario in live_smoke_scenarios() for op in scenario.expected_ops}

    def get_operator(self, op_type: str):
        if op_type in self.known:
            return {"op_type": op_type, "summary": "test card"}
        return None


@pytest.mark.asyncio
async def test_live_smoke_dry_run_covers_required_visual_domains():
    report = await build_live_smoke_report(mode="dry_run")

    assert report["schema_version"] == 1
    assert report["mode"] == "dry_run"
    assert report["ok"] is True
    assert report["mutated_td"] is False
    assert report["scenario_count"] >= 8
    scenarios = {item["id"]: item for item in report["scenarios"]}

    expected = {
        "feedback_loop": ("feedback", "feedbackTOP"),
        "audio_reactive_top": ("audio_reactive", "audiofileinCHOP"),
        "pop_particle_render": ("pop", "rendersimpleTOP"),
        "glsl_shader_top": ("glsl", "glslTOP"),
        "glsl_material_render": ("glsl_material", "glslMAT"),
        "glsl_pop_attribute_render": ("glsl_pop", "glslPOP"),
        "render_pipeline": ("render_pipeline", "renderTOP"),
        "panel_ui_controls": ("panel_ui", "panelCHOP"),
        "custom_parameter_rig": ("control_rig", "baseCOMP"),
        "broken_network_recovery": ("feedback", "feedbackTOP"),
    }
    assert set(expected).issubset(scenarios)

    for scenario_id, (profile, required_op) in expected.items():
        item = scenarios[scenario_id]
        assert item["status"] == "planned"
        assert item["profile"] == profile
        assert required_op in item["operators"]
        assert item["blocked_questions"] == []
        assert item["validation_profile"] == "structural_visual_safe"
        assert "td_brain_plan" in item["tools"]
        assert "td_brain_execute" in item["tools"]


def test_live_smoke_scenario_catalog_is_explicit_about_live_td_requirement():
    scenarios = live_smoke_scenarios()

    assert len(scenarios) >= 8
    assert all(item.requires_live_td for item in scenarios)
    assert all(item.intent for item in scenarios)
    assert all(item.validation_profile == "structural_visual_safe" for item in scenarios)


@pytest.mark.asyncio
async def test_live_smoke_uses_docs_evidence_when_live_family_list_is_sparse():
    report = await build_live_smoke_report(
        mode="live", td_client=_SparseLiveClient(), card_index=_AllScenarioCards()
    )

    assert report["ok"] is True
    assert all(item["status"] == "planned" for item in report["scenarios"])
    assert any("family-list-omitted:feedbackTOP" in item["risk_flags"] for item in report["scenarios"])


def test_brain_live_smoke_cli_outputs_json_report():
    proc = subprocess.run(
        [sys.executable, "scripts/brain_live_smoke.py", "--dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["mode"] == "dry_run"
    assert payload["scenario_count"] >= 8


def test_release_skills_include_live_smoke_gate_commands():
    skill_paths = [
        ROOT / "skills" / "tdpilot-brain-release" / "SKILL.md",
        ROOT / ".agents" / "skills" / "tdpilot-brain-release" / "SKILL.md",
        ROOT / "plugins" / "tdpilot" / "skills" / "tdpilot-brain-release" / "SKILL.md",
    ]

    for path in skill_paths:
        text = path.read_text(encoding="utf-8")
        assert "uv run python scripts/brain_live_smoke.py --dry-run" in text
        assert "uv run python scripts/brain_live_smoke.py --live" in text
