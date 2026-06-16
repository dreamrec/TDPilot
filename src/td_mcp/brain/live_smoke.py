"""Live-smoke scenario catalog and dry-run report builder for the brain layer."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from td_mcp.brain.evals import StaticEvalTDClient, families_for_ops
from td_mcp.brain.planner import build_brain_plan
from td_mcp.brain.validators import checks_for_profile

SmokeMode = Literal["dry_run", "live"]


@dataclass(frozen=True)
class LiveSmokeScenario:
    """One release-gate scenario for the visual-programming brain."""

    id: str
    intent: str
    expected_profile: str
    expected_ops: tuple[str, ...]
    target_root: str = "/project1"
    output_top: str | None = None
    validation_profile: str = "structural_visual_safe"
    tools: tuple[str, ...] = ("td_brain_plan", "td_brain_execute", "td_transaction_apply")
    requires_live_td: bool = True


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
            id="pop_particle_render",
            intent="Build a POP particle simulation with finite bounds and stable POP output.",
            expected_profile="pop",
            expected_ops=("circlePOP", "noisePOP", "nullPOP"),
        ),
        LiveSmokeScenario(
            id="glsl_shader_top",
            intent="Create a GLSL shader TOP with a source texture, shader source DAT, and output null.",
            expected_profile="glsl",
            expected_ops=("constantTOP", "glslTOP", "textDAT", "nullTOP"),
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
) -> dict[str, Any]:
    """Build a JSON-serializable smoke report.

    ``dry_run`` is deterministic and never touches TouchDesigner. ``live``
    connects to TD and plans against real operator/state data, but still does
    not mutate; transactional execution remains part of the MCP tools.
    """
    if mode not in {"dry_run", "live"}:
        raise ValueError("mode must be 'dry_run' or 'live'")

    started = time.perf_counter()
    scenarios = live_smoke_scenarios()
    client_to_close = None
    health: dict[str, Any] | None = None
    connection_error: str | None = None

    if mode == "live":
        client = td_client
        card_index = card_index or _load_default_card_index()
        if client is None:
            from td_mcp.td_client import TDClient  # Imported lazily for deterministic dry-run startup.

            client = TDClient(host=host, port=port, timeout=timeout, max_retries=0)
            client_to_close = client
        try:
            health = await client.health_check()
        except Exception as exc:  # noqa: BLE001
            connection_error = str(exc)
            if client_to_close is not None:
                await client_to_close.close()
            return _connection_failed_report(
                mode=mode,
                scenarios=scenarios,
                connection_error=connection_error,
                duration_ms=_elapsed_ms(started),
            )
    else:
        client = None

    try:
        scenario_reports = []
        for scenario in scenarios:
            scenario_client = client if mode == "live" else _static_client_for(scenario)
            scenario_reports.append(await _plan_scenario(scenario, scenario_client, card_index=card_index))
    finally:
        if client_to_close is not None:
            await client_to_close.close()

    ok = all(item["status"] == "planned" for item in scenario_reports)
    return {
        "schema_version": 1,
        "mode": mode,
        "ok": ok,
        "mutated_td": False,
        "scenario_count": len(scenario_reports),
        "duration_ms": _elapsed_ms(started),
        "td_health": health,
        "connection_error": connection_error,
        "scenarios": scenario_reports,
    }


def _static_client_for(scenario: LiveSmokeScenario) -> StaticEvalTDClient:
    return StaticEvalTDClient(families=families_for_ops(list(scenario.expected_ops)), nodes=[])


async def _plan_scenario(scenario: LiveSmokeScenario, td_client, *, card_index=None) -> dict[str, Any]:
    try:
        plan = await build_brain_plan(
            td_client,
            intent=scenario.intent,
            target_root=scenario.target_root,
            output_top=scenario.output_top,
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
            "status": "failed",
            "error": str(exc),
            "checks": checks_for_profile(scenario.validation_profile, scenario.expected_profile),
            "operators": list(scenario.expected_ops),
            "operation_count": 0,
            "blocked_questions": [],
            "missing_facts": [],
        }

    missing_expected = sorted(set(scenario.expected_ops) - set(plan.concept_graph.operators))
    status = "planned" if not plan.blocked_questions and not missing_expected else "blocked"
    return {
        "id": scenario.id,
        "intent": scenario.intent,
        "profile": plan.concept_graph.profile,
        "target_root": scenario.target_root,
        "output_top": scenario.output_top,
        "validation_profile": plan.validation_profile,
        "tools": list(scenario.tools),
        "requires_live_td": scenario.requires_live_td,
        "status": status,
        "plan_id": plan.id,
        "concept_graph_id": plan.concept_graph.id,
        "operators": plan.concept_graph.operators,
        "expected_ops": list(scenario.expected_ops),
        "missing_expected_ops": missing_expected,
        "operation_count": len(plan.patch_plan.operations),
        "blocked_questions": plan.blocked_questions,
        "missing_facts": plan.missing_facts,
        "risk_flags": plan.risk_flags,
        "checks": checks_for_profile(plan.validation_profile, plan.concept_graph.profile),
    }


def _connection_failed_report(
    *,
    mode: SmokeMode,
    scenarios: tuple[LiveSmokeScenario, ...],
    connection_error: str,
    duration_ms: float,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": mode,
        "ok": False,
        "mutated_td": False,
        "scenario_count": len(scenarios),
        "duration_ms": duration_ms,
        "td_health": None,
        "connection_error": connection_error,
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
                "status": "skipped_no_td",
                "operators": list(scenario.expected_ops),
                "checks": checks_for_profile(scenario.validation_profile, scenario.expected_profile),
                "blocked_questions": [],
                "missing_facts": ["TouchDesigner was not reachable for live smoke planning."],
            }
            for scenario in scenarios
        ],
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
