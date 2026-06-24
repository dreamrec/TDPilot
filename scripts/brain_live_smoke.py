#!/usr/bin/env python3
"""Run TDPilot brain live-smoke scenario planning."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from td_mcp.brain.live_smoke import build_live_smoke_report  # noqa: E402


def _load_incident_replay_module():
    path = ROOT / "scripts" / "replay_live_debug_incident.py"
    spec = importlib.util.spec_from_file_location("tdpilot_live_debug_incident_replay", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load incident replay module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run_incident_replay(args: argparse.Namespace) -> dict[str, Any]:
    module = _load_incident_replay_module()
    replay_args = argparse.Namespace(
        live=True,
        dry_run=False,
        target=args.incident_replay_target,
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        pretty=False,
    )
    return await module._build_report(replay_args)


def _incident_nested(report: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = report.get(key)
    if isinstance(value, dict):
        return value
    live_replay = report.get("live_replay")
    if isinstance(live_replay, dict):
        nested = live_replay.get(key)
        if isinstance(nested, dict):
            return nested
    return None


def _merge_visual_quality(
    existing: dict[str, Any] | None,
    incident_visual: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(existing, dict) or existing.get("status") == "not_run":
        return incident_visual or {
            "ok": False,
            "checked_count": 0,
            "failed_count": 1,
            "missing_count": 0,
            "status": "missing",
        }
    if not isinstance(incident_visual, dict):
        return existing
    return {
        **existing,
        "ok": bool(existing.get("ok")) and bool(incident_visual.get("ok")),
        "checked_count": int(existing.get("checked_count") or 0)
        + int(incident_visual.get("checked_count") or 0),
        "failed_count": int(existing.get("failed_count") or 0)
        + int(incident_visual.get("failed_count") or 0),
        "missing_count": int(existing.get("missing_count") or 0)
        + int(incident_visual.get("missing_count") or 0),
        "incident_replay": incident_visual,
    }


def _merge_incident_replay(report: dict[str, Any], incident_report: dict[str, Any]) -> dict[str, Any]:
    panel = _incident_nested(incident_report, "panel_interaction_results")
    visual = _incident_nested(incident_report, "visual_quality_summary")
    performance = _incident_nested(incident_report, "performance_summary")
    unresolved = incident_report.get("unresolved")
    if not isinstance(unresolved, list):
        unresolved = (
            incident_report.get("untriaged") if isinstance(incident_report.get("untriaged"), list) else []
        )
    live_replay = (
        incident_report.get("live_replay") if isinstance(incident_report.get("live_replay"), dict) else {}
    )
    live_sync = incident_report.get("live_sync") if isinstance(incident_report.get("live_sync"), dict) else {}
    panel_ok = bool(panel and panel.get("ok"))
    visual_ok = bool(visual and visual.get("ok"))
    sync_ok = bool(live_sync.get("ok", True))
    incident_ok = bool(incident_report.get("ok")) and panel_ok and visual_ok and sync_ok

    summary = {
        "ok": incident_ok,
        "mode": incident_report.get("mode"),
        "bug_count": incident_report.get("bug_count"),
        "untriaged": unresolved,
        "unresolved": unresolved,
        "group_counts": incident_report.get("group_counts"),
        "live_sync_ok": sync_ok,
        "target_root": live_replay.get("target_root"),
        "project_count": live_replay.get("project_count"),
        "grid_output": live_replay.get("grid_output"),
        "detail_output": live_replay.get("detail_output"),
        "panel_interaction_results": panel,
        "visual_quality_summary": visual,
        "performance_summary": performance,
    }
    report["incident_replay"] = summary
    if panel is not None:
        report["panel_interaction_results"] = panel
    if visual is not None:
        report["visual_quality_summary"] = _merge_visual_quality(report.get("visual_quality_summary"), visual)
    if performance is not None:
        report["incident_performance_summary"] = performance
    report["ok"] = bool(report.get("ok")) and incident_ok
    return report


async def _build_cli_report(args: argparse.Namespace) -> dict[str, Any]:
    mode = "live" if args.live else "dry_run"
    report = await build_live_smoke_report(
        mode=mode,
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        run_transactional_generated_code=args.transactional_generated_code,
    )
    if mode == "live" and args.transactional_generated_code and not args.skip_incident_replay:
        try:
            incident_report = await _run_incident_replay(args)
        except Exception as exc:  # noqa: BLE001 - CLI reports machine-readable failure.
            report["incident_replay"] = {
                "ok": False,
                "status": "failed",
                "error": str(exc),
                "bug_count": 0,
                "untriaged": ["incident_replay_failed"],
            }
            report["ok"] = False
        else:
            _merge_incident_replay(report, incident_report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="Use deterministic fake TD state; never connect or mutate."
    )
    mode.add_argument(
        "--live", action="store_true", help="Connect to TouchDesigner and plan against live state."
    )
    parser.add_argument("--host", default="127.0.0.1", help="TouchDesigner MCP host for --live.")
    parser.add_argument("--port", type=int, default=9981, help="TouchDesigner MCP port for --live.")
    parser.add_argument(
        "--timeout", type=float, default=15.0, help="TouchDesigner request timeout for --live."
    )
    parser.add_argument(
        "--transactional-generated-code",
        action="store_true",
        help="With --live, apply a tiny generated-code PatchPlan transactionally and undo it.",
    )
    parser.add_argument(
        "--incident-replay-target",
        default="/project1/tdpilot_incident_replay",
        help="Scratch root used by the live incident replay merged into transactional live smoke.",
    )
    parser.add_argument(
        "--skip-incident-replay",
        action="store_true",
        help="With --live --transactional-generated-code, skip the ten-output incident replay merge.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(_build_cli_report(args))
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
