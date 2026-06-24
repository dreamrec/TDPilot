#!/usr/bin/env python3
"""Replay the June 24 live-debug incident ledger.

Dry-run mode is intentionally deterministic and local-only. Live mode also
builds a scratch ten-output library in TouchDesigner, validates real pixels for
project/grid/detail outputs, invokes panel-style callbacks, and reports the
readback evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

LEDGER = ROOT / "tests" / "fixtures" / "td_live_debug_incident_2026_06_24.json"
PROJECT_COUNT = 10


def _load_ledger() -> dict[str, Any]:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _group_counts(bugs: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for bug in bugs:
        group = str(bug.get("group") or "unknown")
        counts[group] = counts.get(group, 0) + 1
    return dict(sorted(counts.items()))


def _representative_checks() -> dict[str, dict[str, str]]:
    return {
        "visual_black_frame": {
            "status": "covered",
            "bugs": "BUG-019,BUG-043,BUG-044",
            "evidence": "visual quality metrics fail black, transparent, flat, and missing frame outputs",
        },
        "panel_callback_wiring": {
            "status": "covered",
            "bugs": "BUG-040,BUG-041,BUG-042",
            "evidence": "panel validation checks callback module source and switch-index readbacks",
        },
        "sync_drift": {
            "status": "covered",
            "bugs": "BUG-002,BUG-003,BUG-010,BUG-018,BUG-021,BUG-023,BUG-045",
            "evidence": "sync diagnostics compare local, installed, running, component, and auth fingerprints",
        },
        "macro_truthfulness": {
            "status": "covered",
            "bugs": "BUG-007,BUG-008,BUG-011",
            "evidence": "macro preview counts macro ops, macro apply returns child paths, and feedback macros avoid invalid input wiring",
        },
        "rollback_readback": {
            "status": "covered",
            "bugs": "BUG-012,BUG-013,BUG-014,BUG-022",
            "evidence": "transaction rollback verifies params, expressions, created paths, and connections by live readback",
        },
        "operator_param_semantics": {
            "status": "covered",
            "bugs": "BUG-017,BUG-025,BUG-029,BUG-032,BUG-033,BUG-034,BUG-035,BUG-038",
            "evidence": "operator creation and parameter readback/semantics regressions cover menu coercion, references, TOP params, and inspection failures",
        },
    }


async def _live_probe(args: argparse.Namespace) -> dict[str, Any]:
    from td_mcp.auth_bootstrap import bootstrap_auth, default_env_file
    from td_mcp.sync_diagnostics import diagnose_sync
    from td_mcp.td_client import TDClient

    env_file = default_env_file()
    bootstrap_auth(env_file)
    client = TDClient(host=args.host, port=args.port, timeout=args.timeout)
    try:
        return await diagnose_sync(client=client, host=args.host, port=args.port, include_live=True)
    finally:
        await client.close()


def _parent_and_name(path: str) -> tuple[str, str]:
    normalized = "/" + path.strip("/")
    parent, _, name = normalized.rpartition("/")
    return parent or "/", name


async def _checked_request(client, endpoint: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = await client.request(endpoint, body or {})
    if not isinstance(payload, dict):
        return {"value": payload}
    if payload.get("error"):
        raise RuntimeError(f"{endpoint} failed: {payload['error']}")
    return payload


async def _create_node(
    client,
    *,
    parent: str,
    op_type: str,
    name: str,
    x: int,
    y: int,
) -> str:
    payload = await _checked_request(
        client,
        "node/create",
        {
            "parent_path": parent,
            "node_type": op_type,
            "name": name,
            "nodeX": x,
            "nodeY": y,
        },
    )
    node = payload.get("node") if isinstance(payload, dict) else None
    path = node.get("path") if isinstance(node, dict) else payload.get("path")
    if not path:
        raise RuntimeError(f"node/create returned no path for {parent}/{name}")
    return str(path)


async def _set_params(client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    payload = await _checked_request(client, "node/params/set", {"path": path, "params": params})
    results = payload.get("results")
    if isinstance(results, dict):
        failed = {
            name: result
            for name, result in results.items()
            if isinstance(result, dict) and result.get("success") is False
        }
        if failed:
            raise RuntimeError(f"node/params/set failed for {path}: {failed}")
    return payload


async def _set_text(client, path: str, text: str) -> None:
    await _checked_request(client, "node/content/set", {"path": path, "text": text})


async def _set_table(client, path: str, table: list[list[Any]]) -> None:
    await _checked_request(client, "node/content/set", {"path": path, "table": table})


async def _connect(client, source: str, target: str, *, to_input: int = 0) -> None:
    await _checked_request(
        client,
        "node/connect",
        {
            "source_path": source,
            "target_path": target,
            "source_index": 0,
            "target_index": to_input,
        },
    )


def _project_shader_source(index: int) -> str:
    seed = index + 1
    warm = 0.08 + (index % 5) * 0.035
    cool = 0.18 + (index % 3) * 0.05
    return (
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
        f"    float wave = 0.5 + 0.5 * sin((uv.x * {9 + seed}.0 + uv.y * {13 + seed}.0) * 6.2831853);\n"
        f"    float cells = hash21(floor(uv * {10 + seed}.0 + vec2({seed}.0, {seed * 3}.0)));\n"
        "    float rings = 0.5 + 0.5 * sin(length(uv - vec2(0.5)) * 54.0);\n"
        f"    vec3 a = vec3({warm:.3f}, {0.16 + index * 0.015:.3f}, {0.42 + cool:.3f});\n"
        f"    vec3 b = vec3({0.78 - index * 0.022:.3f}, {0.42 + index * 0.025:.3f}, {0.18 + index * 0.018:.3f});\n"
        "    vec3 color = mix(a, b, wave * 0.7 + rings * 0.3);\n"
        "    color += vec3(cells * 0.22, hash21(uv * 31.0) * 0.12, rings * 0.08);\n"
        "    fragColor = TDOutputSwizzle(vec4(clamp(color, 0.0, 1.0), 1.0));\n"
        "}\n"
    )


def _grid_shader_source(count: int = PROJECT_COUNT) -> str:
    return (
        "layout(location = 0) out vec4 fragColor;\n"
        "float hash21(vec2 p)\n"
        "{\n"
        "    p = fract(p * vec2(123.34, 456.21));\n"
        "    p += dot(p, p + 45.32);\n"
        "    return fract(p.x * p.y);\n"
        "}\n"
        "vec3 thumbColor(int idx, vec2 uv)\n"
        "{\n"
        "    float fi = float(idx + 1);\n"
        "    float wave = 0.5 + 0.5 * sin((uv.x * (8.0 + fi) + uv.y * (13.0 + fi)) * 6.2831853);\n"
        "    float cells = hash21(floor(uv * (8.0 + fi)) + vec2(fi, fi * 3.0));\n"
        "    vec3 a = vec3(0.05 + fi * 0.025, 0.14 + fi * 0.015, 0.54 - fi * 0.018);\n"
        "    vec3 b = vec3(0.88 - fi * 0.026, 0.28 + fi * 0.044, 0.16 + fi * 0.021);\n"
        "    return clamp(mix(a, b, wave) + vec3(cells * 0.18), 0.0, 1.0);\n"
        "}\n"
        "void main()\n"
        "{\n"
        "    vec2 uv = vUV.st;\n"
        "    vec2 grid = vec2(5.0, 2.0);\n"
        "    vec2 cell = vec2(uv.x * grid.x, (1.0 - uv.y) * grid.y);\n"
        "    ivec2 ij = ivec2(floor(cell));\n"
        "    int idx = ij.y * 5 + ij.x;\n"
        "    vec2 tuv = fract(cell);\n"
        "    vec3 thumb = thumbColor(idx, tuv);\n"
        "    float border = step(tuv.x, 0.025) + step(tuv.y, 0.025) + step(0.975, tuv.x) + step(0.975, tuv.y);\n"
        "    vec3 ink = mix(thumb, vec3(0.96, 0.94, 0.82), clamp(border, 0.0, 1.0) * 0.55);\n"
        "    if (idx >= 10) ink = vec3(0.015, 0.018, 0.024);\n"
        "    fragColor = TDOutputSwizzle(vec4(ink, 1.0));\n"
        "}\n"
    )


def _callback_source(root: str) -> str:
    return (
        f"ROOT = {root!r}\n"
        "COUNT = 10\n\n"
        "def _write(mode, index):\n"
        "    index = max(0, min(COUNT - 1, int(index)))\n"
        "    state = op(ROOT + '/library_state')\n"
        "    state.clear()\n"
        "    state.appendRow(['mode', 'index'])\n"
        "    state.appendRow([mode, str(index)])\n"
        "    op(ROOT + '/detail_switch').par.index = index\n"
        "    op(ROOT + '/display_switch').par.index = 0 if mode == 'grid' else 1\n"
        "    return {'mode': mode, 'index': index}\n\n"
        "def _current_index():\n"
        "    state = op(ROOT + '/library_state')\n"
        "    try:\n"
        "        return int(state[1, 'index'])\n"
        "    except Exception:\n"
        "        return 0\n\n"
        "def reset():\n"
        "    return _write('grid', 0)\n\n"
        "def thumb(index=0):\n"
        "    return _write('detail', index)\n\n"
        "def next():\n"
        "    return _write('detail', _current_index() + 1)\n\n"
        "def prev():\n"
        "    return _write('detail', _current_index() - 1)\n\n"
        "def back():\n"
        "    return _write('grid', _current_index())\n"
    )


async def _build_ten_output_library(client, target: str) -> dict[str, Any]:
    parent, name = _parent_and_name(target)
    try:
        await client.request("node/delete", {"path": target})
    except Exception:
        pass
    root = await _create_node(client, parent=parent, op_type="baseCOMP", name=name, x=0, y=-700)

    outputs: list[str] = []
    for index in range(PROJECT_COUNT):
        y = -index * 160
        prefix = f"project_{index + 1:02d}"
        shader_dat = await _create_node(
            client, parent=root, op_type="textDAT", name=f"{prefix}_shader", x=0, y=y
        )
        glsl = await _create_node(
            client, parent=root, op_type="glslTOP", name=f"{prefix}_glsl", x=200, y=y
        )
        out = await _create_node(
            client, parent=root, op_type="nullTOP", name=f"{prefix}_out", x=420, y=y
        )
        await _set_text(client, shader_dat, _project_shader_source(index))
        await _set_params(
            client,
            glsl,
            {
                "pixeldat": shader_dat,
                "outputresolution": "custom",
                "resolutionw": 512,
                "resolutionh": 512,
            },
        )
        await _connect(client, glsl, out)
        outputs.append(out)

    grid_shader = await _create_node(
        client, parent=root, op_type="textDAT", name="library_grid_shader", x=720, y=40
    )
    grid = await _create_node(client, parent=root, op_type="glslTOP", name="library_grid", x=940, y=40)
    await _set_text(client, grid_shader, _grid_shader_source())
    await _set_params(
        client,
        grid,
        {
            "pixeldat": grid_shader,
            "outputresolution": "custom",
            "resolutionw": 1280,
            "resolutionh": 720,
        },
    )
    detail_switch = await _create_node(
        client, parent=root, op_type="switchTOP", name="detail_switch", x=720, y=-280
    )
    detail_out = await _create_node(
        client, parent=root, op_type="nullTOP", name="detail_output", x=940, y=-280
    )
    for index, output in enumerate(outputs):
        await _connect(client, output, detail_switch, to_input=index)
    await _set_params(client, detail_switch, {"index": 0})
    await _connect(client, detail_switch, detail_out)

    display_switch = await _create_node(
        client, parent=root, op_type="switchTOP", name="display_switch", x=1160, y=-120
    )
    display = await _create_node(
        client, parent=root, op_type="nullTOP", name="library_display", x=1380, y=-120
    )
    await _connect(client, grid, display_switch, to_input=0)
    await _connect(client, detail_out, display_switch, to_input=1)
    await _set_params(client, display_switch, {"index": 0})
    await _connect(client, display_switch, display)

    state = await _create_node(client, parent=root, op_type="tableDAT", name="library_state", x=720, y=-520)
    callbacks = await _create_node(
        client, parent=root, op_type="textDAT", name="library_callbacks", x=940, y=-520
    )
    await _set_table(client, state, [["mode", "index"], ["grid", "0"]])
    await _set_text(client, callbacks, _callback_source(root))

    return {
        "root": root,
        "project_outputs": outputs,
        "grid": grid,
        "detail_output": detail_out,
        "display": display,
        "state": state,
        "callbacks": callbacks,
        "detail_switch": detail_switch,
        "display_switch": display_switch,
    }


def _quality_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    quality = payload.get("quality")
    if isinstance(quality, dict):
        return quality
    return {
        "pass": False,
        "missing": True,
        "fail_reasons": ["quality_payload_missing"],
    }


async def _visual_quality_checks(client, paths: list[str]) -> dict[str, Any]:
    by_path: dict[str, Any] = {}
    for path in paths:
        try:
            payload = await _checked_request(
                client,
                "analyze_frame",
                {
                    "path": path,
                    "modes": ["luminance", "alpha_coverage"],
                    "quality_mode": True,
                },
            )
            by_path[path] = _quality_from_payload(payload)
        except Exception as exc:  # noqa: BLE001
            by_path[path] = {
                "pass": False,
                "missing": True,
                "fail_reasons": [str(exc)],
            }
    failed = [path for path, quality in by_path.items() if not isinstance(quality, dict) or quality.get("pass") is not True]
    missing = [path for path, quality in by_path.items() if isinstance(quality, dict) and quality.get("missing") is True]
    return {
        "ok": not failed,
        "checked_count": len(by_path),
        "failed_count": len(failed),
        "missing_count": len(missing),
        "paths": sorted(by_path),
        "failed_paths": sorted(failed),
        "qualities": by_path,
    }


async def _panel_interaction_checks(client, built: dict[str, Any]) -> dict[str, Any]:
    code = (
        f"cb = op({built['callbacks']!r}).module\n"
        f"state = op({built['state']!r})\n"
        f"detail = op({built['detail_switch']!r})\n"
        f"display = op({built['display_switch']!r})\n"
        "present = {name: hasattr(cb, name) for name in ['reset', 'thumb', 'next', 'prev', 'back']}\n"
        "steps = []\n"
        "steps.append(['reset', cb.reset()])\n"
        "steps.append(['thumb', cb.thumb(4)])\n"
        "steps.append(['next', cb.next()])\n"
        "steps.append(['prev', cb.prev()])\n"
        "steps.append(['back', cb.back()])\n"
        "rows = []\n"
        "for r in range(state.numRows):\n"
        "    row = []\n"
        "    for c in range(state.numCols):\n"
        "        row.append(state[r, c].val)\n"
        "    rows.append(row)\n"
        "__result__ = {\n"
        "    'present': present,\n"
        "    'steps': steps,\n"
        "    'state_rows': rows,\n"
        "    'detail_index': int(detail.par.index.eval()),\n"
        "    'display_index': int(display.par.index.eval()),\n"
        "}\n"
    )
    payload = await _checked_request(client, "exec", {"code": code, "exec_mode": "restricted", "timeout_ms": 5000})
    result = payload.get("result")
    if not isinstance(result, dict):
        return {
            "ok": False,
            "checked_count": 0,
            "failed_count": 1,
            "status": "failed",
            "error": "exec result missing panel interaction payload",
            "raw": payload,
        }
    present = result.get("present") if isinstance(result, dict) else {}
    all_present = isinstance(present, dict) and all(present.get(name) is True for name in ["reset", "thumb", "next", "prev", "back"])
    detail_index = result.get("detail_index")
    display_index = result.get("display_index")
    final_state_ok = detail_index == 4 and display_index == 0
    ok = bool(all_present and final_state_ok)
    return {
        "ok": ok,
        "checked_count": 5,
        "failed_count": 0 if ok else 1,
        "status": "checked",
        "present": present,
        "steps": result.get("steps"),
        "state_rows": result.get("state_rows"),
        "detail_index": detail_index,
        "display_index": display_index,
    }


async def _performance_check(client, target: str) -> dict[str, Any]:
    payload = await _checked_request(client, "cooking", {"path": target})
    nodes = payload.get("nodes") if isinstance(payload, dict) else []
    cook_values: list[float] = []
    if isinstance(nodes, list):
        for item in nodes:
            if not isinstance(item, dict):
                continue
            for key in ("cookTime", "cook_time_ms", "cook_ms", "total_cook_ms"):
                value = item.get(key)
                if isinstance(value, (int, float)):
                    cook_values.append(float(value))
                    break
    max_ms = max(cook_values) if cook_values else 0.0
    return {
        "ok": max_ms <= 16.667,
        "steady_state_max_ms": max_ms,
        "frame_budget_ms": 16.667,
        "sample_count": len(cook_values),
    }


async def _run_live_scratch_replay(client, target: str) -> dict[str, Any]:
    built = await _build_ten_output_library(client, target)
    grid_quality = await _visual_quality_checks(client, [built["grid"]])
    panel = await _panel_interaction_checks(client, built)
    detail_quality = await _visual_quality_checks(client, [built["display"]])
    project_quality = await _visual_quality_checks(client, list(built["project_outputs"]))
    visual = {
        "ok": grid_quality["ok"] and detail_quality["ok"] and project_quality["ok"],
        "grid_mode": grid_quality,
        "detail_mode": detail_quality,
        "project_outputs": project_quality,
        "checked_count": (
            grid_quality["checked_count"]
            + detail_quality["checked_count"]
            + project_quality["checked_count"]
        ),
        "failed_count": (
            grid_quality["failed_count"]
            + detail_quality["failed_count"]
            + project_quality["failed_count"]
        ),
        "missing_count": (
            grid_quality["missing_count"]
            + detail_quality["missing_count"]
            + project_quality["missing_count"]
        ),
    }
    performance = await _performance_check(client, built["root"])
    return {
        "ok": bool(visual["ok"] and panel["ok"] and performance["ok"]),
        "target_root": built["root"],
        "project_count": PROJECT_COUNT,
        "project_outputs": built["project_outputs"],
        "grid_output": built["grid"],
        "detail_output": built["display"],
        "visual_quality_summary": visual,
        "panel_interaction_results": panel,
        "performance_summary": performance,
        "note": "Scratch replay root is left in TouchDesigner for manual inspection.",
    }


async def _build_report(args: argparse.Namespace) -> dict[str, Any]:
    ledger = _load_ledger()
    bugs = list(ledger["bugs"])
    unresolved = [
        bug["id"]
        for bug in bugs
        if bug.get("resolution") in {"untriaged", "documented_open"}
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "mode": "live" if args.live else "dry_run",
        "ok": not unresolved,
        "source_report": ledger["source_report"],
        "bug_count": len(bugs),
        "unresolved": unresolved,
        "group_counts": _group_counts(bugs),
        "representative_checks": _representative_checks(),
    }
    if args.live:
        try:
            from td_mcp.auth_bootstrap import bootstrap_auth, default_env_file
            from td_mcp.sync_diagnostics import diagnose_sync
            from td_mcp.td_client import TDClient

            env_file = default_env_file()
            bootstrap_auth(env_file)
            client = TDClient(host=args.host, port=args.port, timeout=args.timeout)
            try:
                sync = await diagnose_sync(client=client, host=args.host, port=args.port, include_live=True)
                report["live_sync"] = sync
                report["ok"] = report["ok"] and bool(sync.get("ok"))
                if sync.get("ok"):
                    live_replay = await _run_live_scratch_replay(client, args.target)
                    report["live_replay"] = live_replay
                    report["visual_quality_summary"] = live_replay["visual_quality_summary"]
                    report["panel_interaction_results"] = live_replay["panel_interaction_results"]
                    report["performance_summary"] = live_replay["performance_summary"]
                    report["ok"] = report["ok"] and bool(live_replay.get("ok"))
            finally:
                await client.close()
        except Exception as exc:  # noqa: BLE001
            report["ok"] = False
            report["live_error"] = str(exc)
            report["remediation"] = (
                "Run scripts/diagnose_live_sync.py --live --pretty and restart TouchDesigner/MCP "
                "if auth or version fingerprints differ."
            )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Use ledger-only deterministic replay.")
    mode.add_argument("--live", action="store_true", help="Probe live TD/MCP sync in addition to ledger checks.")
    parser.add_argument("--target", default="/project1/tdpilot_incident_replay")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9981)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.live:
        args.dry_run = True
    report = asyncio.run(_build_report(args))
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
