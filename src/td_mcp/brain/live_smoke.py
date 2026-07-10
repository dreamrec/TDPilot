"""Live-smoke scenario catalog and dry-run report builder for the brain layer."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from td_mcp.brain.code_harness import (
    extract_generated_code_blocks,
    patch_plan_generated_code_runtime_contracts,
    validate_patch_plan_generated_code,
)
from td_mcp.brain.evals import StaticEvalTDClient, families_for_ops
from td_mcp.brain.planner import build_brain_plan
from td_mcp.brain.transaction import apply_transaction
from td_mcp.brain.validation_probes import probe_summaries_for_profile, probe_summaries_for_profiles
from td_mcp.brain.validators import (
    checks_for_profile,
    checks_for_profiles,
    static_profile_probe_metrics_for_plan,
)
from td_mcp.models.brain import TransactionOptions
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.undo_sentinel import UndoBlockSentinel
from td_mcp.report_identity import stamp_report_identity
from td_mcp.tool_registry import _direct_param_preflight_callback

SmokeMode = Literal["dry_run", "live"]

_CONCEPT_COMPILED_ASSEMBLY_PROBES = {"component_shell_present", "output_node_present"}


@dataclass(frozen=True)
class LiveSmokeScenario:
    """One release-gate scenario for the visual-programming brain."""

    id: str
    intent: str
    expected_profile: str
    expected_ops: tuple[str, ...]
    target_root: str = "/project1"
    output_top: str | None = None
    constraints: dict[str, Any] | None = None
    validation_profile: str = "structural_visual_safe"
    tools: tuple[str, ...] = ("td_brain_plan", "td_brain_execute", "td_transaction_apply")
    requires_live_td: bool = True
    expected_blocked: bool = False


def live_smoke_scenarios() -> tuple[LiveSmokeScenario, ...]:
    """Return the required vNext smoke scenarios."""
    return (
        LiveSmokeScenario(
            id="feedback_loop",
            intent="Build a stable feedback TOP loop with decay and a final null output.",
            expected_profile="feedback",
            expected_ops=("noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"),
            output_top="/project1/out1",
        ),
        LiveSmokeScenario(
            id="audio_reactive_top",
            intent="Create an audio reactive control chain from audio to analyzed range output.",
            expected_profile="audio_reactive",
            expected_ops=("audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"),
        ),
        LiveSmokeScenario(
            id="audio_feedback_level_binding",
            intent="Build an audio-reactive feedback visual with a control panel and debug output",
            expected_profile="concept_compiled",
            expected_ops=(
                "audiofileinCHOP",
                "analyzeCHOP",
                "mathCHOP",
                "nullCHOP",
                "noiseTOP",
                "feedbackTOP",
                "levelTOP",
                "compositeTOP",
                "nullTOP",
                "baseCOMP",
                "containerCOMP",
                "sliderCOMP",
                "buttonCOMP",
                "panelCHOP",
                "textDAT",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ),
            output_top="/project1/out1",
        ),
        LiveSmokeScenario(
            id="pop_particle_render",
            intent="Build a POP particle simulation with finite bounds and stable POP output.",
            expected_profile="pop",
            expected_ops=("circlePOP", "noisePOP", "mathmixPOP", "nullPOP", "rendersimpleTOP", "nullTOP"),
            output_top="/project1/out1",
        ),
        LiveSmokeScenario(
            id="glsl_shader_top",
            intent="Create a GLSL shader TOP with a source texture, shader source DAT, and output null.",
            expected_profile="glsl",
            expected_ops=("constantTOP", "glslTOP", "textDAT", "nullTOP"),
            output_top="/project1/out1",
        ),
        LiveSmokeScenario(
            id="glsl_material_render",
            intent="Create a GLSL material with vertex and pixel shader DATs on geometry, camera, Render TOP, and stable output.",
            expected_profile="glsl_material",
            expected_ops=("geometryCOMP", "glslMAT", "cameraCOMP", "renderTOP", "textDAT", "nullTOP"),
            output_top="/project1/out1",
        ),
        LiveSmokeScenario(
            id="audio_glsl_material_render",
            intent="Build an audio-reactive 3D render with material modulation",
            expected_profile="concept_compiled",
            expected_ops=(
                "audiofileinCHOP",
                "analyzeCHOP",
                "mathCHOP",
                "nullCHOP",
                "geometryCOMP",
                "cameraCOMP",
                "glslMAT",
                "renderTOP",
                "nullTOP",
                "textDAT",
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ),
            output_top="/project1/out1",
            expected_blocked=True,
        ),
        LiveSmokeScenario(
            id="audio_terrain_glass_controls",
            intent="Build a melting glass terrain driven by music with UI controls and debug output",
            expected_profile="concept_compiled",
            expected_ops=(
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
                "nullTOP",
                "textDAT",
                "containerCOMP",
                "sliderCOMP",
                "buttonCOMP",
                "panelCHOP",
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ),
            output_top="/project1/out1",
            expected_blocked=True,
        ),
        LiveSmokeScenario(
            id="glsl_pop_attribute_render",
            intent="Create a GLSL POP attribute shader with compute DAT, stable POP output, and rendered TOP preview.",
            expected_profile="glsl_pop",
            expected_ops=("circlePOP", "glslPOP", "textDAT", "nullPOP", "rendersimpleTOP", "nullTOP"),
            output_top="/project1/out1",
        ),
        LiveSmokeScenario(
            id="glsl_advanced_pop_topology",
            intent=(
                "Build a GLSL POP shader that changes point counts and writes topology "
                "with a stable TOP preview and debug output."
            ),
            expected_profile="concept_compiled",
            expected_ops=(
                "circlePOP",
                "glsladvancedPOP",
                "topologyPOP",
                "textDAT",
                "nullPOP",
                "rendersimpleTOP",
                "nullTOP",
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ),
            output_top="/project1/out1",
        ),
        LiveSmokeScenario(
            id="render_pipeline",
            intent="Build a render pipeline with geometry, camera, render TOP, and stable output.",
            expected_profile="render_pipeline",
            expected_ops=("geometryCOMP", "cameraCOMP", "renderTOP", "nullTOP"),
            output_top="/project1/out1",
        ),
        LiveSmokeScenario(
            id="render_pipeline_expensive_validation",
            intent="Build a render pipeline with explicit expensive output visibility validation.",
            expected_profile="render_pipeline",
            expected_ops=("geometryCOMP", "cameraCOMP", "renderTOP", "nullTOP"),
            output_top="/project1/out1",
            validation_profile="structural_visual_expensive",
        ),
        LiveSmokeScenario(
            id="panel_ui_controls",
            intent="Create a panel UI with slider, button, panel state reader, and control output.",
            expected_profile="panel_ui",
            expected_ops=("containerCOMP", "sliderCOMP", "buttonCOMP", "panelCHOP", "nullCHOP"),
        ),
        LiveSmokeScenario(
            id="custom_parameter_rig",
            intent="Build a custom parameter control rig with default values, range mapping, and output.",
            expected_profile="control_rig",
            expected_ops=("baseCOMP", "constantCHOP", "mathCHOP", "nullCHOP"),
        ),
        LiveSmokeScenario(
            id="midi_control_bridge",
            intent="Build a MIDI control bridge with normalized CHOP output.",
            expected_profile="concept_compiled",
            expected_ops=(
                "midiinCHOP",
                "mathCHOP",
                "nullCHOP",
                "baseCOMP",
                "annotateCOMP",
                "textDAT",
                "infoCHOP",
                "errorDAT",
            ),
            constraints={"device_sources": ["midi_device"]},
        ),
        LiveSmokeScenario(
            id="serial_dat_protocol_bridge",
            intent="Build a serial DAT protocol bridge with table diagnostics.",
            expected_profile="concept_compiled",
            expected_ops=(
                "serialDAT",
                "tableDAT",
                "nullDAT",
                "baseCOMP",
                "annotateCOMP",
                "textDAT",
                "infoCHOP",
                "errorDAT",
            ),
            constraints={"device_sources": ["serial_device"]},
        ),
        LiveSmokeScenario(
            id="osc_dat_protocol_bridge",
            intent="Create an OSC DAT protocol bridge with table diagnostics.",
            expected_profile="concept_compiled",
            expected_ops=(
                "oscinDAT",
                "tableDAT",
                "nullDAT",
                "baseCOMP",
                "annotateCOMP",
                "textDAT",
                "infoCHOP",
                "errorDAT",
            ),
            constraints={"device_sources": ["osc_source"]},
        ),
        LiveSmokeScenario(
            id="websocket_dat_protocol_bridge",
            intent="Create a WebSocket DAT protocol bridge with table diagnostics.",
            expected_profile="concept_compiled",
            expected_ops=(
                "websocketDAT",
                "tableDAT",
                "nullDAT",
                "baseCOMP",
                "annotateCOMP",
                "textDAT",
                "infoCHOP",
                "errorDAT",
            ),
            constraints={"device_sources": ["websocket_endpoint"]},
        ),
        LiveSmokeScenario(
            id="mqtt_dat_protocol_bridge",
            intent="Create an MQTT DAT protocol bridge with table diagnostics.",
            expected_profile="concept_compiled",
            expected_ops=(
                "mqttclientDAT",
                "tableDAT",
                "nullDAT",
                "baseCOMP",
                "annotateCOMP",
                "textDAT",
                "infoCHOP",
                "errorDAT",
            ),
            constraints={"device_sources": ["mqtt_broker"]},
        ),
        LiveSmokeScenario(
            id="udp_dat_protocol_bridge",
            intent="Create a UDP DAT protocol bridge with table diagnostics.",
            expected_profile="concept_compiled",
            expected_ops=(
                "udpinDAT",
                "tableDAT",
                "nullDAT",
                "baseCOMP",
                "annotateCOMP",
                "textDAT",
                "infoCHOP",
                "errorDAT",
            ),
            constraints={"device_sources": ["udp_source"]},
        ),
        LiveSmokeScenario(
            id="dat_execute_table_change_callback",
            intent="Build a DAT Execute table-change callback with stable DAT diagnostics.",
            expected_profile="concept_compiled",
            expected_ops=(
                "datexecuteDAT",
                "tableDAT",
                "textDAT",
                "nullDAT",
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ),
        ),
        LiveSmokeScenario(
            id="dat_table_render_switch",
            intent="Build a DAT table driven render switch with stable TOP output and debug output.",
            expected_profile="concept_compiled",
            expected_ops=(
                "tableDAT",
                "constantTOP",
                "noiseTOP",
                "switchTOP",
                "nullTOP",
                "baseCOMP",
                "annotateCOMP",
                "textDAT",
                "infoCHOP",
                "errorDAT",
            ),
            output_top="/project1/out1",
        ),
        LiveSmokeScenario(
            id="ndi_post_fx_output",
            intent="Build an NDI input with post FX and stable TOP output.",
            expected_profile="concept_compiled",
            expected_ops=(
                "ndiinTOP",
                "levelTOP",
                "nullTOP",
                "baseCOMP",
                "annotateCOMP",
                "textDAT",
                "infoCHOP",
                "errorDAT",
            ),
            output_top="/project1/out1",
            constraints={"device_sources": ["ndi_source"]},
        ),
        LiveSmokeScenario(
            id="broken_network_recovery",
            intent="Recover an intentionally broken feedback network and validate the repaired output.",
            expected_profile="feedback",
            expected_ops=("noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"),
            tools=("td_brain_plan", "td_brain_execute", "td_transaction_apply", "td_recover_network"),
            output_top="/project1/out1",
        ),
    )


async def build_live_smoke_report(
    *,
    mode: SmokeMode = "dry_run",
    td_client=None,
    card_index=None,
    host: str = "127.0.0.1",
    port: int = 9981,
    timeout: float = 15.0,
    run_transactional_generated_code: bool = False,
) -> dict[str, Any]:
    """Build a JSON-serializable smoke report.

    ``dry_run`` is deterministic and never touches TouchDesigner. ``live``
    connects to TD and plans against real operator/state data. Live mutation is
    still opt-in via ``run_transactional_generated_code`` and is cleaned up
    through the transaction undo block.

    Two-layer contract — ``panel_interaction_results`` and ``incident_replay``:
        This function ALWAYS emits these two fields as ``_panel_interactions_not_run()``
        / ``_incident_replay_not_run()`` placeholders (``ok: False``, ``status:
        "not_run"``). It does NOT run the panel-callback exercise or the
        incident-replay scratch build itself. Those are executed only by the CLI
        wrapper ``scripts/brain_live_smoke.py`` under ``--live
        --transactional-generated-code``, which splices the real results in over
        these placeholders. A direct caller of ``build_live_smoke_report`` (e.g.
        a future ``td_`` tool) therefore sees permanently-``not_run`` fields by
        design — treat ``status == "not_run"`` as "this layer was not exercised
        here", not as a failure to fix, and route through the CLI wrapper (or
        replicate its merge) if you need those tiers populated.
    """
    if mode not in {"dry_run", "live"}:
        raise ValueError("mode must be 'dry_run' or 'live'")

    started = time.perf_counter()
    scenarios = live_smoke_scenarios()
    client_to_close = None
    health: dict[str, Any] | None = None
    connection_error: str | None = None
    sync_diagnostic: dict[str, Any] = _sync_diagnostic_not_run(mode)

    if mode == "live":
        client = td_client
        card_index = card_index or _load_default_card_index()
        from td_mcp.auth_bootstrap import bootstrap_auth, default_env_file

        bootstrap_auth(default_env_file())
        if client is None:
            from td_mcp.td_client import TDClient  # Imported lazily for deterministic dry-run startup.

            client = TDClient(host=host, port=port, timeout=timeout, max_retries=0)
            client_to_close = client
        try:
            health = await client.health_check()
            sync_diagnostic = await _connection_sync_diagnostic(
                client,
                host=host,
                port=port,
                check_running_processes=client_to_close is not None,
            )
        except Exception as exc:  # noqa: BLE001
            connection_error = str(exc)
            sync_diagnostic = await _connection_sync_diagnostic(
                client,
                host=host,
                port=port,
                check_running_processes=client_to_close is not None,
            )
            if client_to_close is not None:
                await client_to_close.close()
            return _connection_failed_report(
                mode=mode,
                scenarios=scenarios,
                connection_error=connection_error,
                duration_ms=_elapsed_ms(started),
                sync_diagnostic=sync_diagnostic,
            )
    else:
        client = None

    transactional_smoke = _transactional_generated_code_not_run()
    performance_summary = _performance_not_run()
    try:
        scenario_reports = []
        for scenario in scenarios:
            scenario_client = client if mode == "live" else _static_client_for(scenario)
            scenario_reports.append(
                await _plan_scenario(
                    scenario,
                    scenario_client,
                    card_index=card_index,
                    allow_unavailable_skip=mode == "live",
                )
            )
        if mode == "live" and run_transactional_generated_code:
            transactional_smoke = await _run_transactional_generated_code_smoke(client)
            performance_summary = await _collect_performance_summary(client, target_root="/project1")
    finally:
        if client_to_close is not None:
            await client_to_close.close()

    ok_statuses = (
        {"planned", "blocked_expected", "skipped_unavailable"}
        if mode == "live"
        else {"planned", "blocked_expected"}
    )
    scenarios_ok = all(item["status"] in ok_statuses for item in scenario_reports)
    transactional_ok = transactional_smoke["status"] == "not_run" or bool(transactional_smoke.get("ok"))
    # `ok` reflects whether the planned scenarios + transactional smoke succeeded
    # — a pure function of the (possibly injected) TD client. The install-sync
    # diagnostic reads ambient machine state (installed version, plugin caches,
    # running processes) the smoke client cannot inject, so folding it into `ok`
    # made the result non-deterministic across machines/runs. It is reported
    # under `sync_diagnostic` and enforced separately by the release gate
    # (check_release_gates.py "brain live smoke sync diagnostic ok").
    ok = scenarios_ok and transactional_ok
    return stamp_report_identity(
        {
            "schema_version": 1,
            "mode": mode,
            "ok": ok,
            "mutated_td": bool(transactional_smoke.get("mutated_td")),
            "scenario_count": len(scenario_reports),
            "duration_ms": _elapsed_ms(started),
            "td_health": health,
            "connection_error": connection_error,
            "sync_diagnostic": sync_diagnostic,
            "visual_quality_summary": _visual_quality_summary(transactional_smoke),
            "panel_interaction_results": _panel_interactions_not_run(),
            "performance_summary": performance_summary,
            "incident_replay": _incident_replay_not_run(),
            "generated_code_summary": _generated_code_summary(scenario_reports),
            "transactional_generated_code_smoke": transactional_smoke,
            "scenarios": scenario_reports,
        }
    )


def _static_client_for(scenario: LiveSmokeScenario) -> StaticEvalTDClient:
    return StaticEvalTDClient(families=families_for_ops(list(scenario.expected_ops)), nodes=[])


async def _plan_scenario(
    scenario: LiveSmokeScenario,
    td_client,
    *,
    card_index=None,
    allow_unavailable_skip: bool = False,
) -> dict[str, Any]:
    try:
        plan = await build_brain_plan(
            td_client,
            intent=scenario.intent,
            target_root=scenario.target_root,
            output_top=scenario.output_top,
            constraints=scenario.constraints,
            validation_profile=scenario.validation_profile,
            card_index=card_index,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "id": scenario.id,
            "intent": scenario.intent,
            "profile": scenario.expected_profile,
            "target_root": scenario.target_root,
            "output_top": scenario.output_top,
            "validation_profile": scenario.validation_profile,
            "tools": list(scenario.tools),
            "requires_live_td": scenario.requires_live_td,
            "expected_blocked": scenario.expected_blocked,
            "status": "failed",
            "error": str(exc),
            "checks": checks_for_profile(scenario.validation_profile, scenario.expected_profile),
            "profile_probes": probe_summaries_for_profile(
                scenario.validation_profile, scenario.expected_profile
            ),
            "operators": list(scenario.expected_ops),
            "operation_count": 0,
            "generated_code_blocks": [],
            "generated_code_runtime_contracts": [],
            "control_bindings": [],
            "blocked_questions": [],
            "missing_facts": [],
        }

    missing_expected = sorted(set(scenario.expected_ops) - set(plan.concept_graph.operators))
    safely_blocked = (
        bool(plan.blocked_questions)
        and not plan.patch_plan.operations
        and not missing_expected
        and any(str(item).startswith(("intent_coverage:", "semantic_edge:")) for item in plan.missing_facts)
    )
    if scenario.expected_blocked:
        status = "blocked_expected" if safely_blocked else "expected_block_failed"
    else:
        status = "planned" if not plan.blocked_questions and not missing_expected else "blocked"
    if (
        allow_unavailable_skip
        and status == "blocked"
        and _is_unavailable_operator_skip(plan, missing_expected)
    ):
        status = "skipped_unavailable"
    probe_profiles = _probe_profiles_for_plan(plan)
    return {
        "id": scenario.id,
        "intent": scenario.intent,
        "profile": plan.concept_graph.profile,
        "target_root": scenario.target_root,
        "output_top": scenario.output_top,
        "validation_profile": plan.validation_profile,
        "tools": list(scenario.tools),
        "requires_live_td": scenario.requires_live_td,
        "expected_blocked": scenario.expected_blocked,
        "status": status,
        "plan_id": plan.id,
        "concept_graph_id": plan.concept_graph.id,
        "operators": plan.concept_graph.operators,
        "expected_ops": list(scenario.expected_ops),
        "missing_expected_ops": missing_expected,
        "operation_count": len(plan.patch_plan.operations),
        "generated_code_blocks": _generated_code_block_summaries(plan.patch_plan),
        "generated_code_runtime_contracts": patch_plan_generated_code_runtime_contracts(plan.patch_plan),
        "control_bindings": _control_binding_summaries(plan.patch_plan),
        "blocked_questions": plan.blocked_questions,
        "missing_facts": plan.missing_facts,
        "risk_flags": plan.risk_flags,
        "grounding_evidence": plan.grounding_evidence,
        "checks": _checks_for_plan(plan, probe_profiles),
        "profile_probes": _profile_probe_summaries_for_plan(plan, probe_profiles),
        "profile_probe_results": _profile_probe_results_for_plan(plan, probe_profiles),
    }


def _is_unavailable_operator_skip(plan, missing_expected: list[str]) -> bool:
    if missing_expected:
        return False
    missing_facts = [str(item) for item in plan.missing_facts]
    if not missing_facts:
        return False
    return all(item.startswith("missing_op:") for item in missing_facts)


def _probe_profiles_for_plan(plan) -> list[str]:
    """Return validation profiles represented by the selected plan graph."""
    if plan.concept_graph.profile == "concept_compiled" and plan.candidate_graphs:
        return list(dict.fromkeys(plan.candidate_graphs[0].profiles))
    return [plan.concept_graph.profile]


def _profile_probe_results_for_plan(plan, probe_profiles: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for profile in [*probe_profiles, *(_assembly_probe_profiles(plan))]:
        metrics = static_profile_probe_metrics_for_plan(
            plan.patch_plan,
            validation_profile=plan.validation_profile,
            concept_profile=profile,
        )
        for result in metrics["profile_probe_results"]:
            if not _include_probe_for_plan(plan, result):
                continue
            key = (str(result["profile"]), str(result["probe_id"]))
            if key in seen:
                continue
            seen.add(key)
            results.append(result)
    return results


def _profile_probe_summaries_for_plan(plan, probe_profiles: list[str]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for profile in [*probe_profiles, *(_assembly_probe_profiles(plan))]:
        for summary in probe_summaries_for_profiles(plan.validation_profile, [profile]):
            if not _include_probe_for_plan(plan, summary):
                continue
            key = (str(summary["profile"]), str(summary["probe_id"]))
            if key in seen:
                continue
            seen.add(key)
            summaries.append(summary)
    return summaries


def _checks_for_plan(plan, probe_profiles: list[str]) -> list[str]:
    checks = checks_for_profiles(plan.validation_profile, probe_profiles)
    for summary in _profile_probe_summaries_for_plan(plan, []):
        checks.append(str(summary["probe_id"]))
    return list(dict.fromkeys(checks))


def _assembly_probe_profiles(plan) -> list[str]:
    if plan.concept_graph.profile == "concept_compiled":
        return ["concept_compiled"]
    return []


def _include_probe_for_plan(plan, probe: dict[str, Any]) -> bool:
    if probe.get("profile") != "concept_compiled":
        return True
    if plan.concept_graph.profile != "concept_compiled":
        return True
    return str(probe.get("probe_id")) in _CONCEPT_COMPILED_ASSEMBLY_PROBES


def _generated_code_block_summaries(patch_plan) -> list[dict[str, Any]]:
    """Return smoke-safe generated-code metadata without source payloads."""
    return [
        {
            "block_id": block.block_id,
            "language": block.language,
            "target_op": block.target_op,
            "target_param": block.target_param,
            "source_refs": list(block.source_refs),
            "static_checks": list(block.static_checks),
            "runtime_checks": list(block.runtime_checks),
            "expected_outputs": list(block.expected_outputs),
            "risk_flags": list(block.risk_flags),
            "official_sources": list(block.official_sources),
        }
        for block in extract_generated_code_blocks(patch_plan)
    ]


def _control_binding_summaries(patch_plan: PatchPlan) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for operation in patch_plan.operations:
        if operation.kind != "set_params" or not operation.target:
            continue
        params = operation.args.get("params")
        if not isinstance(params, dict):
            continue
        for name, value in params.items():
            if not isinstance(value, dict) or set(value) != {"expr"}:
                continue
            expression = value.get("expr")
            if not isinstance(expression, str) or not expression.startswith("op("):
                continue
            summaries.append(
                {
                    "target": operation.target,
                    "param": str(name),
                    "expression": expression,
                }
            )
    return summaries


def _generated_code_summary(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    blocks: list[tuple[str, dict[str, Any]]] = []
    contracts: list[tuple[str, dict[str, Any]]] = []
    for scenario in scenarios:
        scenario_id = str(scenario.get("id") or "")
        for block in scenario.get("generated_code_blocks", []):
            if isinstance(block, dict):
                blocks.append((scenario_id, block))
        for contract in scenario.get("generated_code_runtime_contracts", []):
            if isinstance(contract, dict):
                contracts.append((scenario_id, contract))

    return {
        "block_count": len(blocks),
        "scenario_ids": sorted({scenario_id for scenario_id, _block in blocks if scenario_id}),
        "languages": sorted(
            {str(block.get("language")) for _scenario_id, block in blocks if block.get("language")}
        ),
        "runtime_checks": sorted(
            {str(check) for _scenario_id, block in blocks for check in block.get("runtime_checks", [])}
        ),
        "runtime_contract_count": len(contracts),
        "runtime_contract_checks": sorted(
            {
                str(contract.get("check_id"))
                for _scenario_id, contract in contracts
                if contract.get("check_id")
            }
        ),
        "risk_flags": sorted(
            {str(flag) for _scenario_id, block in blocks for flag in block.get("risk_flags", [])}
        ),
        "source_payloads_included": any("code" in block for _scenario_id, block in blocks),
    }


def _transactional_generated_code_not_run() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "not_run",
        "ok": None,
        "mutated_td": False,
        "runtime_evidence": [],
        "cleanup": {
            "rollback_performed": False,
            "td_stable": True,
            "remaining_created_paths": [],
        },
    }


async def _run_transactional_generated_code_smoke(td_client) -> dict[str, Any]:
    started = time.perf_counter()
    plan = _transactional_generated_code_patch_plan()
    static_issues = validate_patch_plan_generated_code(plan)
    if static_issues:
        return {
            "schema_version": 1,
            "status": "static_failed",
            "ok": False,
            "mutated_td": False,
            "duration_ms": _elapsed_ms(started),
            "plan_id": plan.id,
            "static_issue_count": len(static_issues),
            "static_issues": [issue.model_dump(mode="json") for issue in static_issues],
            "generated_code_blocks": _generated_code_block_summaries(plan),
            "runtime_contracts": patch_plan_generated_code_runtime_contracts(plan),
            "runtime_evidence": [],
            "cleanup": {
                "rollback_performed": False,
                "td_stable": True,
                "remaining_created_paths": [],
            },
        }

    result = await apply_transaction(
        td_client,
        plan,
        options=TransactionOptions(
            snapshot_before=False,
            rollback_on_apply_failure=True,
            rollback_on_validation_failure=True,
            validation_profile="structural_visual_safe",
        ),
        sentinel=UndoBlockSentinel(),
        concept_profile="glsl",
        concept_profiles=["glsl"],
        param_preflight=_direct_param_preflight_callback(safety_manager=None),
    )
    cleanup = await _cleanup_transactional_generated_code_smoke(
        td_client,
        plan,
        already_rolled_back=result.rollback_performed,
    )
    validation_report = result.validation_report
    runtime_evidence = _generated_code_runtime_evidence(result)
    validation_ok = bool(validation_report and validation_report.ok)
    ok = (
        result.status in {"clean", "warnings"}
        and not result.validation_failed
        and validation_ok
        and bool(cleanup.get("td_stable"))
        and not cleanup.get("remaining_created_paths")
    )
    status = "cleaned_up" if ok else result.status
    return {
        "schema_version": 1,
        "status": status,
        "ok": ok,
        "mutated_td": True,
        "duration_ms": _elapsed_ms(started),
        "plan_id": plan.id,
        "transaction_status": result.status,
        "validation_ok": validation_ok,
        "validation_failed": result.validation_failed,
        "validation_checks": list(validation_report.checks) if validation_report else [],
        "validation_cheap_metrics": validation_report.cheap_metrics if validation_report else {},
        "validation_issues": [
            issue.model_dump(mode="json") for issue in (validation_report.issues if validation_report else [])
        ],
        "static_issue_count": 0,
        "generated_code_blocks": _generated_code_block_summaries(plan),
        "runtime_contracts": patch_plan_generated_code_runtime_contracts(plan),
        "runtime_evidence": runtime_evidence,
        "cleanup": cleanup,
    }


def _transactional_generated_code_patch_plan() -> PatchPlan:
    target_root = "/project1"
    glsl_path = f"{target_root}/tdpilot_gc_smoke_glsl"
    shader_path = f"{target_root}/tdpilot_gc_smoke_pixel"
    callback_path = f"{target_root}/tdpilot_gc_smoke_callbacks"
    debug_path = f"{target_root}/tdpilot_gc_smoke_debug"
    out_path = f"{target_root}/tdpilot_gc_smoke_out"
    shader_source = (
        "layout(location = 0) out vec4 fragColor;\n"
        "float hash21(vec2 p)\n"
        "{\n"
        "    p = fract(p * vec2(123.34, 456.21));\n"
        "    p += dot(p, p + 45.32);\n"
        "    return fract(p.x * p.y);\n"
        "}\n"
        "void main()\n"
        "{\n"
        "    vec2 uv = vUV.st;\n"
        "    float cells = hash21(floor(uv * 24.0));\n"
        "    float wave = 0.5 + 0.5 * sin((uv.x * 17.0 + uv.y * 11.0) * 6.2831853);\n"
        "    float lattice = 1.0 - smoothstep(0.0, 0.035, min(abs(fract(uv.x * 12.0) - 0.5), abs(fract(uv.y * 12.0) - 0.5)));\n"
        "    vec3 color = mix(vec3(0.05, 0.16, 0.31), vec3(0.86, 0.94, 0.48), wave);\n"
        "    color = mix(color, vec3(0.95, 0.28, 0.22), cells * 0.45 + lattice * 0.35);\n"
        "    fragColor = TDOutputSwizzle(vec4(color, 1.0));\n"
        "}\n"
    )
    callback_source = (
        "tdpilot_callback_guard = False\n\n"
        "def onTableChange(dat, prevDAT, info):\n"
        "    global tdpilot_callback_guard\n"
        "    if tdpilot_callback_guard:\n"
        "        return\n"
        "    tdpilot_callback_guard = True\n"
        "    try:\n"
        "        op('tdpilot_gc_smoke_debug').appendRow(['changed'])\n"
        "    finally:\n"
        "        tdpilot_callback_guard = False\n"
    )
    operations = [
        PatchOperation(
            kind="create_node",
            target=target_root,
            args={"op_type": "constantTOP", "name": "tdpilot_gc_smoke_const"},
        ),
        PatchOperation(
            kind="create_node",
            target=target_root,
            args={"op_type": "textDAT", "name": "tdpilot_gc_smoke_pixel"},
        ),
        PatchOperation(
            kind="create_node",
            target=target_root,
            args={"op_type": "glslTOP", "name": "tdpilot_gc_smoke_glsl"},
        ),
        PatchOperation(
            kind="create_node",
            target=target_root,
            args={"op_type": "nullTOP", "name": "tdpilot_gc_smoke_out"},
        ),
        PatchOperation(
            kind="create_node",
            target=target_root,
            args={"op_type": "tableDAT", "name": "tdpilot_gc_smoke_debug"},
        ),
        PatchOperation(
            kind="create_node",
            target=target_root,
            args={"op_type": "datexecuteDAT", "name": "tdpilot_gc_smoke_callbacks"},
        ),
        PatchOperation(
            kind="set_dat_content",
            target=shader_path,
            args={
                "text": shader_source,
                "generated_code": {
                    "block_id": "transactional_glsl_top_shader",
                    "language": "glsl",
                    "target_op": glsl_path,
                    "target_param": "pixeldat",
                    "source_kind": "textDAT",
                    "source_refs": [shader_path],
                    "static_checks": [
                        "glsl_no_version_line",
                        "glsl_top_declares_pixel_output",
                        "glsl_top_uses_td_output_swizzle",
                    ],
                    "runtime_checks": ["compile_state"],
                    "expected_outputs": [out_path],
                    "risk_flags": ["validate-glsl-compile-state"],
                    "official_sources": [
                        "https://docs.derivative.ca/GLSL_TOP",
                        "https://docs.derivative.ca/Write_a_GLSL_TOP",
                    ],
                },
            },
        ),
        PatchOperation(
            kind="set_params",
            target=glsl_path,
            args={
                "params": {
                    "pixeldat": shader_path,
                    "outputresolution": "custom",
                    "resolutionw": 512,
                    "resolutionh": 512,
                }
            },
        ),
        PatchOperation(
            kind="connect", args={"from": f"{target_root}/tdpilot_gc_smoke_const", "to": glsl_path}
        ),
        PatchOperation(kind="connect", args={"from": glsl_path, "to": out_path}),
        PatchOperation(
            kind="set_dat_content",
            target=callback_path,
            args={
                "text": callback_source,
                "generated_code": {
                    "block_id": "transactional_dat_execute_callback",
                    "language": "python",
                    "target_op": callback_path,
                    "target_param": "text",
                    "source_kind": "datexecuteDAT",
                    "source_refs": [callback_path],
                    "static_checks": ["python_syntax", "dat_execute_table_change_callback"],
                    "runtime_checks": ["callback_guard_present", "diagnostic_output_present"],
                    "expected_outputs": [debug_path],
                    "risk_flags": ["validate-python-callback"],
                    "official_sources": ["https://docs.derivative.ca/DAT_Execute_DAT"],
                },
            },
        ),
        PatchOperation(
            kind="set_params",
            target=callback_path,
            args={
                "params": {
                    "active": True,
                    "dat": debug_path,
                    "tablechange": True,
                    "rowchange": False,
                    "colchange": False,
                    "cellchange": False,
                    "sizechange": False,
                }
            },
        ),
    ]
    return PatchPlan(
        intent="transactional live generated-code smoke",
        target_root=target_root,
        source="operations",
        operations=operations,
        required_ops=[
            "constantTOP",
            "textDAT",
            "glslTOP",
            "nullTOP",
            "tableDAT",
            "datexecuteDAT",
        ],
        risk_flags=["live-generated-code-smoke"],
        undo_label="tdpilot live generated-code smoke",
        validation_plan=ValidationPlan(target_root=target_root),
    )


async def _cleanup_transactional_generated_code_smoke(
    td_client,
    plan: PatchPlan,
    *,
    already_rolled_back: bool,
) -> dict[str, Any]:
    rollback_performed = bool(already_rolled_back)
    rollback_error = ""
    nodes_readback_error = ""
    fallback_deleted_paths: list[str] = []
    fallback_delete_errors: list[dict[str, str]] = []
    if not rollback_performed:
        try:
            await td_client.request("project/lifecycle", {"action": "undo"})
            rollback_performed = True
        except Exception as exc:  # noqa: BLE001
            rollback_error = str(exc)

    remaining_created_paths: list[str] = []
    try:
        remaining_created_paths = await _read_remaining_transactional_paths(td_client, plan)
    except Exception as exc:  # noqa: BLE001
        nodes_readback_error = f"cleanup nodes readback failed: {exc}"
        remaining_created_paths = _planned_created_paths(plan)
    if remaining_created_paths:
        for path in remaining_created_paths:
            try:
                await td_client.request("node/delete", {"path": path})
                fallback_deleted_paths.append(path)
            except Exception as exc:  # noqa: BLE001
                fallback_delete_errors.append({"path": path, "error": str(exc)})
        try:
            remaining_created_paths = await _read_remaining_transactional_paths(td_client, plan)
            nodes_readback_error = ""
        except Exception as exc:  # noqa: BLE001
            nodes_readback_error = f"cleanup nodes readback failed: {exc}"

    rollback_error = rollback_error or nodes_readback_error

    error_issues: list[Any] = []
    try:
        errors = await td_client.request(
            "node/errors",
            {"path": plan.target_root, "recurse": True, "max_depth": 10},
        )
        error_issues = (
            errors.get("issues", [])
            if isinstance(errors, dict)
            else errors
            if isinstance(errors, list)
            else []
        )
    except Exception as exc:  # noqa: BLE001
        rollback_error = rollback_error or f"cleanup errors readback failed: {exc}"

    stuck: list[Any] = []
    try:
        cooking = await td_client.request("cooking", {"path": plan.target_root})
        stuck = cooking.get("stuck", []) if isinstance(cooking, dict) else []
    except Exception as exc:  # noqa: BLE001
        rollback_error = rollback_error or f"cleanup cooking readback failed: {exc}"

    return {
        "rollback_performed": rollback_performed,
        "rollback_error": rollback_error,
        "fallback_delete_performed": bool(fallback_deleted_paths or fallback_delete_errors),
        "fallback_deleted_paths": fallback_deleted_paths,
        "fallback_delete_errors": fallback_delete_errors,
        "remaining_created_paths": remaining_created_paths,
        "td_stable": (
            not rollback_error
            and not fallback_delete_errors
            and not remaining_created_paths
            and not error_issues
            and not stuck
        ),
        "error_issue_count": len(error_issues),
        "stuck_cook_count": len(stuck),
    }


async def _read_remaining_transactional_paths(td_client, plan: PatchPlan) -> list[str]:
    created_paths = _planned_created_paths(plan)
    payload = await td_client.request("nodes", {"path": plan.target_root, "limit": 1000})
    nodes = (
        payload
        if isinstance(payload, list)
        else payload.get("nodes", [])
        if isinstance(payload, dict)
        else []
    )
    live_paths = {
        str(node.get("path") or "") for node in nodes if isinstance(node, dict) and node.get("path")
    }
    return sorted(path for path in created_paths if path in live_paths)


def _planned_created_paths(plan: PatchPlan) -> list[str]:
    paths: list[str] = []
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        parent = str(operation.target or plan.target_root).rstrip("/")
        name = str(operation.args.get("name") or "")
        if not name:
            continue
        paths.append(f"{parent}/{name}".replace("//", "/"))
    return paths


def _generated_code_runtime_evidence(result) -> list[dict[str, Any]]:
    if result.validation_report is None:
        return []
    runtime = result.validation_report.cheap_metrics.get("generated_code_runtime", {})
    evidence = runtime.get("evidence") if isinstance(runtime, dict) else []
    if not isinstance(evidence, list):
        return []
    return [item for item in evidence if isinstance(item, dict)]


def _connection_failed_report(
    *,
    mode: SmokeMode,
    scenarios: tuple[LiveSmokeScenario, ...],
    connection_error: str,
    duration_ms: float,
    sync_diagnostic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    remediation = (
        "Verify TD_MCP_SHARED_SECRET in the MCP process and canonical .tdpilot env file, "
        "then restart the MCP server and TouchDesigner WebServer component."
    )
    return stamp_report_identity(
        {
            "schema_version": 1,
            "mode": mode,
            "ok": False,
            "mutated_td": False,
            "scenario_count": len(scenarios),
            "duration_ms": duration_ms,
            "td_health": None,
            "connection_error": connection_error,
            "sync_diagnostic": sync_diagnostic or {},
            "visual_quality_summary": _visual_quality_summary(_transactional_generated_code_not_run()),
            "panel_interaction_results": _panel_interactions_not_run(),
            "performance_summary": _performance_not_run(),
            "incident_replay": _incident_replay_not_run(),
            "remediation": remediation,
            "generated_code_summary": _generated_code_summary([]),
            "transactional_generated_code_smoke": _transactional_generated_code_not_run(),
            "scenarios": [
                {
                    "id": scenario.id,
                    "intent": scenario.intent,
                    "profile": scenario.expected_profile,
                    "target_root": scenario.target_root,
                    "output_top": scenario.output_top,
                    "validation_profile": scenario.validation_profile,
                    "tools": list(scenario.tools),
                    "requires_live_td": scenario.requires_live_td,
                    "expected_blocked": scenario.expected_blocked,
                    "status": "skipped_no_td",
                    "operators": list(scenario.expected_ops),
                    "checks": checks_for_profile(scenario.validation_profile, scenario.expected_profile),
                    "profile_probes": probe_summaries_for_profile(
                        scenario.validation_profile, scenario.expected_profile
                    ),
                    "generated_code_blocks": [],
                    "generated_code_runtime_contracts": [],
                    "control_bindings": [],
                    "blocked_questions": [],
                    "missing_facts": ["TouchDesigner was not reachable for live smoke planning."],
                }
                for scenario in scenarios
            ],
        }
    )


async def _connection_sync_diagnostic(
    client,
    *,
    host: str,
    port: int,
    check_running_processes: bool = True,
) -> dict[str, Any]:
    try:
        from td_mcp.sync_diagnostics import diagnose_sync

        return await diagnose_sync(
            client=client,
            host=host,
            port=port,
            include_live=True,
            install_roots=None if check_running_processes else {},
            running_processes=None if check_running_processes else [],
        )
    except Exception as exc:  # noqa: BLE001
        return {"schema_version": 1, "ok": False, "error": str(exc)}


def _sync_diagnostic_not_run(mode: SmokeMode) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ok": None,
        "skipped": True,
        "reason": f"sync diagnosis is not run in {mode} mode before live connection",
    }


def _visual_quality_summary(transactional_smoke: dict[str, Any]) -> dict[str, Any]:
    metrics = transactional_smoke.get("validation_cheap_metrics")
    visual_quality = metrics.get("visual_quality") if isinstance(metrics, dict) else None
    if not isinstance(visual_quality, dict):
        return {
            "ok": False,
            "checked_count": 0,
            "failed_count": 0,
            "missing_count": 0,
            "status": "not_run",
        }
    checked = 0
    failed = 0
    missing = 0
    paths: list[str] = []
    failed_paths: list[str] = []
    for path, quality in visual_quality.items():
        checked += 1
        paths.append(str(path))
        if not isinstance(quality, dict):
            failed += 1
            failed_paths.append(str(path))
            continue
        if quality.get("missing") is True:
            missing += 1
            failed_paths.append(str(path))
            continue
        if quality.get("pass") is not True:
            failed += 1
            failed_paths.append(str(path))
    return {
        "ok": checked > 0 and failed == 0 and missing == 0,
        "checked_count": checked,
        "failed_count": failed,
        "missing_count": missing,
        "paths": sorted(paths),
        "failed_paths": sorted(set(failed_paths)),
        "status": "checked" if checked else "not_run",
    }


def _panel_interactions_not_run() -> dict[str, Any]:
    # Two-layer contract: build_live_smoke_report always returns THIS placeholder;
    # the real panel-callback exercise runs only in scripts/brain_live_smoke.py
    # under --live --transactional-generated-code, which splices its result in
    # over this. status == "not_run" here means "not exercised at this layer", not
    # a failure to fix. See build_live_smoke_report's docstring.
    return {
        "ok": False,
        "checked_count": 0,
        "failed_count": 0,
        "status": "not_run",
        "reason": (
            "panel reset/thumb/next/prev/back interaction validator was not run "
            "(populated only by scripts/brain_live_smoke.py --live "
            "--transactional-generated-code)"
        ),
    }


def _performance_not_run() -> dict[str, Any]:
    return {
        "ok": False,
        "status": "not_run",
        "steady_state_max_ms": None,
        "frame_budget_ms": 16.667,
        "safety_target_ms": 12.0,
        "warmup_spike_recorded": False,
        "target_root_spike_count": None,
        "sys_ui_spike_count": None,
        "sample_interval_s": None,
        "frames_advanced": None,
        "frame_advance_ok": None,
    }


# Steady-state sampling is measured over a real wall-clock window, not
# back-to-back. The old loop fired 3 "cooking" requests separated only by
# ``asyncio.sleep(0)`` (all resolved within milliseconds), so "steady state"
# was indistinguishable from warmup and could report a cached cook reading as a
# passing frame budget. We now take one warmup sample plus several steady
# samples spaced by a real interval, and record the ``absTime.frame`` delta
# across the window so a frozen/cached graph (frames_advanced == 0) is visible
# rather than silently passing. See eval-truth audit finding
# "Live-smoke performance summary measures back-to-back samples".
_PERF_STEADY_SAMPLES = 5
_PERF_SAMPLE_INTERVAL_S = 0.5


async def _collect_performance_summary(
    td_client,
    *,
    target_root: str,
    sample_interval_s: float = _PERF_SAMPLE_INTERVAL_S,
    steady_samples: int = _PERF_STEADY_SAMPLES,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    frames: list[int] = []
    total_samples = 1 + max(1, steady_samples)  # warmup + steady window
    for index in range(total_samples):
        if index > 0 and sample_interval_s > 0:
            # Real gap so successive samples reflect steady-state cook, not a
            # burst of back-to-back reads of the same cached frame.
            await asyncio.sleep(sample_interval_s)
        try:
            payload = await td_client.request(
                "cooking", {"path": target_root, "recurse": True, "max_depth": 10}
            )
        except Exception as exc:  # noqa: BLE001
            return {
                **_performance_not_run(),
                "status": "failed",
                "error": str(exc),
            }
        samples.append(_cook_sample_summary(payload, sample_index=index))
        frame_value = _sample_frame(payload)
        if frame_value is not None:
            frames.append(frame_value)

    # Frame-advance evidence: absTime.frame must move across the sampling window,
    # otherwise the timeline is paused/frozen and the "steady state" numbers are
    # not describing a live-cooking graph.
    frames_advanced = (frames[-1] - frames[0]) if len(frames) >= 2 else None
    frame_advance_ok = (frames_advanced is not None and frames_advanced > 0) if frames else None

    warmup_max = _max_cook_for_prefixes(samples[0], (target_root,)) if samples else None
    global_steady_values = [sample["max_ms"] for sample in samples[1:] if sample["max_ms"] is not None]
    steady_values = [
        value
        for sample in samples[1:]
        for value in [_max_cook_for_prefixes(sample, (target_root,))]
        if value is not None
    ]
    frame_budget_ms = 16.667
    global_steady_max = max(global_steady_values) if global_steady_values else None
    steady_max = max(steady_values) if steady_values else None
    target_root_spike_count = sum(
        1
        for sample in samples[1:]
        for node in sample.get("nodes", [])
        if str(node.get("path") or "").startswith(target_root)
        and float(node.get("cook_ms") or 0.0) > frame_budget_ms
    )
    sys_ui_spike_count = sum(
        1
        for sample in samples[1:]
        for node in sample.get("nodes", [])
        if str(node.get("path") or "").startswith(("/sys", "/ui"))
        and float(node.get("cook_ms") or 0.0) > frame_budget_ms
    )
    return {
        "ok": steady_max is not None and steady_max <= frame_budget_ms,
        "status": "checked" if steady_max is not None else "missing_metrics",
        "sample_count": len(samples),
        "warmup_max_ms": warmup_max,
        "steady_state_max_ms": steady_max,
        "global_steady_state_max_ms": global_steady_max,
        "frame_budget_ms": frame_budget_ms,
        "safety_target_ms": 12.0,
        "warmup_spike_recorded": warmup_max is not None,
        "target_root_spike_count": target_root_spike_count,
        "sys_ui_spike_count": sys_ui_spike_count,
        "sample_interval_s": sample_interval_s,
        "frames_advanced": frames_advanced,
        "frame_advance_ok": frame_advance_ok,
        "samples": samples,
    }


def _sample_frame(payload: Any) -> int | None:
    """Extract the ``absTime.frame`` reported by a cooking payload, or None.

    The TD ``cooking`` endpoint returns a top-level ``frame`` (handle_cooking_info
    in mcp_webserver_callbacks.py). Used to prove the timeline advanced across the
    steady-state window rather than reading a paused/cached frame repeatedly.
    """
    if isinstance(payload, dict):
        raw = payload.get("frame")
        if isinstance(raw, bool):
            return None
        if isinstance(raw, (int, float)):
            return int(raw)
    return None


def _cook_sample_summary(payload: Any, *, sample_index: int) -> dict[str, Any]:
    nodes = _cook_nodes(payload)
    normalized_nodes: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        cook_ms = _node_cook_ms(node)
        if cook_ms is None:
            continue
        normalized_nodes.append(
            {
                "path": str(node.get("path") or node.get("node") or ""),
                "cook_ms": cook_ms,
            }
        )
    max_ms = max((node["cook_ms"] for node in normalized_nodes), default=None)
    return {
        "sample_index": sample_index,
        "max_ms": max_ms,
        "node_count": len(normalized_nodes),
        "nodes": normalized_nodes,
    }


def _max_cook_for_prefixes(sample: dict[str, Any], prefixes: tuple[str, ...]) -> float | None:
    values = [
        float(node.get("cook_ms") or 0.0)
        for node in sample.get("nodes", [])
        if isinstance(node, dict) and str(node.get("path") or "").startswith(prefixes)
    ]
    return max(values) if values else None


def _cook_nodes(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("nodes", "cooks", "cooking", "top_cooks", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _node_cook_ms(node: dict[str, Any]) -> float | None:
    for key in ("cookTime", "cook_time", "cook_ms", "cpuCookTime", "cpu_cook_time"):
        value = node.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _incident_replay_not_run() -> dict[str, Any]:
    # Two-layer contract: build_live_smoke_report always returns THIS placeholder;
    # the incident replay runs only in scripts/brain_live_smoke.py under --live
    # --transactional-generated-code, which merges its result in. status ==
    # "not_run" here means "not exercised at this layer", not a failure to fix.
    # See build_live_smoke_report's docstring.
    return {
        "ok": False,
        "status": "not_run",
        "bug_count": 0,
        "untriaged": [],
        "reason": (
            "scripts/replay_live_debug_incident.py was not run inside this "
            "live-smoke report (populated only by scripts/brain_live_smoke.py "
            "--live --transactional-generated-code)"
        ),
    }


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _load_default_card_index():
    try:
        from td_mcp.knowledge.docsbrain import DocsBrain

        root = Path(__file__).resolve().parents[3] / "data" / "normalized" / "derivative"
        db_path = root / "docsbrain.db"
        if db_path.exists():
            return DocsBrain(
                db_path=db_path,
                changelog_path=root / "operator_changelog.json",
                manifest_path=root / "build_manifest.json",
            )
    except Exception:  # noqa: BLE001
        return None
    return None


__all__ = [
    "LiveSmokeScenario",
    "build_live_smoke_report",
    "live_smoke_scenarios",
]
