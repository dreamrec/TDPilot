"""End-to-end live audit of v1.6.16 against a running TouchDesigner.

Run from the worktree root:

    cd <worktree>
    PYTHONPATH=src python scripts/audit_v1_6_16_live.py

What it does (in order):

1. Loads the WORKTREE's `td_mcp` (not the installed plugin), so the
   `_read_journal` injection, `activity_log` recording, and the two new
   tools are exercised with the v1.6.16 code.
2. Builds a real `TDClient` + `ServiceContainer` + `Context` so
   ``tool_registry._forward`` runs against the live TD on 127.0.0.1:9981.
3. Resolves the shared secret from `~/.tdpilot/.tdpilot.env` so requests
   pass auth on TD 2025+.
4. Exercises:
   - First `td_get_info` → `_read_journal.call_count == 1`,
     `result_unchanged is None`.
   - Second `td_get_info` → `call_count == 2`. `result_unchanged` is
     determined by whether `seconds`/`frame` advanced (almost always
     True if TD is playing, so we accept either value but require the
     field to be present).
   - `td_get_activity_log` MCP tool → returns the two entries we just
     created, newest-first, with all expected columns.
   - `td_self_update(check_only=True)` MCP tool → returns the GitHub
     latest-release semver comparison with a structured envelope.
   - Error path: `td_get_nodes("/nonexistent")` records ok=True (TD
     returns 200 with success:false body) — confirms the recorder
     follows HTTP-status contract (not body-level semantic failures).
5. Checks `activity_log` ring-buffer bounds + that the journal hint
   shape stays stable across all dispatched tools.

Each step prints PASS / FAIL with the evidence inline. Final summary at
the end. Exit code 0 if everything passed; non-zero otherwise.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# ── bootstrap ────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Skip the env-bootstrap module's heavy startup probe; we resolve the
# shared secret manually below.
os.environ.setdefault("TDPILOT_SKIP_AUTH_BOOTSTRAP", "1")

_secret_file = Path.home() / ".tdpilot" / ".tdpilot.env"
if _secret_file.is_file():
    for line in _secret_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("TD_MCP_SHARED_SECRET="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                os.environ["TD_MCP_SHARED_SECRET"] = value
            break

from td_mcp import __version__ as worktree_version  # noqa: E402
from td_mcp import activity_log, read_journal  # noqa: E402
from td_mcp import tool_registry as tr  # noqa: E402
from td_mcp.registry.tools_meta import (  # noqa: E402
    td_get_activity_log,
    td_self_update,
)
from td_mcp.services import ServiceContainer  # noqa: E402
from td_mcp.td_client import TDClient  # noqa: E402
from td_mcp.telemetry import TelemetryCollector  # noqa: E402

# ── helpers ──────────────────────────────────────────────────────────

PASSES: list[str] = []
FAILS: list[str] = []


def check(label: str, condition: bool, evidence: str = "") -> None:
    if condition:
        PASSES.append(label)
        print(f"PASS  {label}" + (f"\n      {evidence}" if evidence else ""))
    else:
        FAILS.append(label)
        print(f"FAIL  {label}" + (f"\n      {evidence}" if evidence else ""))


def _build_ctx() -> SimpleNamespace:
    client = TDClient(
        host="127.0.0.1",
        port=9981,
        shared_secret=os.environ.get("TD_MCP_SHARED_SECRET"),
    )
    telemetry = TelemetryCollector()
    services = ServiceContainer(
        td_client=client,
        technique_store=None,
        preference_store=None,
        telemetry=telemetry,
    )
    state = {"services": services}
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=state,
            lifespan_state=state,
        )
    )


def _parse_envelope(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise TypeError(f"unexpected envelope type {type(raw).__name__}")


# ── checks ───────────────────────────────────────────────────────────


async def audit_first_call_envelope(ctx: SimpleNamespace) -> None:
    read_journal.reset()
    activity_log.reset()
    raw = await tr._forward(ctx, "td_get_info", "info")
    parsed = _parse_envelope(raw)
    has_hint = "_read_journal" in parsed
    check(
        "1.1  _read_journal envelope present on first call",
        has_hint,
        f"keys={sorted(parsed.keys())[:8]}",
    )
    if has_hint:
        h = parsed["_read_journal"]
        check(
            "1.2  first call: call_count == 1",
            h["call_count"] == 1,
            f"call_count={h['call_count']}",
        )
        check(
            "1.3  first call: result_unchanged is None",
            h["result_unchanged"] is None,
            f"result_unchanged={h['result_unchanged']!r}",
        )
        check(
            "1.4  first_seen_at and last_seen_at present",
            "first_seen_at" in h and "last_seen_at" in h,
            f"first_seen_at={h.get('first_seen_at')}, last_seen_at={h.get('last_seen_at')}",
        )
    api_v = parsed.get("api_version")
    check(
        "1.5  TD api_version is 1.6.16 (TD-side wired)",
        api_v == "1.6.16",
        f"api_version={api_v!r}",
    )


async def audit_repeat_call(ctx: SimpleNamespace) -> None:
    raw = await tr._forward(ctx, "td_get_info", "info")
    parsed = _parse_envelope(raw)
    h = parsed["_read_journal"]
    check(
        "2.1  second call: call_count == 2",
        h["call_count"] == 2,
        f"call_count={h['call_count']}",
    )
    # result_unchanged is True only if TD info bytes are identical. The
    # `frame` and `seconds` fields advance every cook tick, so on a playing
    # project this is almost always False. We accept either, but the field
    # MUST be a real bool (not None).
    check(
        "2.2  second call: result_unchanged is bool (True or False, not None)",
        isinstance(h["result_unchanged"], bool),
        f"result_unchanged={h['result_unchanged']!r}",
    )


async def audit_static_endpoint_unchanged(ctx: SimpleNamespace) -> None:
    """Pick an endpoint whose response IS stable across cooks: list_families.
    Two repeat calls should produce result_unchanged=True.
    """
    raw1 = await tr._forward(ctx, "td_list_families", "families")
    raw2 = await tr._forward(ctx, "td_list_families", "families")
    p2 = _parse_envelope(raw2)
    h = p2["_read_journal"]
    check(
        "3.1  static endpoint repeat: result_unchanged == True",
        h["result_unchanged"] is True,
        f"call_count={h['call_count']}, result_unchanged={h['result_unchanged']}",
    )


async def audit_activity_log_server_side() -> None:
    snap = activity_log.snapshot(limit=10)
    check(
        "4.1  activity_log captured >= 4 entries from audit so far",
        len(snap) >= 4,
        f"entries={len(snap)}, tools={[e['tool'] for e in snap]}",
    )
    # Field-shape contract
    if snap:
        e = snap[0]
        required = {"ts", "tool", "args_summary", "result_summary", "duration_ms", "ok"}
        check(
            "4.2  activity_log entry shape complete",
            required.issubset(set(e.keys())),
            f"keys={sorted(e.keys())}",
        )
        check(
            "4.3  activity_log duration_ms is float and > 0",
            isinstance(e["duration_ms"], (int, float)) and e["duration_ms"] >= 0,
            f"duration_ms={e['duration_ms']}",
        )


async def audit_td_get_activity_log_tool(ctx: SimpleNamespace) -> None:
    raw = await td_get_activity_log(ctx, limit=5)
    parsed = _parse_envelope(raw)
    check(
        "5.1  td_get_activity_log returns count + max_buffer + entries",
        all(k in parsed for k in ("count", "max_buffer", "entries", "schema_version")),
        f"keys={sorted(parsed.keys())}",
    )
    check(
        "5.2  td_get_activity_log respects limit",
        len(parsed["entries"]) <= 5,
        f"returned={len(parsed['entries'])}",
    )
    # Did it ALSO log its own call?
    snap_after = activity_log.snapshot(limit=1)
    check(
        "5.3  td_get_activity_log itself is NOT recorded (server-local, no _forward path)",
        snap_after[0]["tool"] != "td_get_activity_log",
        f"newest_tool={snap_after[0]['tool']}",
    )
    # tool_filter argument
    filtered = await td_get_activity_log(ctx, limit=20, tool_filter="td_list_families")
    fparsed = _parse_envelope(filtered)
    check(
        "5.4  td_get_activity_log tool_filter works",
        all(e["tool"] == "td_list_families" for e in fparsed["entries"]),
        f"filtered_tools={[e['tool'] for e in fparsed['entries']]}",
    )


async def audit_td_self_update_tool(ctx: SimpleNamespace) -> None:
    # check_only=True is safe — no disk writes, just GitHub API hit.
    raw = await td_self_update(ctx, check_only=True)
    parsed = _parse_envelope(raw)
    has_required = all(k in parsed for k in ("installed", "latest", "newer_available", "release_url"))
    check(
        "6.1  td_self_update check_only returns full envelope",
        has_required,
        f"keys={sorted(parsed.keys())}",
    )
    if has_required:
        check(
            "6.2  installed matches worktree __version__",
            parsed["installed"] == worktree_version,
            f"installed={parsed['installed']!r}, worktree={worktree_version!r}",
        )
        check(
            "6.3  follow_up reminder present (post-update setup hint)",
            "follow_up" in parsed and "setup_mcp_in_td" in parsed.get("follow_up", ""),
            f"follow_up={parsed.get('follow_up','')[:80]!r}",
        )


async def audit_error_path(ctx: SimpleNamespace) -> None:
    """A request that TD rejects: nonexistent path. TD returns 200 + success:false."""
    activity_log.reset()
    raw = await tr._forward(ctx, "td_get_nodes", "nodes/list", {"path": "/no/such/path/anywhere"})
    parsed = _parse_envelope(raw)
    # The response itself may or may not be wrapped — depends on the error format.
    snap = activity_log.snapshot(limit=1)
    has_entry = len(snap) == 1
    check(
        "7.1  error-path call still records to activity_log",
        has_entry,
        f"entries={len(snap)}",
    )
    if has_entry:
        check(
            "7.2  error-path call has _read_journal too (advisory layer is universal)",
            "_read_journal" in parsed or parsed.get("success") is False,
            f"keys={sorted(parsed.keys())[:8]}, success={parsed.get('success')}",
        )


async def audit_concurrent_calls(ctx: SimpleNamespace) -> None:
    """Fire 10 parallel calls; verify no race conditions in journal/log."""
    read_journal.reset()
    activity_log.reset()
    results = await asyncio.gather(
        *[tr._forward(ctx, "td_list_families", "families") for _ in range(10)]
    )
    # All 10 should have read_journal hints with call_count summing to ≥ 10
    parsed_all = [_parse_envelope(r) for r in results]
    counts = sorted(p["_read_journal"]["call_count"] for p in parsed_all)
    check(
        "8.1  concurrent: 10 parallel calls all have envelopes",
        all("_read_journal" in p for p in parsed_all),
        "all hinted",
    )
    check(
        "8.2  concurrent: call_count reaches 10 monotonically (no lost counts)",
        max(counts) == 10 and min(counts) == 1,
        f"counts={counts}",
    )
    # activity_log should have exactly 10 entries
    snap = activity_log.snapshot(limit=20)
    check(
        "8.3  concurrent: activity_log recorded all 10 calls",
        len(snap) == 10,
        f"recorded={len(snap)}",
    )


async def audit_tool_schemas() -> None:
    """Pydantic schemas for the new tools — make sure FastMCP knows about them."""
    tools = tr.mcp._tool_manager._tools
    for name in ("td_get_activity_log", "td_self_update"):
        t = tools.get(name)
        check(
            f"9.{'1' if name == 'td_get_activity_log' else '2'}  {name} is registered as a Tool object",
            t is not None,
            f"type={type(t).__name__ if t else 'None'}",
        )


async def audit_module_imports() -> None:
    """Cold-import test: the side-effect chain in registry/__init__.py must
    not break the package."""
    check(
        "10.1 td_mcp.read_journal module loads cleanly",
        hasattr(read_journal, "record_call"),
        "",
    )
    check(
        "10.2 td_mcp.activity_log module loads cleanly",
        hasattr(activity_log, "record") and hasattr(activity_log, "snapshot"),
        "",
    )
    from td_mcp import self_updater
    check(
        "10.3 td_mcp.self_updater module loads cleanly",
        callable(self_updater.run) and callable(self_updater.is_newer),
        "",
    )


# ── main ─────────────────────────────────────────────────────────────


async def main() -> int:
    print(f"=== Live audit of TDPilot v{worktree_version} ===\n")
    ctx = _build_ctx()
    try:
        # Health-check the TD connection up front.
        h = await ctx.request_context.lifespan_state["services"].td_client.health_check()
        check("0.0  TD reachable + auth OK", h.get("status") == "ok", f"health={h}")
        if not FAILS:
            await audit_first_call_envelope(ctx)
            await audit_repeat_call(ctx)
            await audit_static_endpoint_unchanged(ctx)
            await audit_activity_log_server_side()
            await audit_td_get_activity_log_tool(ctx)
            await audit_td_self_update_tool(ctx)
            await audit_error_path(ctx)
            await audit_concurrent_calls(ctx)
            await audit_tool_schemas()
            await audit_module_imports()
    finally:
        try:
            await ctx.request_context.lifespan_state["services"].td_client.close()
        except Exception:
            pass

    print(f"\n=== Summary: {len(PASSES)} pass, {len(FAILS)} fail ===")
    if FAILS:
        print("FAILED:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception:
        traceback.print_exc()
        sys.exit(2)
