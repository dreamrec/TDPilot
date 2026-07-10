from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_core_is_compact_and_teaches_dual_route_checkpoint_discipline():
    core = _read("skills/tdpilot-core/SKILL.md")

    assert len(core.encode("utf-8")) <= 14_000
    assert "Complete Tool Surface" not in core
    assert "Feature Adoption Rules" not in core
    assert "Pattern-shaped" in core
    assert "Concept-shaped" in core
    assert "td_brain_ground" in core
    assert "td_brain_propose" in core
    assert "Do not scan after every operation" in core
    assert "td_tool_batch" in core
    assert "td_memory_recall" in core
    assert "one low-quality inline thumbnail" in core

    assert core == _read("plugins/tdpilot/skills/tdpilot-core/SKILL.md")


def test_production_skill_uses_logical_checkpoints_and_route_specific_safety():
    production = _read("skills/tdpilot-production/SKILL.md")
    flat = " ".join(production.split())

    assert "exact compiler-backed pattern" in production
    assert "td_brain_ground` → author → `td_brain_propose" in production
    assert "logical batch boundaries" in production
    assert "not after every individual" in production
    assert "guarded route swap" in flat
    assert production == _read("plugins/tdpilot/skills/tdpilot-production/SKILL.md")


def test_builder_preload_budget_and_public_agents_inherit_caller_model():
    builder_agent = _read("agents/td-brain-builder.md")
    builder_skill = _read("skills/tdpilot-brain-builder/SKILL.md")

    assert len((builder_agent + builder_skill).encode("utf-8")) <= 16_000
    assert "model: sonnet" not in "\n".join(
        _read(f"agents/{name}")
        for name in (
            "td-brain-builder.md",
            "td-brain-explorer.md",
            "td-brain-validator.md",
            "td-release-auditor.md",
        )
    )
    frontmatter = builder_agent.split("---", 2)[1]
    assert re.findall(r"^\s+-\s+(tdpilot-[\w-]+)\s*$", frontmatter, flags=re.MULTILINE) == [
        "tdpilot-brain-builder"
    ]

    for name in (
        "td-brain-builder.md",
        "td-brain-explorer.md",
        "td-brain-validator.md",
    ):
        assert _read(f"agents/{name}") == _read(f"plugins/tdpilot/agents/{name}")

    assert not (ROOT / "plugins/tdpilot/agents/td-release-auditor.md").exists()


def test_builder_progressive_reference_covers_2d_3d_and_real_control_binding():
    canonical = _read("skills/tdpilot-brain-builder/references/progressive-drafts.md")

    assert "## 2D: Audio-controlled TOP" in canonical
    assert "## 3D: Rendered object with a stable TOP" in canonical
    assert '"mode": "chop_reference_expression"' in canonical
    assert '"source_channel": 0' in canonical
    assert '"target_param": "brightness1"' in canonical
    assert "unresolved_semantic_edges" in canonical

    for rel in (
        ".agents/skills/tdpilot-brain-builder/references/progressive-drafts.md",
        "plugins/tdpilot/skills/tdpilot-brain-builder/references/progressive-drafts.md",
    ):
        assert canonical == _read(rel)


def test_commands_use_concept_authoring_and_never_flagship_macros():
    concept = _read("commands/td-concept.md")
    first_wow = _read("commands/td-first-wow.md")
    audio = _read("commands/td-audio-reactive.md")
    first_wow_flat = " ".join(first_wow.split())

    for text in (concept, first_wow, audio):
        assert "td_brain_ground" in text
        assert "td_brain_propose" in text
        assert "plan_id" in text
        assert "td_create_macro" not in text
        assert "grounding_id" in text
        assert 'draft_schema_version="2"' in text

    assert "visible seeded TOP source" in first_wow_flat
    assert "nonblack/nonuniform" in first_wow
    assert "temporal analysis" in first_wow
    assert "one screenshot" in first_wow.lower()

    assert "If no active source" in audio
    assert "chop_reference_expression" in audio
    assert "nonzero source/analysis signal" in audio
    assert "two screenshots" in audio


def test_public_routing_surfaces_do_not_mandate_planner_first():
    surfaces = {
        "AGENTS.md": _read("AGENTS.md"),
        "builder skill": _read("skills/tdpilot-brain-builder/SKILL.md"),
        "builder agent": _read("agents/td-brain-builder.md"),
        "Codex builder": _read(".codex/agents/td-brain-builder.toml"),
        "MCP prompts": _read("src/td_mcp/registry/prompts.py"),
        "README": _read("README.md"),
        "plugin README": _read("plugin_README.md"),
    }
    forbidden = (
        "call td_brain_plan first",
        "call `td_brain_plan` first",
        "plan before building: call `td_brain_plan`",
        "run `td_brain_plan` before any mutation",
    )

    for label, text in surfaces.items():
        lowered = text.lower()
        for phrase in forbidden:
            assert phrase not in lowered, f"{label} retains planner-first doctrine: {phrase}"
        assert "td_brain_ground" in text, f"{label} omits concept route"
        assert "td_brain_propose" in text, f"{label} omits proposal review"


def test_codex_default_prompts_advertise_both_brain_routes():
    manifest = json.loads(_read("plugins/tdpilot/.codex-plugin/plugin.json"))
    prompts = "\n".join(manifest["interface"]["defaultPrompt"])

    assert "exact validated" in prompts
    assert "td_brain_plan" in prompts
    assert "td_brain_ground" in prompts
    assert "td_brain_propose" in prompts
    assert "actual graph, runtime, and visual behavior" in prompts


def test_project_post_tool_hook_is_checkpoint_scoped_not_per_primitive():
    settings = json.loads(_read(".claude/settings.json"))
    post = settings["hooks"]["PostToolUse"]
    text = json.dumps(post)

    assert "brain_execute" in text
    assert "transaction_apply" in text
    for primitive in ("create_node", "set_params", "connect_nodes", "delete_node", "disconnect"):
        assert primitive not in text
    assert "logical boundary" in text
