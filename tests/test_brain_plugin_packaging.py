from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from td_mcp.brain.plugin_surface import audit_plugin_surface
from td_mcp.release_gates import EXPECTED_MIN_TOOL_COUNT

ROOT = Path(__file__).resolve().parent.parent


def _load_build_plugin_zip_module():
    path = ROOT / "scripts" / "build_plugin_zip.py"
    spec = importlib.util.spec_from_file_location("build_plugin_zip", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_build_mcpb_module():
    path = ROOT / "scripts" / "build_mcpb.py"
    spec = importlib.util.spec_from_file_location("build_mcpb", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plugin_zip_bundles_brain_skills_agents_and_hooks():
    module = _load_build_plugin_zip_module()
    packaged_dirs = dict(module.PLUGIN_DIRS)

    assert packaged_dirs["skills"] == "skills"
    assert packaged_dirs["agents"] == "agents"
    assert packaged_dirs["hooks"] == "hooks"

    for rel in (
        "skills/tdpilot-brain-builder/SKILL.md",
        "skills/tdpilot-brain-explorer/SKILL.md",
        "skills/tdpilot-brain-validator/SKILL.md",
        "skills/tdpilot-brain-recovery/SKILL.md",
        "skills/tdpilot-brain-release/SKILL.md",
        "agents/td-brain-explorer.md",
        "agents/td-brain-builder.md",
        "agents/td-brain-validator.md",
        "agents/td-release-auditor.md",
        "hooks/hooks.json",
        "hooks/run_hook.py",
    ):
        assert (ROOT / rel).exists(), f"missing plugin package file: {rel}"


def test_plugin_surface_audit_proves_codex_claude_and_package_mirrors():
    report = audit_plugin_surface(ROOT)

    assert report["ok"] is True
    assert report["brain_skill_count"] == 5
    assert report["agent_count"] == 4
    assert report["hook_count"] >= 1
    assert report["tool_count"] == EXPECTED_MIN_TOOL_COUNT
    assert report["registry_tool_count"] == EXPECTED_MIN_TOOL_COUNT
    assert report["registry_tool_count"] == report["tool_count"]
    assert report["local_first"]["ok"] is True
    assert report["local_first"]["hosted_llm_dependency_leaks"] == []
    assert report["personal_path_leaks"] == []
    assert report["missing_artifacts"] == []
    assert report["mirror_mismatches"] == []
    assert report["mcp_config"]["uses_plugin_root_placeholder"] is True
    assert report["hooks"]["uses_hook_check_module"] is True
    assert report["hooks"]["uses_hook_runner"] is True
    assert report["hooks"]["has_post_tool_use_guard"] is True
    assert report["hooks"]["has_stop_release_guard"] is True


def test_codex_claude_plugin_surfaces_advertise_reviewed_operator_atlas():
    claude_manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    codex_manifest = json.loads(
        (ROOT / "plugins" / "tdpilot" / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    codex_interface = codex_manifest["interface"]
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    plugin_readme_text = (ROOT / "plugin_README.md").read_text(encoding="utf-8")

    advertised_surfaces = "\n".join(
        [
            claude_manifest["description"],
            codex_manifest["description"],
            codex_interface["longDescription"],
            "\n".join(codex_interface["defaultPrompt"]),
            readme_text,
            plugin_readme_text,
        ]
    )

    assert "656-card reviewed operator atlas" in advertised_surfaces
    assert "zero-concept backlog" in advertised_surfaces
    assert "concept-to-node" in advertised_surfaces
    assert "Official Derivative" in advertised_surfaces


def test_readmes_advertise_measured_concept_to_node_eval_gate():
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    plugin_readme_text = (ROOT / "plugin_README.md").read_text(encoding="utf-8")

    for text in (readme_text, plugin_readme_text):
        assert "50+ case concept-to-node golden eval corpus" in text
        assert "50-case concept-to-node golden eval corpus" not in text
        assert "scripts/eval_brain_golden.py" in text


def test_concept_to_node_master_plan_is_linked_and_implementation_ready():
    plan_path = ROOT / "docs" / "TDPILOT_CONCEPT_TO_NODE_MASTER_PLAN.md"
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap_text = (ROOT / "docs" / "TDPILOT_EFFECTIVENESS_ROADMAP.md").read_text(encoding="utf-8")

    assert plan_path.exists()
    plan_text = plan_path.read_text(encoding="utf-8")

    assert "docs/TDPILOT_CONCEPT_TO_NODE_MASTER_PLAN.md" in readme_text
    assert "docs/TDPILOT_CONCEPT_TO_NODE_MASTER_PLAN.md" in roadmap_text
    for required in (
        "Prompt -> ConceptCompiler -> CandidateGraph -> PatternResolver",
        "CompiledVisualTaskSpec",
        "CandidateConceptGraph",
        "BrainPattern",
        "OperatorAvailabilityMatrix",
        "OperatorSubstitutionRule",
        "ParamSemantics",
        "GeneratedCodeBlock",
        "ProfileValidationProbe",
        "AssemblyMacro",
        "ConceptToNodeEvalCase",
        "Official Derivative",
        "Codex",
        "Claude Code",
        "6-9 focused weeks",
        "10-14 weeks",
    ):
        assert required in plan_text


def test_audit_plugin_surface_cli_outputs_json_report():
    proc = subprocess.run(
        [sys.executable, "scripts/audit_plugin_surface.py", "--root", str(ROOT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["tool_count"] == EXPECTED_MIN_TOOL_COUNT


def test_mcpb_manifest_uses_current_brain_tool_count_and_positioning():
    module = _load_build_mcpb_module()
    manifest = module._build_manifest("1.6.16")
    expected_count = str(module.EXPECTED_MIN_TOOL_COUNT)
    combined_text = manifest["description"] + "\n" + manifest["long_description"]

    assert expected_count in manifest["description"]
    assert "103 MCP tools" not in combined_text
    assert "106 MCP tools" not in combined_text
    assert "BrainPlan" in combined_text
    assert "transaction" in combined_text.lower()
