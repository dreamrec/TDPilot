"""Optimizer + dynamics tools.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Tools in this module (2):
    td_optimize_visual   — bounded parameter search toward a goal
    td_describe_dynamics — async temporal observation (fps, cook, events)

Both tools use the async job-manager pattern (``_tr._get_job_manager``)
to run long-running loops off the request path. The optimizer also
threads in the snapshot manager for baseline capture + safety manager
for clamped parameter writes.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.capabilities import detect_capabilities
from td_mcp.errors import format_tool_error
from td_mcp.models import AdjustableParamInput, OptimizeVisualInput
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_optimize_visual")
async def td_optimize_visual(
    ctx: Context,
    goal: Annotated[
        str,
        Field(min_length=3, description="Natural-language optimization goal."),
    ],
    output_top: Annotated[
        str,
        Field(description="TOP path used as output reference."),
    ],
    adjustable_params: Annotated[
        list[AdjustableParamInput],
        Field(
            min_length=1,
            max_length=200,
            description=(
                "Parameter search space. Each entry specifies path/param/"
                "min_val/max_val/step for a parameter the optimizer may "
                "adjust."
            ),
        ),
    ],
    profile: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional optimizer profile: balanced | complexity | motion_rhythm | stability_guard"
            ),
        ),
    ] = None,
    objective_weights: Annotated[
        dict[str, float] | None,
        Field(
            default=None,
            description=(
                "Optional explicit objective weights, e.g. {'motion_rhythm': 0.8, 'stability': 0.4}."
            ),
        ),
    ] = None,
    max_iterations: Annotated[
        int,
        Field(default=10, ge=1, le=50, description="Max iterations."),
    ] = 10,
    convergence_threshold: Annotated[
        float,
        Field(default=0.8, ge=0.0, le=1.0, description="Convergence threshold."),
    ] = 0.8,
    safety_profile: Annotated[
        str,
        Field(
            default="balanced",
            description=("Optimizer safety profile: conservative | balanced | aggressive"),
        ),
    ] = "balanced",
    root_path: Annotated[
        str,
        Field(
            default="/project1",
            description="Root scope for instability checks and snapshots.",
        ),
    ] = "/project1",
    snapshot_before: Annotated[
        bool,
        Field(
            default=True,
            description="Capture snapshot before optimization loop starts.",
        ),
    ] = True,
) -> str:
    """Autonomous visual goal optimization via bounded parameter search."""
    # Re-instantiate so OptimizeVisualInput's @field_validator decorators on
    # ``safety_profile`` (conservative|balanced|aggressive) and ``profile``
    # (balanced|complexity|motion_rhythm|stability_guard) still run. Each
    # AdjustableParamInput also has a cross-field validator (max_val >= min_val).
    validated = OptimizeVisualInput(
        goal=goal,
        profile=profile,
        objective_weights=objective_weights,
        output_top=output_top,
        adjustable_params=adjustable_params,
        max_iterations=max_iterations,
        convergence_threshold=convergence_threshold,
        safety_profile=safety_profile,
        root_path=root_path,
        snapshot_before=snapshot_before,
    )

    finish = _tr._start_tool(ctx, "td_optimize_visual")
    try:
        client = _tr._get_client(ctx)
        safety = _tr._get_safety_manager(ctx)
        snapshots = _tr._get_snapshot_manager(ctx)
        jobs = _tr._get_job_manager(ctx)
        capabilities = detect_capabilities(ctx)

        # Build goal profile from explicit weights or sensible defaults.
        default_weights: dict[str, float] = {
            "brightness": 0.0,
            "contrast": 0.0,
            "stability": 0.4,
            "complexity": 0.3,
            "motion_rhythm": 0.0,
        }
        goal_profile: dict[str, float] = dict(default_weights)
        if validated.objective_weights:
            for key, value in validated.objective_weights.items():
                if key in goal_profile:
                    try:
                        goal_profile[key] = max(-1.0, min(1.0, float(value)))
                    except Exception:
                        continue

        baseline_snapshot_id: str | None = None
        snapshot_warning: str | None = None
        if validated.snapshot_before:
            try:
                snapshot_payload = await _tr._capture_snapshot_payload(
                    ctx,
                    path=validated.root_path,
                    include_visual=False,
                )
                saved = snapshots.add_snapshot(
                    snapshot_payload,
                    name=f"optimize_start_{validated.output_top.strip('/').replace('/', '_') or 'top'}",
                )
                baseline_snapshot_id = saved["snapshot_id"]
            except Exception as exc:
                snapshot_warning = str(exc)

        async def runner(job_id: str) -> dict[str, Any]:
            optimize_result = await _tr._run_optimizer_iterations(
                client=client,
                safety=safety,
                jobs=jobs,
                job_id=job_id,
                adjustable_params=validated.adjustable_params,
                goal_profile=goal_profile,
                max_iterations=validated.max_iterations,
                convergence_threshold=validated.convergence_threshold,
                safety_profile=validated.safety_profile,
                root_path=validated.root_path,
                phase_label="optimize_visual",
            )

            return {
                "schema_version": 1,
                "mode": "bounded_search",
                "sampling_supported": capabilities.supports_sampling,
                "goal": validated.goal,
                "goal_profile": goal_profile,
                "output_top": validated.output_top,
                "root_path": validated.root_path,
                "safety_profile": validated.safety_profile,
                "snapshot_before": validated.snapshot_before,
                "baseline_snapshot_id": baseline_snapshot_id,
                "snapshot_warning": snapshot_warning,
                "converged": optimize_result["converged"],
                "emergency_stop": optimize_result["emergency_stop"],
                "stop_reason": optimize_result["stop_reason"],
                "iterations_completed": optimize_result["iterations_completed"],
                "max_iterations": validated.max_iterations,
                "convergence_threshold": validated.convergence_threshold,
                "final_score": optimize_result["final_score"],
                "iterations": optimize_result["iterations"],
                "final_params": optimize_result["final_params"],
                "next": [
                    "Read td://job/{job_id} for incremental updates while running.",
                    "If results are unstable, use td_restore_snapshot with baseline_snapshot_id.",
                ],
            }

        job = jobs.start_async(
            description=f"Optimize visual goal: {validated.goal}",
            runner=runner,
        )

        _tr._audit_log(
            ctx,
            "td_optimize_visual",
            {
                "goal": validated.goal,
                "output_top": validated.output_top,
                "adjustable_count": len(validated.adjustable_params),
                "max_iterations": validated.max_iterations,
                "safety_profile": validated.safety_profile,
                "goal_profile": goal_profile,
                "baseline_snapshot_id": baseline_snapshot_id,
            },
        )

        payload = {
            "success": True,
            "job": job,
            "job_id": job["job_id"],
            "job_resource_uri": f"td://job/{job['job_id']}",
            "mode": "bounded_search",
            "sampling_supported": capabilities.supports_sampling,
            "baseline_snapshot_id": baseline_snapshot_id,
            "snapshot_warning": snapshot_warning,
            "goal_profile": goal_profile,
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_optimize_visual")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_describe_dynamics")
async def td_describe_dynamics(
    ctx: Context,
    path: Annotated[
        str,
        Field(default="/project1", description="Root path to observe."),
    ] = "/project1",
    observation_window: Annotated[
        float,
        Field(
            default=3.0,
            ge=0.5,
            le=30.0,
            description="Observation duration in seconds.",
        ),
    ] = 3.0,
    sample_rate: Annotated[
        float,
        Field(
            default=10.0,
            ge=1.0,
            le=60.0,
            description="Samples per second while observing.",
        ),
    ] = 10.0,
) -> str:
    """Asynchronous temporal dynamics observation (frame, cooking, events)."""
    finish = _tr._start_tool(ctx, "td_describe_dynamics")
    try:
        client = _tr._get_client(ctx)
        jobs = _tr._get_job_manager(ctx)
        event_manager = _tr._get_event_manager(ctx)

        sample_interval = max(1.0 / sample_rate, 0.01)
        target_samples = max(1, int(round(observation_window * sample_rate)))

        async def runner(job_id: str) -> dict[str, Any]:
            samples: list[dict[str, Any]] = []
            started = time.perf_counter()

            for index in range(target_samples):
                tick_started = time.perf_counter()

                timeline, cooking, errors = await asyncio.gather(
                    _tr._safe_request(client, "timeline"),
                    _tr._safe_request(
                        client,
                        "cooking",
                        {"path": path, "recurse": True, "limit": 20, "sort_by": "cookTime"},
                    ),
                    _tr._safe_request(
                        client,
                        "node/errors",
                        {"path": path, "recurse": True, "max_depth": 10},
                    ),
                )

                heavy_nodes = [
                    node
                    for node in (cooking.get("nodes", []) if isinstance(cooking, dict) else [])
                    if isinstance(node, dict) and float(node.get("cookTime", 0.0) or 0.0) >= 0.01
                ]
                issues = errors.get("issues", []) if isinstance(errors, dict) else []
                recent_events = event_manager.get_recent_events(limit=200)

                sample = {
                    "index": index + 1,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "frame": int(timeline.get("frame", 0) or 0) if isinstance(timeline, dict) else 0,
                    "seconds": float(timeline.get("seconds", 0.0) or 0.0)
                    if isinstance(timeline, dict)
                    else 0.0,
                    "playing": bool(timeline.get("playing", False)) if isinstance(timeline, dict) else False,
                    "fps": float(cooking.get("fps", 0.0) or 0.0) if isinstance(cooking, dict) else 0.0,
                    "issues_count": len(issues),
                    "heavy_nodes_count": len(heavy_nodes),
                    "event_rate": _tr._event_rate_per_sec(recent_events),
                }
                samples.append(sample)

                jobs.update_job(
                    job_id,
                    progress=float(index + 1) / float(target_samples),
                    result={
                        "latest_sample": sample,
                        "samples_collected": index + 1,
                        "target_samples": target_samples,
                    },
                )

                elapsed_tick = time.perf_counter() - tick_started
                await asyncio.sleep(max(0.0, sample_interval - elapsed_tick))

            elapsed = time.perf_counter() - started
            classifications = _tr._classify_temporal_character(samples)

            return {
                "schema_version": 1,
                "path": path,
                "observation": {
                    "duration_sec": elapsed,
                    "requested_window_sec": observation_window,
                    "sample_rate": sample_rate,
                    "samples": len(samples),
                    "fps_during_mean": classifications.get("fps_mean", 0.0),
                },
                "samples": samples,
                "classifications": classifications,
                "notes": [
                    "Current classifier is heuristic and intended for fast diagnostics.",
                    "Use td_get_state_vector alongside this report for broader context.",
                ],
            }

        job = jobs.start_async(
            description=f"Describe dynamics for {path}",
            runner=runner,
        )

        _tr._audit_log(
            ctx,
            "td_describe_dynamics",
            {
                "path": path,
                "observation_window": observation_window,
                "sample_rate": sample_rate,
            },
        )

        payload = {
            "success": True,
            "job": job,
            "job_id": job["job_id"],
            "job_resource_uri": f"td://job/{job['job_id']}",
            "path": path,
            "observation_window": observation_window,
            "sample_rate": sample_rate,
            "target_samples": target_samples,
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_describe_dynamics")
        return format_tool_error(exc)
    finally:
        finish()
