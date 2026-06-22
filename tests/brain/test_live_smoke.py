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
                    "POP": ["glsladvanced", "null", "topology"],
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


class _MissingAdvancedPopLiveClient(_SparseLiveClient):
    async def request(self, endpoint: str, params: dict | None = None):
        if endpoint == "families":
            return {
                "families": {
                    "TOP": ["null"],
                    "CHOP": ["null"],
                    "COMP": ["base"],
                    "POP": ["null", "topology"],
                    "DAT": ["text"],
                }
            }
        return await super().request(endpoint, params)


class _DerivativePopAliasLiveClient(_SparseLiveClient):
    async def request(self, endpoint: str, params: dict | None = None):
        if endpoint == "families":
            return {
                "families": {
                    "TOP": ["null", "rendersimple"],
                    "CHOP": ["null"],
                    "COMP": ["base"],
                    "POP": ["circle", "glsladv", "null", "topology"],
                    "DAT": ["text"],
                }
            }
        return await super().request(endpoint, params)


class _TransactionalGeneratedCodeLiveClient(_SparseLiveClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []
        self.created_paths: set[str] = set()
        self.content: dict[str, str] = {}

    async def health_check(self):
        self.calls.append(("health", {}))
        return {
            "status": "ok",
            "api_version": "test",
            "td_build": "2025.32820",
            "platform": "macOS",
        }

    async def request(self, endpoint: str, params: dict | None = None):
        payload = params or {}
        self.calls.append((endpoint, payload))
        if endpoint == "families":
            return await super().request(endpoint, params)
        if endpoint == "nodes":
            return {
                "nodes": [
                    {"path": path, "name": path.rsplit("/", 1)[-1]}
                    for path in sorted(self.created_paths)
                ]
            }
        if endpoint == "node/create":
            parent = str(payload.get("parent_path") or "/project1").rstrip("/")
            name = str(payload.get("name") or "created")
            path = f"{parent}/{name}".replace("//", "/")
            self.created_paths.add(path)
            return {"node": {"path": path}}
        if endpoint == "node/params/set":
            return {"ok": True}
        if endpoint == "node/content/set":
            path = str(payload.get("path") or "")
            self.content[path] = str(payload.get("text") or "")
            return {"ok": True}
        if endpoint == "node/content":
            return {"text": self.content.get(str(payload.get("path") or ""), "")}
        if endpoint == "node/connect":
            return {"ok": True}
        if endpoint == "node/errors":
            return {"issues": []}
        if endpoint == "cooking":
            return {"stuck": []}
        if endpoint == "analyze_frame":
            return {"resolution": [16, 16], "channels": 4, "luminance": {"mean": 0.5, "max": 0.8, "std": 0.1}}
        if endpoint == "project/lifecycle":
            if payload.get("action") == "undo":
                self.created_paths.clear()
            return {"ok": True}
        return {}


class _CompileFailGeneratedCodeLiveClient(_TransactionalGeneratedCodeLiveClient):
    async def request(self, endpoint: str, params: dict | None = None):
        payload = params or {}
        if endpoint == "node/errors" and payload.get("path") == "/project1/tdpilot_gc_smoke_glsl":
            self.calls.append((endpoint, payload))
            return {
                "issues": [
                    {
                        "path": "/project1/tdpilot_gc_smoke_glsl",
                        "message": "shader compile failed",
                    }
                ]
            }
        return await super().request(endpoint, params)


class _UndoNoopGeneratedCodeLiveClient(_TransactionalGeneratedCodeLiveClient):
    async def request(self, endpoint: str, params: dict | None = None):
        payload = params or {}
        if endpoint == "project/lifecycle":
            self.calls.append((endpoint, payload))
            return {"ok": True}
        if endpoint == "node/delete":
            self.calls.append((endpoint, payload))
            self.created_paths.discard(str(payload.get("path") or ""))
            return {"success": True}
        return await super().request(endpoint, params)


class _CleanupReadbackFailGeneratedCodeLiveClient(_UndoNoopGeneratedCodeLiveClient):
    def __init__(self) -> None:
        super().__init__()
        self.undo_seen = False
        self.failed_cleanup_readback = False

    async def request(self, endpoint: str, params: dict | None = None):
        payload = params or {}
        if endpoint == "project/lifecycle":
            self.undo_seen = True
            return await super().request(endpoint, params)
        if endpoint == "nodes" and self.undo_seen and not self.failed_cleanup_readback:
            self.calls.append((endpoint, payload))
            self.failed_cleanup_readback = True
            raise RuntimeError("transient cleanup nodes readback failed")
        return await super().request(endpoint, params)


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
        "audio_glsl_material_render": ("concept_compiled", "glslMAT"),
        "audio_terrain_glass_controls": ("concept_compiled", "gridSOP"),
        "glsl_pop_attribute_render": ("glsl_pop", "glslPOP"),
        "render_pipeline": ("render_pipeline", "renderTOP"),
        "panel_ui_controls": ("panel_ui", "panelCHOP"),
        "custom_parameter_rig": ("control_rig", "baseCOMP"),
        "midi_control_bridge": ("concept_compiled", "midiinCHOP"),
        "serial_dat_protocol_bridge": ("concept_compiled", "serialDAT"),
        "osc_dat_protocol_bridge": ("concept_compiled", "oscinDAT"),
        "websocket_dat_protocol_bridge": ("concept_compiled", "websocketDAT"),
        "mqtt_dat_protocol_bridge": ("concept_compiled", "mqttclientDAT"),
        "udp_dat_protocol_bridge": ("concept_compiled", "udpinDAT"),
        "dat_execute_table_change_callback": ("concept_compiled", "datexecuteDAT"),
        "dat_table_render_switch": ("concept_compiled", "switchTOP"),
        "ndi_post_fx_output": ("concept_compiled", "ndiinTOP"),
        "glsl_advanced_pop_topology": ("concept_compiled", "glsladvancedPOP"),
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
    assert all(
        item.validation_profile in {"structural_visual_safe", "structural_visual_expensive"}
        for item in scenarios
    )
    expensive = [item for item in scenarios if item.validation_profile == "structural_visual_expensive"]
    assert [item.id for item in expensive] == ["render_pipeline_expensive_validation"]


@pytest.mark.asyncio
async def test_live_smoke_reports_profile_probe_summaries_without_expensive_defaults():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    glsl = scenarios["glsl_shader_top"]

    assert glsl["profile_probes"]
    assert any(item["probe_id"] == "compile_state" for item in glsl["profile_probes"])
    assert all(item["cost_level"] != "expensive" for item in glsl["profile_probes"])
    assert all(item["metric_names"] for item in glsl["profile_probes"])


@pytest.mark.asyncio
async def test_live_smoke_exercises_expensive_validation_only_when_explicitly_opted_in():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    expensive = scenarios["render_pipeline_expensive_validation"]
    default_render = scenarios["render_pipeline"]

    assert default_render["validation_profile"] == "structural_visual_safe"
    assert all(item["cost_level"] != "expensive" for item in default_render["profile_probes"])
    assert expensive["validation_profile"] == "structural_visual_expensive"
    render_probe = next(
        item for item in expensive["profile_probes"] if item["probe_id"] == "render_top_output"
    )
    render_result = next(
        item
        for item in expensive["profile_probe_results"]
        if item["probe_id"] == "render_top_output"
    )
    assert render_probe["cost_level"] == "expensive"
    assert render_probe["readback_strategy"] == "top_sample_optional"
    assert render_result["status"] == "runtime_contract_present"
    assert render_result["runtime_required"] is True
    assert render_result["pending_metric_names"] == ["render_luminance", "render_coverage"]


@pytest.mark.asyncio
async def test_live_smoke_reports_static_profile_probe_results():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    feedback = scenarios["feedback_loop"]
    results = {
        (item["profile"], item["probe_id"]): item for item in feedback["profile_probe_results"]
    }

    assert results[("feedback", "feedback_cycle")]["status"] == "static_pass"
    assert results[("feedback", "feedback_cycle")]["present_required_inputs"] == [
        "feedbackTOP",
        "compositeTOP",
    ]
    assert results[("feedback", "feedback_cycle")]["missing_required_inputs"] == []

    audio = scenarios["audio_reactive_top"]
    audio_results = {
        (item["profile"], item["probe_id"]): item for item in audio["profile_probe_results"]
    }
    activity = audio_results[("audio_reactive", "audio_signal_activity")]
    assert activity["status"] == "runtime_contract_present"
    assert activity["runtime_required"] is True
    assert activity["pending_metric_names"] == [
        "audio_analysis_channel_delta",
        "audio_analysis_channel_samples",
    ]


@pytest.mark.asyncio
async def test_compiler_backed_live_smoke_uses_candidate_profile_probes():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    material = scenarios["audio_glsl_material_render"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in material["profile_probes"]}

    assert ("audio_reactive", "analysis_stage") in probe_pairs
    assert ("audio_reactive", "audio_signal_activity") in probe_pairs
    assert ("render_pipeline", "camera_present") in probe_pairs
    assert ("glsl_material", "material_assigned") in probe_pairs
    assert ("concept_compiled", "feedback_cycle") not in probe_pairs
    assert ("concept_compiled", "panel_state_reader") not in probe_pairs
    assert "analysis_stage" in material["checks"]
    assert "material_assigned" in material["checks"]
    assert "feedback_cycle" not in material["checks"]
    assert "panel_state_reader" not in material["checks"]


@pytest.mark.asyncio
async def test_compiler_backed_live_smoke_reports_assembly_probe_results():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    showpiece = scenarios["audio_terrain_glass_controls"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in showpiece["profile_probes"]}
    result_pairs = {
        (item["profile"], item["probe_id"]): item for item in showpiece["profile_probe_results"]
    }

    assert ("concept_compiled", "component_shell_present") in probe_pairs
    assert ("concept_compiled", "output_node_present") in probe_pairs
    assert result_pairs[("concept_compiled", "component_shell_present")]["status"] == "static_pass"
    assert result_pairs[("concept_compiled", "component_shell_present")][
        "present_required_inputs"
    ] == ["baseCOMP"]
    assert result_pairs[("concept_compiled", "output_node_present")]["status"] == "static_pass"
    assert "component_shell_present" in showpiece["checks"]
    assert "output_node_present" in showpiece["checks"]


@pytest.mark.asyncio
async def test_live_smoke_covers_audio_terrain_material_controls_showpiece():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    showpiece = scenarios["audio_terrain_glass_controls"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in showpiece["profile_probes"]}

    assert showpiece["profile"] == "concept_compiled"
    assert showpiece["status"] == "planned"
    assert showpiece["output_top"] == "/project1/out1"
    assert showpiece["missing_expected_ops"] == []
    assert {
        "audiofileinCHOP",
        "analyzeCHOP",
        "mathCHOP",
        "nullCHOP",
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "glslMAT",
        "renderTOP",
        "containerCOMP",
        "sliderCOMP",
        "buttonCOMP",
        "panelCHOP",
        "errorDAT",
    }.issubset(set(showpiece["operators"]))
    assert ("audio_reactive", "analysis_stage") in probe_pairs
    assert ("render_pipeline", "camera_present") in probe_pairs
    assert ("glsl_material", "material_assigned") in probe_pairs
    assert ("panel_ui", "panel_state_reader") in probe_pairs
    assert "panel_state_reader" in showpiece["checks"]
    assert "material_assigned" in showpiece["checks"]


@pytest.mark.asyncio
async def test_live_smoke_reports_midi_control_probe_and_device_dependency():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    midi = scenarios["midi_control_bridge"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in midi["profile_probes"]}

    assert midi["profile"] == "concept_compiled"
    assert "midiinCHOP" in midi["operators"]
    assert "device-source-required" in midi["risk_flags"]
    assert "device-source-declared:midi_device" in midi["grounding_evidence"]
    assert ("midi_control", "midi_source_present") in probe_pairs
    assert "midi_source_present" in midi["checks"]


@pytest.mark.asyncio
async def test_live_smoke_reports_serial_dat_protocol_probe_and_device_dependency():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    serial = scenarios["serial_dat_protocol_bridge"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in serial["profile_probes"]}

    assert serial["profile"] == "concept_compiled"
    assert "serialDAT" in serial["operators"]
    assert "device-source-required" in serial["risk_flags"]
    assert ("dat_protocol", "serial_source_present") in probe_pairs
    assert "serial_source_present" in serial["checks"]


@pytest.mark.asyncio
async def test_live_smoke_reports_osc_dat_protocol_probe_and_device_dependency():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    osc = scenarios["osc_dat_protocol_bridge"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in osc["profile_probes"]}

    assert osc["profile"] == "concept_compiled"
    assert "oscinDAT" in osc["operators"]
    assert "device-source-required" in osc["risk_flags"]
    assert "device-source-declared:osc_source" in osc["grounding_evidence"]
    assert ("dat_protocol", "osc_source_present") in probe_pairs
    assert "osc_source_present" in osc["checks"]


@pytest.mark.asyncio
async def test_live_smoke_reports_websocket_dat_protocol_probe_and_device_dependency():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    websocket = scenarios["websocket_dat_protocol_bridge"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in websocket["profile_probes"]}

    assert websocket["profile"] == "concept_compiled"
    assert "websocketDAT" in websocket["operators"]
    assert "device-source-required" in websocket["risk_flags"]
    assert "device-source-declared:websocket_endpoint" in websocket["grounding_evidence"]
    assert ("dat_protocol", "websocket_source_present") in probe_pairs
    assert "websocket_source_present" in websocket["checks"]


@pytest.mark.asyncio
async def test_live_smoke_reports_mqtt_dat_protocol_probe_and_device_dependency():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    mqtt = scenarios["mqtt_dat_protocol_bridge"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in mqtt["profile_probes"]}

    assert mqtt["profile"] == "concept_compiled"
    assert "mqttclientDAT" in mqtt["operators"]
    assert "device-source-required" in mqtt["risk_flags"]
    assert "device-source-declared:mqtt_broker" in mqtt["grounding_evidence"]
    assert ("dat_protocol", "mqtt_source_present") in probe_pairs
    assert "mqtt_source_present" in mqtt["checks"]


@pytest.mark.asyncio
async def test_live_smoke_reports_udp_dat_protocol_probe_and_device_dependency():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    udp = scenarios["udp_dat_protocol_bridge"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in udp["profile_probes"]}

    assert udp["profile"] == "concept_compiled"
    assert "udpinDAT" in udp["operators"]
    assert "device-source-required" in udp["risk_flags"]
    assert "device-source-declared:udp_source" in udp["grounding_evidence"]
    assert ("dat_protocol", "udp_source_present") in probe_pairs
    assert "udp_source_present" in udp["checks"]


@pytest.mark.asyncio
async def test_live_smoke_reports_dat_execute_callback_probes_and_static_code_checks():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    callback = scenarios["dat_execute_table_change_callback"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in callback["profile_probes"]}

    assert callback["profile"] == "concept_compiled"
    assert "datexecuteDAT" in callback["operators"]
    assert "validate-python-callback" in callback["risk_flags"]
    assert ("dat_protocol", "dat_execute_callback_present") in probe_pairs
    assert ("dat_protocol", "callback_guard_present") in probe_pairs
    serial_source = next(
        item
        for item in callback["profile_probe_results"]
        if item["profile"] == "dat_protocol" and item["probe_id"] == "serial_source_present"
    )
    assert serial_source["status"] == "static_incomplete"
    assert serial_source["issue_code"] == "profile_probe_missing_required_inputs"
    assert "serial_source_present:" in serial_source["issue_message"]
    assert "serialDAT" in serial_source["issue_message"]
    assert "dat_execute_callback_present" in callback["checks"]
    assert "callback_guard_present" in callback["checks"]


@pytest.mark.asyncio
async def test_live_smoke_reports_dat_table_render_switch_probes():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    switch = scenarios["dat_table_render_switch"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in switch["profile_probes"]}
    result_pairs = {
        (item["profile"], item["probe_id"]): item for item in switch["profile_probe_results"]
    }

    assert switch["profile"] == "concept_compiled"
    assert {"tableDAT", "switchTOP", "nullTOP"}.issubset(set(switch["operators"]))
    assert ("dat_protocol", "render_switch_table_present") in probe_pairs
    assert ("dat_protocol", "render_switch_index_binding") in probe_pairs
    assert ("dat_protocol", "render_switch_output_present") in probe_pairs
    assert result_pairs[("dat_protocol", "render_switch_table_present")]["status"] == "static_pass"
    assert result_pairs[("dat_protocol", "render_switch_index_binding")]["status"] == "static_pass"
    assert result_pairs[("dat_protocol", "render_switch_index_binding")]["present_parameter_bindings"] == [
        "switchTOP.index<-tableDAT"
    ]
    assert result_pairs[("dat_protocol", "render_switch_output_present")]["status"] == "static_pass"
    assert "render_switch_table_present" in switch["checks"]
    assert "render_switch_index_binding" in switch["checks"]
    assert "render_switch_output_present" in switch["checks"]


@pytest.mark.asyncio
async def test_live_smoke_reports_generated_code_block_evidence_without_source_payloads():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    glsl = scenarios["glsl_shader_top"]
    callback = scenarios["dat_execute_table_change_callback"]

    assert glsl["generated_code_blocks"] == [
        {
            "block_id": "glsl_top_shader",
            "language": "glsl",
            "target_op": "/project1/glsl",
            "target_param": "pixeldat",
            "source_refs": ["/project1/text"],
            "static_checks": [
                "glsl_no_version_line",
                "glsl_top_declares_pixel_output",
                "glsl_top_uses_td_output_swizzle",
            ],
            "runtime_checks": ["compile_state"],
            "expected_outputs": ["/project1/out1"],
            "risk_flags": ["validate-glsl-compile-state"],
            "official_sources": [
                "https://docs.derivative.ca/GLSL_TOP",
                "https://docs.derivative.ca/Write_a_GLSL_TOP",
            ],
        }
    ]
    assert "code" not in glsl["generated_code_blocks"][0]

    callback_blocks = callback["generated_code_blocks"]
    assert len(callback_blocks) == 1
    assert callback_blocks[0]["block_id"] == "dat_execute_table_change_callback"
    assert callback_blocks[0]["language"] == "python"
    assert callback_blocks[0]["target_param"] == "text"
    assert "callback_guard_present" in callback_blocks[0]["runtime_checks"]
    assert "code" not in callback_blocks[0]


@pytest.mark.asyncio
async def test_live_smoke_reports_generated_code_runtime_contracts_without_source_payloads():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    glsl_contracts = scenarios["glsl_shader_top"]["generated_code_runtime_contracts"]
    callback_contracts = scenarios["dat_execute_table_change_callback"][
        "generated_code_runtime_contracts"
    ]

    assert glsl_contracts == [
        {
            "block_id": "glsl_top_shader",
            "check_id": "compile_state",
            "language": "glsl",
            "target_op": "/project1/glsl",
            "target_param": "pixeldat",
            "source_refs": ["/project1/text"],
            "expected_outputs": ["/project1/out1"],
            "risk_flags": ["validate-glsl-compile-state"],
            "official_sources": [
                "https://docs.derivative.ca/GLSL_TOP",
                "https://docs.derivative.ca/Write_a_GLSL_TOP",
            ],
        }
    ]
    assert {contract["check_id"] for contract in callback_contracts} == {
        "callback_guard_present",
        "diagnostic_output_present",
    }
    assert all("code" not in contract for contract in glsl_contracts + callback_contracts)


@pytest.mark.asyncio
async def test_live_smoke_reports_generated_code_coverage_summary():
    report = await build_live_smoke_report(mode="dry_run")

    summary = report["generated_code_summary"]

    assert summary["block_count"] >= 2
    assert {"glsl", "python"}.issubset(set(summary["languages"]))
    assert {"glsl_shader_top", "dat_execute_table_change_callback"}.issubset(
        set(summary["scenario_ids"])
    )
    assert {"compile_state", "callback_guard_present", "topology_capacity"}.issubset(
        set(summary["runtime_checks"])
    )
    assert "validate-glsl-compile-state" in summary["risk_flags"]
    assert summary["runtime_contract_count"] >= summary["block_count"]
    assert {"compile_state", "callback_guard_present", "topology_capacity"}.issubset(
        set(summary["runtime_contract_checks"])
    )
    assert summary["source_payloads_included"] is False


@pytest.mark.asyncio
async def test_live_smoke_reports_ndi_post_fx_probes_and_device_dependency():
    report = await build_live_smoke_report(mode="dry_run")
    scenarios = {item["id"]: item for item in report["scenarios"]}

    ndi = scenarios["ndi_post_fx_output"]
    probe_pairs = {(item["profile"], item["probe_id"]) for item in ndi["profile_probes"]}

    assert ndi["profile"] == "concept_compiled"
    assert "ndiinTOP" in ndi["operators"]
    assert "device-source-required" in ndi["risk_flags"]
    assert ("video_io", "ndi_source_present") in probe_pairs
    assert ("video_io", "post_fx_stage") in probe_pairs
    assert ("video_io", "top_output_present") in probe_pairs
    assert "ndi_source_present" in ndi["checks"]
    assert "post_fx_stage" in ndi["checks"]


@pytest.mark.asyncio
async def test_live_smoke_uses_docs_evidence_when_live_family_list_is_sparse():
    report = await build_live_smoke_report(
        mode="live", td_client=_SparseLiveClient(), card_index=_AllScenarioCards()
    )

    assert report["ok"] is True
    assert all(item["status"] == "planned" for item in report["scenarios"])
    assert any("family-list-omitted:feedbackTOP" in item["risk_flags"] for item in report["scenarios"])


@pytest.mark.asyncio
async def test_live_smoke_skips_live_scenarios_when_critical_operators_are_unavailable():
    report = await build_live_smoke_report(
        mode="live", td_client=_MissingAdvancedPopLiveClient(), card_index=_AllScenarioCards()
    )

    topology = next(item for item in report["scenarios"] if item["id"] == "glsl_advanced_pop_topology")

    assert report["ok"] is True
    assert report["mutated_td"] is False
    assert topology["status"] == "skipped_unavailable"
    assert "missing_op:glsladvancedPOP" in topology["missing_facts"]
    assert topology["blocked_questions"]


@pytest.mark.asyncio
async def test_live_smoke_normalizes_derivative_glsladv_pop_alias():
    report = await build_live_smoke_report(
        mode="live", td_client=_DerivativePopAliasLiveClient(), card_index=_AllScenarioCards()
    )

    topology = next(item for item in report["scenarios"] if item["id"] == "glsl_advanced_pop_topology")

    assert topology["status"] == "planned"
    assert "glsladvancedPOP" in topology["operators"]
    assert "missing_op:glsladvancedPOP" not in topology["missing_facts"]
    assert "topology_capacity" in report["generated_code_summary"]["runtime_contract_checks"]


@pytest.mark.asyncio
async def test_live_smoke_transactional_generated_code_smoke_is_opt_in_and_cleans_up():
    planning_only = await build_live_smoke_report(
        mode="live",
        td_client=_TransactionalGeneratedCodeLiveClient(),
        card_index=_AllScenarioCards(),
    )

    assert planning_only["mutated_td"] is False
    assert planning_only["transactional_generated_code_smoke"]["status"] == "not_run"

    client = _TransactionalGeneratedCodeLiveClient()
    report = await build_live_smoke_report(
        mode="live",
        td_client=client,
        card_index=_AllScenarioCards(),
        run_transactional_generated_code=True,
    )

    smoke = report["transactional_generated_code_smoke"]
    runtime_checks = {
        item["check_id"]: item for item in smoke["runtime_evidence"] if isinstance(item, dict)
    }

    assert report["ok"] is True
    assert report["mutated_td"] is True
    assert smoke["ok"] is True
    assert smoke["status"] == "cleaned_up"
    assert smoke["transaction_status"] == "clean"
    assert smoke["static_issue_count"] == 0
    assert smoke["validation_ok"] is True
    assert runtime_checks["compile_state"]["status"] == "runtime_pass"
    assert runtime_checks["callback_guard_present"]["status"] == "runtime_pass"
    assert runtime_checks["diagnostic_output_present"]["status"] == "runtime_pass"
    assert smoke["cleanup"]["rollback_performed"] is True
    assert smoke["cleanup"]["td_stable"] is True
    assert smoke["cleanup"]["remaining_created_paths"] == []
    assert ("project/lifecycle", {"action": "undo"}) in client.calls
    assert any(call[0] == "node/create" for call in client.calls)


@pytest.mark.asyncio
async def test_live_smoke_transactional_generated_code_smoke_reports_compile_failure_and_cleanup():
    client = _CompileFailGeneratedCodeLiveClient()

    report = await build_live_smoke_report(
        mode="live",
        td_client=client,
        card_index=_AllScenarioCards(),
        run_transactional_generated_code=True,
    )

    smoke = report["transactional_generated_code_smoke"]
    runtime_checks = {
        item["check_id"]: item for item in smoke["runtime_evidence"] if isinstance(item, dict)
    }

    assert report["ok"] is False
    assert report["mutated_td"] is True
    assert smoke["ok"] is False
    assert smoke["transaction_status"] == "rolled_back"
    assert smoke["validation_ok"] is False
    assert runtime_checks["compile_state"]["status"] == "runtime_fail"
    assert smoke["cleanup"]["rollback_performed"] is True
    assert smoke["cleanup"]["td_stable"] is True
    assert smoke["cleanup"]["remaining_created_paths"] == []
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


@pytest.mark.asyncio
async def test_live_smoke_transactional_generated_code_cleanup_deletes_when_undo_noops():
    client = _UndoNoopGeneratedCodeLiveClient()

    report = await build_live_smoke_report(
        mode="live",
        td_client=client,
        card_index=_AllScenarioCards(),
        run_transactional_generated_code=True,
    )

    cleanup = report["transactional_generated_code_smoke"]["cleanup"]

    assert report["ok"] is True
    assert cleanup["rollback_performed"] is True
    assert cleanup["fallback_delete_performed"] is True
    assert len(cleanup["fallback_deleted_paths"]) == 6
    assert cleanup["fallback_delete_errors"] == []
    assert cleanup["td_stable"] is True
    assert cleanup["remaining_created_paths"] == []
    assert any(call[0] == "node/delete" for call in client.calls)


@pytest.mark.asyncio
async def test_live_smoke_transactional_generated_code_cleanup_deletes_after_readback_failure():
    client = _CleanupReadbackFailGeneratedCodeLiveClient()

    report = await build_live_smoke_report(
        mode="live",
        td_client=client,
        card_index=_AllScenarioCards(),
        run_transactional_generated_code=True,
    )

    cleanup = report["transactional_generated_code_smoke"]["cleanup"]

    assert report["ok"] is True
    assert cleanup["rollback_error"] == ""
    assert cleanup["fallback_delete_performed"] is True
    assert cleanup["td_stable"] is True
    assert cleanup["remaining_created_paths"] == []
    assert client.failed_cleanup_readback is True


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
