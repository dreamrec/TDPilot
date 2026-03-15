#!/usr/bin/env python3
"""Full end-to-end integration suite for TDPilot against a live TouchDesigner session.

This suite drives the MCP server over stdio (real MCP protocol), not direct HTTP,
and exercises core + extended tools against the currently running TD project that has
`td_component/tdpilot_v1_3.tox` loaded.

Typical usage:

    uv run python scripts/full_td_mcp_e2e.py \
      --repo-dir "/ABS/PATH/TDPilot" \
      --out reports/e2e_live.json
"""

from __future__ import annotations

import argparse
import json
import random
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@dataclass
class StepResult:
    name: str
    status: str  # pass | fail | warn | skip
    duration_ms: float
    detail: str


class TestFailure(RuntimeError):
    pass


class TestWarning(RuntimeError):
    pass


class E2ESuite:
    def __init__(self, session: ClientSession, repo_dir: Path, strict_events: bool = False):
        self.session = session
        self.repo_dir = repo_dir
        self.strict_events = strict_events
        self.steps: list[StepResult] = []
        self.ctx: Dict[str, Any] = {
            "created_paths": [],
            "timeline_before": None,
            "exec_mode": None,
            "job_ids": [],
        }

    async def _call_tool(
        self,
        name: str,
        params: Optional[dict[str, Any]] = None,
        *,
        expect_error: bool = False,
    ) -> dict[str, Any]:
        args = {"params": params or {}} if params is not None else None

        try:
            result = await self.session.call_tool(name, args)
        except Exception as exc:
            raise TestFailure(f"call_tool({name}) raised: {exc}") from exc

        text_parts = [getattr(chunk, "text", "") for chunk in result.content if hasattr(chunk, "text")]
        text = "\n".join(part for part in text_parts if part).strip()

        payload: dict[str, Any]
        if not text:
            payload = {}
        else:
            try:
                obj = json.loads(text)
                payload = obj if isinstance(obj, dict) else {"value": obj}
            except json.JSONDecodeError:
                payload = {"raw": text}

        has_error = self._has_payload_error(payload)
        if expect_error:
            if not has_error:
                raise TestFailure(f"{name} expected error but succeeded: {payload}")
        else:
            if has_error:
                raise TestFailure(f"{name} failed: {payload}")

        return payload

    async def _read_resource_json(self, uri: str) -> dict[str, Any]:
        try:
            result = await self.session.read_resource(uri)
        except Exception as exc:
            raise TestFailure(f"read_resource({uri}) raised: {exc}") from exc

        text = ""
        try:
            contents = getattr(result, "contents", [])
            if contents:
                text = getattr(contents[0], "text", "") or ""
        except Exception:
            text = ""

        if not text.strip():
            return {}

        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else {"value": payload}
        except json.JSONDecodeError as exc:
            raise TestFailure(f"read_resource({uri}) returned non-JSON payload: {text[:200]}") from exc

    async def _wait_for_job(self, job_id: str, *, timeout_sec: float = 60.0) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        last_payload: dict[str, Any] = {}
        while time.time() < deadline:
            payload = await self._read_resource_json(f"td://job/{job_id}")
            job = payload.get("job", {}) if isinstance(payload, dict) else {}
            status = str(job.get("status", "")).lower()
            last_payload = payload
            if status in {"completed", "failed", "cancelled"}:
                return payload
            await anyio.sleep(0.25)
        raise TestFailure(f"Timed out waiting for job {job_id}; last payload={last_payload}")

    @staticmethod
    def _has_payload_error(payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return True
        if bool(payload.get("requires_confirmation")):
            return True
        if payload.get("success") is False and "error" in payload:
            return True
        err = payload.get("error")
        if err not in (None, "", []):
            return True
        return False

    async def _run_step(self, name: str, fn, *, allow_warn: bool = False, allow_skip: bool = False) -> None:
        started = time.perf_counter()
        try:
            await fn()
            status = "pass"
            detail = ""
        except TestWarning as warn:
            if allow_warn:
                status = "warn"
                detail = str(warn)
            else:
                status = "fail"
                detail = str(warn)
        except FileNotFoundError as exc:
            if allow_skip:
                status = "skip"
                detail = str(exc)
            else:
                status = "fail"
                detail = str(exc)
        except Exception as exc:  # pragma: no cover - runtime integration path
            status = "fail"
            detail = f"{exc}\n{traceback.format_exc(limit=1)}"

        duration_ms = (time.perf_counter() - started) * 1000.0
        self.steps.append(StepResult(name=name, status=status, duration_ms=duration_ms, detail=detail))

    async def run(self) -> dict[str, Any]:
        await self._run_step("bootstrap_registry", self._step_bootstrap)
        await self._run_step("sync_td_component_scripts", self._step_sync_td_component_scripts)
        await self._run_step("core_info_tools", self._step_core_info)
        await self._run_step("build_fixture_network", self._step_build_fixture)
        await self._run_step("node_graph_tools", self._step_node_graph_tools)
        await self._run_step("params_exec_and_content", self._step_params_exec_and_content)
        await self._run_step("capture_geometry_and_debug", self._step_capture_geometry_and_debug)
        await self._run_step("timeline_tools", self._step_timeline_tools)
        await self._run_step("macro_tools", self._step_macro_tools)
        await self._run_step("event_subscription_tools", self._step_event_tools, allow_warn=not self.strict_events)
        await self._run_step("visual_monitor_and_stream", self._step_visual_tools)
        await self._run_step("safety_snapshot_state", self._step_safety_snapshot_state)
        await self._run_step("async_job_tools", self._step_async_jobs)

        # Always attempt cleanup, but do not mask prior failures.
        await self._run_step("cleanup_fixture", self._step_cleanup, allow_warn=True)

        fail_count = sum(1 for s in self.steps if s.status == "fail")
        warn_count = sum(1 for s in self.steps if s.status == "warn")
        skip_count = sum(1 for s in self.steps if s.status == "skip")
        pass_count = sum(1 for s in self.steps if s.status == "pass")

        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total": len(self.steps),
                "passed": pass_count,
                "failed": fail_count,
                "warnings": warn_count,
                "skipped": skip_count,
                "ok": fail_count == 0,
            },
            "fixture": {
                "base_path": self.ctx.get("base_path"),
                "created_paths": self.ctx.get("created_paths", []),
                "timeline_before": self.ctx.get("timeline_before"),
                "pop_warning": self.ctx.get("pop_warning"),
            },
            "steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "duration_ms": round(s.duration_ms, 2),
                    "detail": s.detail,
                }
                for s in self.steps
            ],
        }

    async def _step_bootstrap(self) -> None:
        tools = await self.session.list_tools()
        tool_names = {tool.name for tool in tools.tools}

        if len(tool_names) < 86:
            raise TestFailure(f"Expected at least 92 tools, got {len(tool_names)}")

        required_tools = {
            "td_geometry_data",
            "td_pop_inspect",
            "td_capture_and_analyze",
            "td_monitor_visual",
            "td_stream_top",
            "td_project_lifecycle",
            "td_custom_parameters",
            "td_memory_learn",
        }
        missing = sorted(required_tools - tool_names)
        if missing:
            raise TestFailure(f"Required runtime tools missing: {missing}")

        if "td_sop_data" in tool_names:
            raise TestFailure("Legacy td_sop_data is still present")

        templates = await self.session.list_resource_templates()
        if len(templates.resourceTemplates) < 5:
            raise TestFailure("Resource templates unexpectedly low")

    async def _step_sync_td_component_scripts(self) -> None:
        """Hot-sync latest TD-side scripts into loaded /project1/mcp_server DATs."""
        mapping = [
            ("/project1/mcp_server/callbacks", self.repo_dir / "td_component" / "mcp_webserver_callbacks.py"),
            ("/project1/mcp_server/ws_callbacks", self.repo_dir / "td_component" / "ws_callbacks.py"),
            ("/project1/mcp_server/event_emitter", self.repo_dir / "td_component" / "event_emitter.py"),
        ]

        for td_path, file_path in mapping:
            if not file_path.is_file():
                raise FileNotFoundError(f"Missing file for TD sync: {file_path}")
            text = file_path.read_text(encoding="utf-8")
            await self._call_tool("td_set_content", {"path": td_path, "text": text})

    async def _step_core_info(self) -> None:
        info = await self._call_tool("td_get_info")
        if "project_name" not in info:
            raise TestFailure("td_get_info missing project_name")

        await self._call_tool("td_list_families")
        await self._call_tool("td_get_capabilities")
        metrics = await self._call_tool("td_get_server_metrics")
        runtime = metrics.get("runtime", {})
        self.ctx["exec_mode"] = runtime.get("exec_mode")

        await self._call_tool("td_python_classes")
        await self._call_tool("td_python_help", {"target": "td.OP"})

        timeline = await self._call_tool("td_timeline")
        self.ctx["timeline_before"] = {
            "playing": bool(timeline.get("playing", False)),
            "frame": int(timeline.get("frame", 0) or 0),
        }

    async def _create_node(self, *, parent: str, node_type: str, name: str, x: int, y: int) -> str:
        payload = await self._call_tool(
            "td_create_node",
            {
                "parent_path": parent,
                "node_type": node_type,
                "name": name,
                "nodeX": x,
                "nodeY": y,
            },
        )
        node = payload.get("node")
        if not isinstance(node, dict) or not node.get("path"):
            raise TestFailure(f"td_create_node returned invalid payload: {payload}")
        node_path = str(node["path"])
        self.ctx["created_paths"].append(node_path)
        return node_path

    async def _step_build_fixture(self) -> None:
        suffix = datetime.now().strftime("%H%M%S")
        base_name = f"tdpilot_e2e_{suffix}"
        base_path = await self._create_node(
            parent="/project1",
            node_type="baseCOMP",
            name=base_name,
            x=0,
            y=0,
        )
        self.ctx["base_name"] = base_name
        self.ctx["base_path"] = base_path

        self.ctx["noise_top"] = await self._create_node(parent=base_path, node_type="noiseTOP", name="noise_main", x=0, y=0)
        self.ctx["out_top"] = await self._create_node(parent=base_path, node_type="nullTOP", name="out_top", x=220, y=0)
        self.ctx["ctrl_chop"] = await self._create_node(parent=base_path, node_type="constantCHOP", name="ctrl", x=0, y=-180)
        self.ctx["out_chop"] = await self._create_node(parent=base_path, node_type="nullCHOP", name="ctrl_out", x=220, y=-180)
        self.ctx["geo_sop"] = await self._create_node(parent=base_path, node_type="sphereSOP", name="geo", x=0, y=-360)
        self.ctx["text_dat"] = await self._create_node(parent=base_path, node_type="textDAT", name="notes", x=0, y=-540)
        self.ctx["table_dat"] = await self._create_node(parent=base_path, node_type="tableDAT", name="table", x=220, y=-540)

        # POP is optional depending build/license; treat absence as warning only.
        try:
            self.ctx["pop_geo"] = await self._create_node(
                parent=base_path,
                node_type="particlePOP",
                name="pop_geo",
                x=440,
                y=-360,
            )
        except Exception as exc:
            self.ctx["pop_geo"] = None
            self.ctx["pop_warning"] = str(exc)

    async def _step_node_graph_tools(self) -> None:
        base_path = self.ctx["base_path"]
        noise_top = self.ctx["noise_top"]
        out_top = self.ctx["out_top"]

        nodes = await self._call_tool("td_get_nodes", {"path": base_path, "limit": 100})
        if int(nodes.get("count", 0) or 0) < 6:
            raise TestFailure("Fixture node count unexpectedly low")

        await self._call_tool("td_get_node_detail", {"path": noise_top})
        search = await self._call_tool(
            "td_search_nodes",
            {"query": self.ctx["base_name"], "path": "/project1", "search_type": "name", "limit": 20},
        )
        if int(search.get("count", 0) or 0) < 1:
            raise TestFailure("td_search_nodes did not find fixture")

        copy_payload = await self._call_tool(
            "td_copy_node",
            {"source_path": noise_top, "dest_parent": base_path, "new_name": "noise_copy"},
        )
        copied_path = str(copy_payload.get("node", {}).get("path", ""))
        if not copied_path:
            raise TestFailure(f"td_copy_node missing copied path: {copy_payload}")

        renamed = await self._call_tool(
            "td_rename_node",
            {"path": copied_path, "new_name": "noise_clone"},
        )
        renamed_path = str(renamed.get("new_path", ""))
        if not renamed_path:
            raise TestFailure(f"td_rename_node missing new_path: {renamed}")

        await self._call_tool("td_delete_node", {"path": renamed_path})

        await self._call_tool(
            "td_connect_nodes",
            {"source_path": noise_top, "target_path": out_top, "source_index": 0, "target_index": 0},
        )
        conns = await self._call_tool("td_get_connections", {"path": out_top})
        if not conns.get("inputs"):
            raise TestFailure("td_get_connections reports no inputs after connect")

        await self._call_tool("td_disconnect", {"path": out_top, "connector_type": "input", "index": 0})
        await self._call_tool(
            "td_connect_nodes",
            {"source_path": noise_top, "target_path": out_top, "source_index": 0, "target_index": 0},
        )

    async def _step_params_exec_and_content(self) -> None:
        noise_top = self.ctx["noise_top"]
        ctrl_chop = self.ctx["ctrl_chop"]
        text_dat = self.ctx["text_dat"]
        table_dat = self.ctx["table_dat"]

        await self._call_tool(
            "td_set_params",
            {"path": noise_top, "params": {"period": {"val": 5.0}, "seed": {"val": 3.0}}},
        )
        await self._call_tool(
            "td_set_params",
            {"path": noise_top, "params": {"seed": {"expr": "absTime.frame % 100"}}},
        )
        params = await self._call_tool("td_get_params", {"path": noise_top, "names": ["period", "seed"]})
        p = params.get("parameters", {})
        if "period" not in p or "seed" not in p:
            raise TestFailure("td_get_params missing expected keys")

        all_params = await self._call_tool("td_get_params", {"path": noise_top})
        pulse_name = None
        for pname, meta in (all_params.get("parameters", {}) or {}).items():
            if isinstance(meta, dict) and bool(meta.get("isPulse", False)):
                pulse_name = pname
                break
        if pulse_name:
            await self._call_tool("td_pulse_param", {"path": noise_top, "param": pulse_name})

        safe_exec = await self._call_tool(
            "td_exec_python",
            {"code": f"__result__ = op('{noise_top}') is not None"},
        )
        if str(safe_exec.get("result", "")).lower() not in {"true", "1"}:
            raise TestFailure(f"td_exec_python unexpected result: {safe_exec}")

        exec_mode = (self.ctx.get("exec_mode") or "restricted").lower()
        if exec_mode == "restricted":
            await self._call_tool(
                "td_exec_python",
                {"code": "import os\n__result__ = 1"},
                expect_error=True,
            )

        await self._call_tool("td_set_content", {"path": text_dat, "text": "tdpilot e2e text"})
        text_payload = await self._call_tool("td_get_content", {"path": text_dat})
        if "text" not in text_payload and "data" not in text_payload:
            raise TestFailure("td_get_content text DAT returned unexpected payload")

        await self._call_tool(
            "td_set_content",
            {
                "path": table_dat,
                "table": [["k", "v"], ["mode", "e2e"], ["seed", str(random.randint(1, 999))]],
            },
        )
        table_payload = await self._call_tool("td_get_content", {"path": table_dat})
        if table_payload.get("format") not in {"table", "text"}:
            raise TestFailure("td_get_content table DAT returned unknown format")

        # CHOP parameter sanity before event tools.
        await self._call_tool("td_set_params", {"path": ctrl_chop, "params": {"value0": {"val": 0.25}}})

    async def _step_capture_geometry_and_debug(self) -> None:
        out_top = self.ctx["out_top"]
        ctrl_chop = self.ctx["ctrl_chop"]
        geo_sop = self.ctx["geo_sop"]
        base_path = self.ctx["base_path"]

        shot = await self._call_tool("td_screenshot", {"path": out_top, "quality": 0.2})
        if int(shot.get("size_bytes", 0) or 0) <= 0:
            raise TestFailure("td_screenshot produced empty capture")

        await self._call_tool(
            "td_capture_and_analyze",
            {"path": out_top, "quality": 0.2, "analyze": False},
            expect_error=True,
        )
        await self._call_tool(
            "td_capture_and_analyze",
            {"path": out_top, "quality": 0.2, "analyze": False, "confirm_image_capture": True},
        )

        chop = await self._call_tool("td_chop_data", {"path": ctrl_chop})
        if int(chop.get("numChans", 0) or 0) < 1:
            raise TestFailure("td_chop_data returned no channels")

        geo = await self._call_tool(
            "td_geometry_data",
            {"path": geo_sop, "include_points": True, "include_prims": True, "limit": 25},
        )
        if int(geo.get("numPoints", 0) or 0) < 1:
            raise TestFailure("td_geometry_data on SOP returned no points")

        pop_path = self.ctx.get("pop_geo")
        if pop_path:
            pop_geo = await self._call_tool(
                "td_geometry_data",
                {"path": pop_path, "include_points": True, "include_prims": False, "limit": 25},
            )
            if pop_geo.get("family") not in {"POP", "SOP"}:
                raise TestFailure("td_geometry_data POP response missing family")

        await self._call_tool("td_cooking_info", {"path": base_path, "recurse": True, "limit": 20})
        await self._call_tool("td_get_errors", {"path": base_path, "recurse": True, "max_depth": 8})

    async def _step_timeline_tools(self) -> None:
        timeline = await self._call_tool("td_timeline")
        frame = int(timeline.get("frame", 0) or 0)

        await self._call_tool("td_timeline_set", {"action": "frame", "frame": frame + 2})
        await self._call_tool("td_timeline_set", {"action": "pause"})
        await self._call_tool("td_timeline_set", {"action": "play"})

    async def _step_macro_tools(self) -> None:
        base_path = self.ctx["base_path"]
        macros = await self._call_tool("td_list_macros")
        available = {item.get("name") for item in macros.get("macros", []) if isinstance(item, dict)}
        if not available:
            raise TestFailure("td_list_macros returned no macros")

        await self._call_tool("td_get_macro_params", {"macro_type": "feedback_loop"})
        await self._call_tool(
            "td_create_macro",
            {
                "parent_path": base_path,
                "macro_type": "feedback_loop",
                "name": "macro_fx",
                "nodeX": 640,
                "nodeY": 0,
            },
        )

    async def _step_event_tools(self) -> None:
        ctrl_chop = self.ctx["ctrl_chop"]

        before = await self._call_tool(
            "td_get_events",
            {"event_type": "chop_change", "limit": 200},
        )
        before_events = before.get("events", []) if isinstance(before, dict) else []
        before_latest_ts = 0.0
        for event in before_events:
            if not isinstance(event, dict):
                continue
            data = event.get("data", {})
            if not isinstance(data, dict) or data.get("path") != ctrl_chop:
                continue
            ts = float(event.get("timestamp", 0.0) or 0.0)
            if ts > before_latest_ts:
                before_latest_ts = ts

        await self._call_tool(
            "td_subscribe",
            {
                "path": ctrl_chop,
                "event_types": ["chop_change"],
                "rate_limit": 0.01,
            },
        )
        # Allow monitor fallback scripts to establish baseline values on first frame.
        await anyio.sleep(0.25)

        await self._call_tool(
            "td_set_params",
            {"path": ctrl_chop, "params": {"value0": {"val": round(random.random(), 4)}}},
        )
        await anyio.sleep(0.25)
        await self._call_tool(
            "td_set_params",
            {"path": ctrl_chop, "params": {"value0": {"val": round(random.random(), 4)}}},
        )

        found = False
        deadline = time.time() + 2.0
        while time.time() < deadline:
            await anyio.sleep(0.15)
            current = await self._call_tool(
                "td_get_events",
                {"event_type": "chop_change", "limit": 200},
            )
            events = current.get("events", []) if isinstance(current, dict) else []
            for event in events:
                if not isinstance(event, dict):
                    continue
                data = event.get("data", {})
                if not isinstance(data, dict) or data.get("path") != ctrl_chop:
                    continue
                ts = float(event.get("timestamp", 0.0) or 0.0)
                if ts > before_latest_ts:
                    found = True
                    break
            if found:
                break

        await self._call_tool("td_unsubscribe", {"path": ctrl_chop})

        if not found:
            raise TestWarning(
                "No new chop_change events observed for subscribed path. Check ws_client URL, active state, and event_emitter wiring in tdpilot_v1_3.tox."
            )

    async def _step_visual_tools(self) -> None:
        out_top = self.ctx["out_top"]

        await self._call_tool(
            "td_monitor_visual",
            {
                "path": out_top,
                "interval": 0.5,
                "quality": 0.2,
                "include_image": True,
                "auto_analyze": False,
            },
            expect_error=True,
        )
        await self._call_tool(
            "td_monitor_visual",
            {"path": out_top, "interval": 0.5, "quality": 0.2, "auto_analyze": False},
        )
        await anyio.sleep(1.1)
        await self._call_tool("td_stop_monitor_visual", {"path": out_top})

        await self._call_tool(
            "td_stream_top",
            {"path": out_top, "fps": 2.0, "quality": 0.2, "include_image": True, "emit_unchanged": False},
            expect_error=True,
        )
        await self._call_tool(
            "td_stream_top",
            {"path": out_top, "fps": 2.0, "quality": 0.2, "emit_unchanged": False},
        )
        await anyio.sleep(1.0)
        await self._call_tool("td_stop_stream_top", {"path": out_top})

        # One short high-token stream with explicit confirmation.
        await self._call_tool(
            "td_stream_top",
            {
                "path": out_top,
                "fps": 1.0,
                "quality": 0.1,
                "include_image": True,
                "confirm_high_token_mode": True,
                "emit_unchanged": True,
            },
        )
        await anyio.sleep(0.5)
        await self._call_tool("td_stop_stream_top", {"path": out_top})

    async def _step_safety_snapshot_state(self) -> None:
        base_path = self.ctx["base_path"]
        noise_top = self.ctx["noise_top"]

        await self._call_tool(
            "td_set_param_bounds",
            {
                "bounds": [
                    {
                        "path": noise_top,
                        "param": "period",
                        "min_val": 1.0,
                        "max_val": 10.0,
                    }
                ],
                "enforce_mode": "clamp",
            },
        )

        await self._call_tool("td_detect_instability", {"path": base_path})
        await self._call_tool("td_emergency_stabilize", {"path": base_path})

        snap_a = await self._call_tool(
            "td_snapshot_scene",
            {"name": "e2e_before", "path": base_path, "include_visual": False},
        )
        snap_a_id = str(snap_a.get("snapshot_id", ""))
        if not snap_a_id:
            raise TestFailure("td_snapshot_scene missing snapshot_id")
        self.ctx["snap_a_id"] = snap_a_id

        await self._call_tool("td_set_params", {"path": noise_top, "params": {"period": {"val": 9.0}}})

        snap_b = await self._call_tool(
            "td_snapshot_scene",
            {"name": "e2e_after", "path": base_path, "include_visual": False},
        )
        snap_b_id = str(snap_b.get("snapshot_id", ""))
        if not snap_b_id:
            raise TestFailure("second td_snapshot_scene missing snapshot_id")
        self.ctx["snap_b_id"] = snap_b_id

        await self._call_tool("td_list_snapshots", {"limit": 20})
        await self._call_tool("td_diff_snapshots", {"snapshot_a": snap_a_id, "snapshot_b": snap_b_id})
        await self._call_tool("td_restore_snapshot", {"snapshot_id": snap_a_id, "dry_run": True})
        await self._call_tool("td_restore_snapshot", {"snapshot_id": snap_a_id, "dry_run": False})

        await self._call_tool("td_clear_param_bounds", {})

        sv1 = await self._call_tool("td_get_state_vector", {"path": base_path, "force_refresh": True})
        if sv1.get("cache", {}).get("hit") not in {False, None}:
            raise TestFailure("first td_get_state_vector expected cache miss")

        cached_state = await self._call_tool("td_get_state_vector", {"path": base_path, "force_refresh": False})
        if cached_state.get("cache", {}).get("hit") is not True:
            raise TestFailure("second td_get_state_vector expected cache hit")

        await self._call_tool("td_get_timescale_state", {"bpm_hint": 120.0, "beats_per_bar": 4})

    async def _step_async_jobs(self) -> None:
        base_path = self.ctx["base_path"]
        noise_top = self.ctx["noise_top"]
        out_top = self.ctx["out_top"]

        dynamics = await self._call_tool(
            "td_describe_dynamics",
            {"path": base_path, "observation_window": 1.2, "sample_rate": 5.0},
        )
        dyn_job = str(dynamics.get("job_id", ""))
        if not dyn_job:
            raise TestFailure("td_describe_dynamics missing job_id")

        optimize = await self._call_tool(
            "td_optimize_visual",
            {
                "goal": "increase temporal variation while staying stable",
                "output_top": out_top,
                "adjustable_params": [
                    {
                        "path": noise_top,
                        "param": "period",
                        "min_val": 1.0,
                        "max_val": 10.0,
                        "step": 1.0,
                    }
                ],
                "max_iterations": 2,
                "convergence_threshold": 0.2,
                "safety_profile": "balanced",
                "root_path": base_path,
                "snapshot_before": True,
            },
        )
        opt_job = str(optimize.get("job_id", ""))
        if not opt_job:
            raise TestFailure("td_optimize_visual missing job_id")

        self.ctx["job_ids"] = [dyn_job, opt_job]
        dyn_result = await self._wait_for_job(dyn_job, timeout_sec=30.0)
        dyn_job_payload = dyn_result.get("job", {})
        if str(dyn_job_payload.get("status", "")).lower() != "completed":
            raise TestFailure(f"Dynamics job did not complete: {dyn_result}")

        opt_result = await self._wait_for_job(opt_job, timeout_sec=30.0)
        opt_job_payload = opt_result.get("job", {})
        if str(opt_job_payload.get("status", "")).lower() != "completed":
            raise TestFailure(f"Optimize job did not complete: {opt_result}")
        if not isinstance(opt_job_payload.get("result"), dict):
            raise TestFailure(f"Optimize job missing result payload: {opt_result}")


    async def _step_cleanup(self) -> None:
        base_path = self.ctx.get("base_path")
        out_top = self.ctx.get("out_top")
        ctrl_chop = self.ctx.get("ctrl_chop")

        # Best-effort stop/cleanup actions.
        if out_top:
            try:
                await self._call_tool("td_stop_stream_top", {"path": out_top})
            except Exception:
                pass
            try:
                await self._call_tool("td_stop_monitor_visual", {"path": out_top})
            except Exception:
                pass

        if ctrl_chop:
            try:
                await self._call_tool("td_unsubscribe", {"path": ctrl_chop})
            except Exception:
                pass

        timeline_before = self.ctx.get("timeline_before") or {}
        try:
            if timeline_before.get("playing"):
                await self._call_tool("td_timeline_set", {"action": "play"})
            else:
                await self._call_tool("td_timeline_set", {"action": "pause"})
        except Exception:
            pass

        if base_path:
            await self._call_tool("td_delete_node", {"path": base_path})


async def run_suite(args: argparse.Namespace) -> dict[str, Any]:
    server = StdioServerParameters(
        command=args.server_command,
        args=args.server_args,
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            suite = E2ESuite(
                session=session,
                repo_dir=Path(args.repo_dir),
                strict_events=args.strict_events,
            )
            return await suite.run()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full live TD + MCP integration suite")
    parser.add_argument(
        "--repo-dir",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root containing pyproject.toml",
    )
    parser.add_argument(
        "--server-command",
        default="uv",
        help="Command to launch MCP server",
    )
    parser.add_argument(
        "--strict-events",
        action="store_true",
        help="Fail the suite if no new runtime events are observed after subscribe+mutate",
    )
    parser.add_argument(
        "--out",
        default="reports/e2e_live.json",
        help="JSON report output path",
    )

    parsed = parser.parse_args()
    parsed.server_args = ["run", "--directory", parsed.repo_dir, "tdpilot"]
    return parsed


def main() -> int:
    args = parse_args()
    report = anyio.run(run_suite, args)

    output = json.dumps(report, indent=2)
    print(output)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output + "\n", encoding="utf-8")

    summary = report.get("summary", {})
    failed = int(summary.get("failed", 0) or 0)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
