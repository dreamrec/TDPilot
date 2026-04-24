#!/usr/bin/env python3
"""Runtime-focused stress matrix against a live TouchDesigner session."""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# Make src/td_mcp importable when script is invoked directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from td_mcp.release_gates import EXPECTED_MIN_TOOL_COUNT  # noqa: E402


@dataclass
class Step:
    name: str
    status: str
    duration_ms: float
    detail: str = ""


class MatrixFailure(RuntimeError):
    pass


class RuntimeMatrix:
    def __init__(self, session: ClientSession) -> None:
        self.session = session
        self.steps: list[Step] = []
        self.ctx: dict[str, Any] = {}

    async def _call_tool(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        *,
        expect_error: bool = False,
    ) -> dict[str, Any]:
        args = {"params": params or {}} if params is not None else None
        result = await self.session.call_tool(name, args)
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

        is_error = self._is_error_payload(payload)
        if expect_error and not is_error:
            raise MatrixFailure(f"{name} expected failure but got success payload: {payload}")
        if not expect_error and is_error:
            raise MatrixFailure(f"{name} failed: {payload}")
        return payload

    @staticmethod
    def _is_error_payload(payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return True
        if payload.get("requires_confirmation"):
            return True
        if payload.get("success") is False and "error" in payload:
            return True
        err = payload.get("error")
        if err not in (None, "", []):
            return True
        return False

    async def _read_job(self, job_id: str, timeout_sec: float = 90.0) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        last: dict[str, Any] = {}
        while time.time() < deadline:
            result = await self.session.read_resource(f"td://job/{job_id}")
            text = result.contents[0].text if result.contents else "{}"
            payload = json.loads(text)
            if not isinstance(payload, dict):
                payload = {"value": payload}
            last = payload
            job = payload.get("job", {})
            if isinstance(job, dict) and str(job.get("status", "")).lower() in {
                "completed",
                "failed",
                "cancelled",
            }:
                return payload
            await anyio.sleep(0.25)
        raise MatrixFailure(f"Timed out waiting for job {job_id}. Last={last}")

    async def _step(self, name: str, fn) -> None:
        started = time.perf_counter()
        try:
            await fn()
            status = "pass"
            detail = ""
        except Exception as exc:  # pragma: no cover - runtime integration
            status = "fail"
            detail = f"{exc}\n{traceback.format_exc(limit=1)}"
        duration_ms = (time.perf_counter() - started) * 1000.0
        self.steps.append(Step(name=name, status=status, duration_ms=duration_ms, detail=detail))

    async def run(self) -> dict[str, Any]:
        await self._step("registry_runtime_surface", self._registry_runtime_surface)
        await self._step("build_runtime_fixture", self._build_runtime_fixture)
        await self._step("token_guard_negatives", self._token_guard_negatives)
        await self._step("cleanup", self._cleanup)

        failed = sum(1 for s in self.steps if s.status == "fail")
        passed = sum(1 for s in self.steps if s.status == "pass")
        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total": len(self.steps),
                "passed": passed,
                "failed": failed,
                "ok": failed == 0,
            },
            "fixture": {
                "base_path": self.ctx.get("base_path"),
                "snapshot_id": self.ctx.get("snapshot_id"),
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

    async def _registry_runtime_surface(self) -> None:
        tools = await self.session.list_tools()
        names = {t.name for t in tools.tools}
        if len(names) < EXPECTED_MIN_TOOL_COUNT:
            raise MatrixFailure(f"Expected at least {EXPECTED_MIN_TOOL_COUNT} tools, got {len(names)}")

    async def _build_runtime_fixture(self) -> None:
        suffix = datetime.now().strftime("%H%M%S")
        base_name = f"runtime_matrix_{suffix}"
        base = await self._call_tool(
            "td_create_node",
            {
                "parent_path": "/project1",
                "node_type": "baseCOMP",
                "name": base_name,
                "nodeX": -420,
                "nodeY": 320,
            },
        )
        base_path = str(base.get("node", {}).get("path", ""))
        if not base_path:
            raise MatrixFailure(f"Failed to create runtime fixture base: {base}")
        self.ctx["base_path"] = base_path

        noise = await self._call_tool(
            "td_create_node",
            {"parent_path": base_path, "node_type": "noiseTOP", "name": "noise", "nodeX": 0, "nodeY": 0},
        )
        out = await self._call_tool(
            "td_create_node",
            {"parent_path": base_path, "node_type": "nullTOP", "name": "out", "nodeX": 220, "nodeY": 0},
        )
        self.ctx["noise_top"] = str(noise.get("node", {}).get("path", ""))
        self.ctx["out_top"] = str(out.get("node", {}).get("path", ""))
        await self._call_tool(
            "td_connect_nodes",
            {
                "source_path": self.ctx["noise_top"],
                "target_path": self.ctx["out_top"],
                "source_index": 0,
                "target_index": 0,
            },
        )
        snap = await self._call_tool(
            "td_snapshot_scene",
            {"name": "runtime_matrix_start", "path": base_path, "include_visual": False},
        )
        self.ctx["snapshot_id"] = str(snap.get("snapshot_id", ""))
        if not self.ctx["snapshot_id"]:
            raise MatrixFailure(f"Failed to create runtime snapshot: {snap}")

    async def _token_guard_negatives(self) -> None:
        out_top = self.ctx["out_top"]
        await self._call_tool(
            "td_capture_and_analyze",
            {"path": out_top, "quality": 0.2, "analyze": False},
            expect_error=True,
        )
        await self._call_tool(
            "td_monitor_visual",
            {"path": out_top, "interval": 0.5, "quality": 0.2, "include_image": True},
            expect_error=True,
        )
        await self._call_tool(
            "td_stream_top",
            {"path": out_top, "fps": 1.0, "quality": 0.2, "include_image": True},
            expect_error=True,
        )

    async def _cleanup(self) -> None:
        base_path = self.ctx.get("base_path")
        if base_path:
            try:
                await self._call_tool("td_delete_node", {"path": base_path})
            except Exception:
                pass


async def run_matrix(args: argparse.Namespace) -> dict[str, Any]:
    server = StdioServerParameters(
        command=args.server_command,
        args=["run", "--directory", args.repo_dir, "tdpilot"],
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            matrix = RuntimeMatrix(session)
            return await matrix.run()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run runtime stress matrix against live TouchDesigner")
    parser.add_argument(
        "--repo-dir",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root containing pyproject.toml",
    )
    parser.add_argument("--server-command", default="uv")
    parser.add_argument("--out", default="reports/runtime_stress_matrix.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = anyio.run(run_matrix, args)
    output = json.dumps(report, indent=2)
    print(output)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output + "\n", encoding="utf-8")
    failed = int(report.get("summary", {}).get("failed", 0) or 0)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
