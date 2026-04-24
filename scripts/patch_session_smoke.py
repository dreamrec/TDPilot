"""Live-TD end-to-end smoke for the Phase 3 patch session MVP.

Run with TD launched and the TDPilot MCP component started.
Not part of CI.

Exercises:
  1. td_patch_plan   — build a PatchPlan
  2. td_patch_preview — inspect live_risk_flags
  3. td_patch_apply  — execute; assert status=clean
  4. td_patch_validate — assert ok=True
  5. td_project_lifecycle(action=undo) — revert
  6. Post-undo: created paths gone

Usage:
    uv run python scripts/patch_session_smoke.py [--target /project1]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from td_mcp.td_client import TDClient


async def main(target: str) -> int:
    host = os.environ.get("TDPILOT_HOST", "127.0.0.1")
    port = int(os.environ.get("TDPILOT_PORT", "9980"))
    secret = os.environ.get("TDPILOT_SHARED_SECRET", "")

    client = TDClient(host=host, port=port, shared_secret=secret)

    # 1. Plan
    print(f"[1/6] td_patch_plan({target!r}, intent='feedback trail') ... ", flush=True)
    from td_mcp import patch
    plan = await patch.build_plan(
        td_client=client,
        target_root=target,
        intent="feedback trail",
    )
    print(f"  plan_id={plan.id} source={plan.source} ops={len(plan.operations)}")
    if not plan.operations:
        print(
            "  FAIL: expected at least one operation from 'feedback trail' intent; "
            "_INTENT_MACRO_KEYWORDS may be out of sync",
            file=sys.stderr,
        )
        return 1

    # 2. Preview
    print("[2/6] td_patch_preview ... ", flush=True)
    preview = await patch.preview_plan(client, plan)
    print(f"  live_risk_flags={preview['live_risk_flags']}")

    # 3. Apply
    print("[3/6] td_patch_apply auto_validate=True ... ", flush=True)
    from td_mcp.patch.undo_sentinel import UndoBlockSentinel
    sentinel = UndoBlockSentinel()
    result = await patch.apply_plan(client, plan, sentinel=sentinel, auto_validate=True)
    print(f"  status={result.status} created={result.created_paths}")
    if result.status != "clean":
        print(f"  FAIL: expected clean, got {result.status}: {result.failed_reason}", file=sys.stderr)
        return 1

    # 4. Validate standalone
    print("[4/6] td_patch_validate ... ", flush=True)
    from td_mcp.models.patch import ValidationPlan
    report = await patch.validate_target(client, ValidationPlan(target_root=target))
    print(f"  ok={report.ok}")
    if not report.ok:
        print("  FAIL: validation reports not ok", file=sys.stderr)
        return 1

    # 5. Undo
    print("[5/6] td_project_lifecycle action=undo ... ", flush=True)
    await client.request("project/lifecycle", {"action": "undo"})
    print("  undo requested")

    # 6. Post-undo check
    print("[6/6] Post-undo: verifying created paths are gone ... ", flush=True)
    resp = await client.request("nodes", {"path": target, "limit": 500})
    live_paths = {n["path"] for n in (resp if isinstance(resp, list) else resp.get("nodes", [])) if isinstance(n, dict)}
    still_present = [p for p in result.created_paths if p in live_paths]
    if still_present:
        print(f"  FAIL: expected paths gone, still present: {still_present}", file=sys.stderr)
        return 1
    print("  clean — all created paths reverted")

    print("\nALL SMOKE CHECKS PASSED — Phase 3 patch session works end to end.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="/project1")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.target)))
