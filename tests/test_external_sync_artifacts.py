"""Regression coverage for the MIDI + Ableton Link support kit.

This ports the still-useful pieces of the old acafcfe side branch onto the
current v2 brain surface without accepting that branch's stale files wholesale.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

import td_mcp.tool_registry as registry
from td_mcp.hints import default_registry
from td_mcp.macros.templates import build_default_templates
from td_mcp.services import ServiceContainer

ROOT = Path(__file__).resolve().parent.parent
ROOT_SKILL = ROOT / "skills" / "tdpilot-core"
PLUGIN_SKILL = ROOT / "plugins" / "tdpilot" / "skills" / "tdpilot-core"
HINT_OP_DIR = ROOT / "src" / "td_mcp" / "hints" / "packs" / "op_types"
HINT_TOPIC_DIR = ROOT / "src" / "td_mcp" / "hints" / "packs" / "topics"


class _FakeCardIndex:
    def get_operator(self, op_type: str):
        return None

    def get_palette(self, op_type: str):
        return None


class _AuditClient:
    def __init__(self, tree: dict[str, list[dict[str, Any]]]):
        self._tree = tree

    async def request(self, endpoint: str, body: dict | None = None):
        if endpoint == "nodes":
            return self._tree.get((body or {}).get("path", "/"), [])
        if endpoint == "node/errors":
            return {"issues": []}
        return {}


def _make_ctx(*, client, card_index):
    services = ServiceContainer(td_client=client, technique_store=None, preference_store=None)
    services.card_index = card_index
    state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=state, lifespan_state=state)
    )


def test_default_registry_ships_external_sync_hint_packs():
    reg = default_registry()

    assert "external_sync" in reg.topics()
    for op_type in ("abletonlinkCHOP", "midiinCHOP", "midioutCHOP", "midiinmapCHOP", "midiinDAT"):
        assert op_type in reg.op_types()

    link_hint_ids = {match.hint.id for match in reg.find(op_type="abletonlinkCHOP")}
    assert {
        "abletonlink_no_quantum_channel",
        "abletonlink_enable_output_channel_toggles",
        "abletonlink_setting_tempo_is_global",
    }.issubset(link_hint_ids)

    midi_hint_ids = {match.hint.id for match in reg.find(op_type="midioutCHOP")}
    assert {"midi_device_mapper_first", "midioutchop_cookalways_required"}.issubset(midi_hint_ids)


def test_external_sync_topic_routes_ableton_and_daw_audio_intents():
    reg = default_registry()

    ableton_ids = {
        match.hint.id
        for match in reg.find(topic="external_sync", intent="sync TouchDesigner visuals to Ableton Link")
    }
    assert {"external_sync_three_paths", "external_sync_link_preferred_for_ableton"}.issubset(
        ableton_ids
    )

    audio_ids = {
        match.hint.id
        for match in reg.find(topic="external_sync", intent="route BlackHole DAW audio into TD")
    }
    assert "external_sync_audio_path_routing" in audio_ids


def test_midi_pack_keeps_mapper_hint_pack_scoped_and_raw_send_documented():
    midi_pack = yaml.safe_load((HINT_OP_DIR / "midiinCHOP.yaml").read_text(encoding="utf-8"))
    assert midi_pack["schema_version"] == 2
    assert set(midi_pack["op_types"]) == {"midiinCHOP", "midioutCHOP", "midiinmapCHOP", "midiinDAT"}

    mapper_hint = next(hint for hint in midi_pack["hints"] if hint["id"] == "midi_device_mapper_first")
    assert "op_type" not in (mapper_hint.get("when") or {})

    send_hint = next(hint for hint in midi_pack["hints"] if hint["id"] == "midioutchop_python_send_methods")
    assert ".send(" in send_hint["rule"]
    assert "midioutDAT" in send_hint["rule"]


def test_external_sync_packs_use_current_hint_schema_and_sources():
    for path in (
        HINT_OP_DIR / "abletonlinkCHOP.yaml",
        HINT_OP_DIR / "midiinCHOP.yaml",
        HINT_TOPIC_DIR / "external_sync.yaml",
    ):
        pack = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert pack["schema_version"] == 2
        assert pack["hints"]
        for hint in pack["hints"]:
            assert hint["source_kind"] in {"skill_pitfall", "operator_docs", "hint_pack"}
            assert hint["source"]
            assert hint["rule"]


def test_default_macro_templates_include_external_sync_without_regressing_particle_gpu():
    templates = build_default_templates()

    assert {"ableton_link_sync", "midi_control_mapping"}.issubset(templates)

    link = templates["ableton_link_sync"]
    assert "tempo" not in link.param_targets
    link_node = next(node for node in link.nodes if node.name == "link")
    for toggle in ("tempo", "beats", "phase", "rampbeat"):
        assert link_node.params[toggle] == 1

    midi = templates["midi_control_mapping"]
    assert [node.node_type for node in midi.nodes] == [
        "midiinmapCHOP",
        "selectCHOP",
        "mathCHOP",
        "nullCHOP",
    ]
    assert midi.param_schema["normalize_scale"].default == pytest.approx(1 / 127)

    particle = templates["particle_gpu"]
    assert [node.node_type for node in particle.nodes] == [
        "circlePOP",
        "noisePOP",
        "nullPOP",
        "rendersimpleTOP",
        "nullTOP",
    ]


@pytest.mark.asyncio
async def test_legacy_project_audit_treats_abletonlink_as_stock_chop(monkeypatch):
    idx = _FakeCardIndex()
    client = _AuditClient(
        {
            "/project1": [
                {
                    "name": "link1",
                    "type": "abletonlinkCHOP",
                    "family": "CHOP",
                    "path": "/project1/link1",
                }
            ],
        }
    )
    ctx = _make_ctx(client=client, card_index=idx)
    monkeypatch.setattr(registry, "_get_client", lambda _ctx: client)

    result = await registry.td_audit_project(ctx, root_path="/project1")

    assert result["success"] is True
    assert "abletonlinkCHOP" not in result["unknown_op_types"]


def test_external_sync_reference_is_mirrored_for_root_and_plugin_skills():
    for skill_root in (ROOT_SKILL, PLUGIN_SKILL):
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        reference_path = skill_root / "references" / "external-sync-and-control.md"

        assert reference_path.exists()
        assert "external-sync-and-control.md" in skill_text
        reference = reference_path.read_text(encoding="utf-8")
        assert "Ableton Link path" in reference
        assert "MIDI Device Mapper" in reference
        assert "midioutCHOP" in reference
