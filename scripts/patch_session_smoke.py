"""Live-TD comprehensive smoke for the Patch Session API (v1.5.1).

Run with TD launched and the TDPilot MCP component started.
Not part of CI — requires a running TouchDesigner instance.

Exercises all six op kinds end-to-end, plus the sentinel guard,
variations, legacy intent path, validator, and auto-validate
status promotion. Each scenario runs in its own scratch container
under ``/project1/tdpilot_smoke/`` so cleanup is one delete at the
end (whether scenarios pass or fail).

Coverage:
    [1/13]  connectivity         - TD reachable; api_version present
    [2/13]  kind=create_node     - node creation + readback
    [3/13]  kind=set_params      - parameter set + readback
    [4/13]  kind=connect         - wire two nodes + verify
    [5/13]  kind=layout          - set node position via /api/exec
    [6/13]  kind=annotate        - annotateCOMP + text param
    [7/13]  kind=macro           - macro_engine DI dispatch
    [8/13]  sentinel guard       - NestedBlockError on re-entry
    [9/13]  variations           - param_jitter reproducibility
    [10/13] legacy intent        - intent='feedback trail' -> macro op
    [11/13] validate_target      - composite errors+cook probe
    [12/13] auto_validate        - populates result.validation
    [13/13] cleanup              - delete scratch container

Usage:
    TDPILOT_PORT=9981 TDPILOT_SHARED_SECRET=<secret> \\
        uv run python scripts/patch_session_smoke.py [--target /project1]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from td_mcp import patch
from td_mcp.macros import MacroEngine
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.undo_sentinel import UndoBlockSentinel
from td_mcp.td_client import TDClient

# All scenarios scope work inside this scratch container so cleanup
# is one delete regardless of which scenarios pass or fail.
SCRATCH_NAME = "tdpilot_smoke"
results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    icon = "OK " if passed else "FAIL"
    line = f"  [{icon}] {name}"
    if detail:
        line += f"  [{detail[:200]}]"
    print(line, flush=True)


def _plan(ops, target_root, undo_label, capture_frames=None):
    return PatchPlan(
        target_root=target_root,
        source="operations",
        operations=ops,
        undo_label=undo_label,
        validation_plan=ValidationPlan(target_root=target_root, capture_frames=capture_frames or []),
    )


async def main(target: str) -> int:
    host = os.environ.get("TDPILOT_HOST", "127.0.0.1")
    port = int(os.environ.get("TDPILOT_PORT", "9981"))
    secret = os.environ.get("TDPILOT_SHARED_SECRET", "")

    client = TDClient(host=host, port=port, shared_secret=secret)
    scratch = f"{target.rstrip('/')}/{SCRATCH_NAME}"

    print("=" * 70)
    print(" TDPilot Patch Session - comprehensive live-TD smoke")
    print("=" * 70)
    print(f" target: {target}    scratch: {scratch}")
    print()

    # Setup: scratch container.
    try:
        setup_resp = await client.request(
            "node/create",
            {"parent_path": target, "node_type": "baseCOMP", "name": SCRATCH_NAME},
        )
        if isinstance(setup_resp, dict) and setup_resp.get("error"):
            print(f"setup failed: {setup_resp['error']}")
            await client.close()
            return 1
    except Exception as exc:  # noqa: BLE001
        print(f"setup exception: {exc}")
        await client.close()
        return 1

    try:
        # ─── Layer 1: connectivity ──────────────────────────────────
        try:
            info = await client.request("info", {})
            api_v = info.get("api_version") if isinstance(info, dict) else None
            ok = bool(api_v)
            record("[1/13] connectivity", ok, f"api_version={api_v!r}")
        except Exception as exc:  # noqa: BLE001
            record("[1/13] connectivity", False, f"exception: {exc}")

        # ─── Layer 2: 6 op kinds ────────────────────────────────────

        # 2/13 create_node
        s = UndoBlockSentinel()
        plan = _plan(
            [PatchOperation(kind="create_node", target=scratch, args={"op_type": "noiseTOP", "name": "n1"})],
            scratch,
            "smoke-create_node",
        )
        result = await patch.apply_plan(client, plan, sentinel=s, auto_validate=False)
        ok = result.status == "clean" and bool(result.created_paths)
        record("[2/13] kind=create_node", ok, f"status={result.status} created={result.created_paths}")
        n1_path = result.created_paths[0] if result.created_paths else None

        # 3/13 set_params (requires the node from step 2)
        if n1_path:
            s = UndoBlockSentinel()
            plan = _plan(
                [PatchOperation(kind="set_params", target=n1_path, args={"params": {"period": 0.5}})],
                scratch,
                "smoke-set_params",
            )
            result = await patch.apply_plan(client, plan, sentinel=s, auto_validate=False)
            # TD's node/params returns:
            #   {"path": ..., "type": ..., "parameters": {name: {"value": ..., ...}}}
            readback = await client.request("node/params", {"path": n1_path})
            period = None
            if isinstance(readback, dict):
                params_dict = readback.get("parameters", {})
                if isinstance(params_dict, dict):
                    entry = params_dict.get("period", {})
                    if isinstance(entry, dict):
                        period = entry.get("value")
            ok = result.status == "clean" and period == 0.5
            record("[3/13] kind=set_params", ok, f"status={result.status} period->{period}")
        else:
            record("[3/13] kind=set_params", False, "skipped: create_node didn't yield path")

        # 4/13 connect (need a second node)
        s = UndoBlockSentinel()
        n2 = await client.request(
            "node/create",
            {"parent_path": scratch, "node_type": "levelTOP", "name": "n2"},
        )
        n2_path = n2.get("node", {}).get("path") if isinstance(n2, dict) else None
        if n1_path and n2_path:
            plan = _plan(
                [PatchOperation(kind="connect", target=scratch, args={"from": n1_path, "to": n2_path})],
                scratch,
                "smoke-connect",
            )
            result = await patch.apply_plan(client, plan, sentinel=s, auto_validate=False)
            ok = result.status == "clean"
            record("[4/13] kind=connect", ok, f"status={result.status} reason={result.failed_reason}")
        else:
            record("[4/13] kind=connect", False, "scaffolding incomplete")

        # 5/13 layout
        s = UndoBlockSentinel()
        layout_node = await client.request(
            "node/create", {"parent_path": scratch, "node_type": "nullTOP", "name": "lay"}
        )
        lay_path = layout_node.get("node", {}).get("path") if isinstance(layout_node, dict) else None
        if lay_path:
            plan = _plan(
                [PatchOperation(kind="layout", target=lay_path, args={"x": 250, "y": 175})],
                scratch,
                "smoke-layout",
            )
            result = await patch.apply_plan(client, plan, sentinel=s, auto_validate=False)
            detail = await client.request("node/detail", {"path": lay_path})
            x_actual = y_actual = None
            if isinstance(detail, dict):
                node_data = detail.get("node", detail)
                if isinstance(node_data, dict):
                    x_actual = node_data.get("nodeX")
                    y_actual = node_data.get("nodeY")
            ok = result.status == "clean" and x_actual == 250 and y_actual == 175
            record("[5/13] kind=layout", ok, f"status={result.status} pos=({x_actual},{y_actual})")
        else:
            record("[5/13] kind=layout", False, "scaffolding incomplete")

        # 6/13 annotate
        s = UndoBlockSentinel()
        plan = _plan(
            [PatchOperation(kind="annotate", target=scratch, args={"text": "smoke annotation"})],
            scratch,
            "smoke-annotate",
        )
        result = await patch.apply_plan(client, plan, sentinel=s, auto_validate=False)
        ok = result.status == "clean" and bool(result.created_paths)
        record("[6/13] kind=annotate", ok, f"status={result.status} created={result.created_paths}")

        # 7/13 macro (needs MacroEngine DI)
        s = UndoBlockSentinel()
        engine = MacroEngine(td_client=client, user_template_dir=None)
        plan = _plan(
            [PatchOperation(kind="macro", target=scratch, args={"macro_type": "feedback_loop"})],
            scratch,
            "smoke-macro",
        )
        result = await patch.apply_plan(client, plan, sentinel=s, auto_validate=False, macro_engine=engine)
        ok = result.status == "clean"
        record("[7/13] kind=macro (engine DI)", ok, f"status={result.status} reason={result.failed_reason}")

        # ─── Layer 3: behaviors ─────────────────────────────────────

        # 8/13 sentinel guard
        s = UndoBlockSentinel()
        s.mark_active("pre-existing")
        plan = _plan(
            [
                PatchOperation(
                    kind="create_node", target=scratch, args={"op_type": "noiseTOP", "name": "blocked"}
                )
            ],
            scratch,
            "smoke-sentinel",
        )
        try:
            await patch.apply_plan(client, plan, sentinel=s)
            record("[8/13] sentinel guard", False, "expected NestedBlockError, got success")
        except patch.NestedBlockError:
            record("[8/13] sentinel guard", True, "NestedBlockError raised correctly")
        except Exception as exc:  # noqa: BLE001
            record("[8/13] sentinel guard", False, f"wrong exception type: {type(exc).__name__}")

        # 9/13 variations (pure local; no TD calls)
        base = _plan(
            [PatchOperation(kind="set_params", target=scratch + "/dummy", args={"params": {"period": 1.0}})],
            scratch,
            "base",
        )
        v1, _ = patch.generate_variants(base, n=3, strategies=["param_jitter"], seed=42)
        v2, _ = patch.generate_variants(base, n=3, strategies=["param_jitter"], seed=42)
        same_seed_match = [a.model_dump() for a in v1] == [b.model_dump() for b in v2]
        ok = same_seed_match and len(v1) == 3
        record(
            "[9/13] variations (param_jitter reproducibility)",
            ok,
            f"n={len(v1)} same_seed_match={same_seed_match}",
        )

        # 10/13 legacy intent → macro op
        legacy_plan = await patch.build_plan(td_client=client, target_root=target, intent="feedback trail")
        ok = (
            legacy_plan.source == "intent_heuristic"
            and len(legacy_plan.operations) == 1
            and legacy_plan.operations[0].kind == "macro"
        )
        record(
            "[10/13] legacy intent -> macro op",
            ok,
            f"source={legacy_plan.source} kind0={legacy_plan.operations[0].kind if legacy_plan.operations else None}",
        )

        # 11/13 validate_target on the scratch (should be ok=True)
        report = await patch.validate_target(client, ValidationPlan(target_root=scratch))
        record("[11/13] validate_target clean", report.ok, f"ok={report.ok} errors={len(report.errors)}")

        # 12/13 auto_validate populates result.validation
        s = UndoBlockSentinel()
        plan = _plan(
            [PatchOperation(kind="create_node", target=scratch, args={"op_type": "nullTOP", "name": "av"})],
            scratch,
            "smoke-autovalidate",
        )
        result = await patch.apply_plan(client, plan, sentinel=s, auto_validate=True)
        ok = result.status in ("clean", "warnings") and result.validation is not None
        record(
            "[12/13] auto_validate populates result.validation",
            ok,
            f"status={result.status} validation_set={result.validation is not None}",
        )

    finally:
        # 13/13 cleanup
        print()
        try:
            await client.request("node/delete", {"path": scratch})
            record("[13/13] cleanup", True, f"deleted {scratch}")
        except Exception as exc:  # noqa: BLE001
            record("[13/13] cleanup", False, f"delete failed: {exc}")
        await client.close()

    # Summary
    print()
    print("=" * 70)
    passed = sum(1 for _, p, _ in results if p)
    failed = len(results) - passed
    print(f" SUMMARY:  {passed}/{len(results)} passed,  {failed} failed")
    print("=" * 70)

    if failed:
        print("\nFailures:")
        for n, p, d in results:
            if not p:
                print(f"  FAIL {n}: {d}")
        return 1

    print("\nALL SMOKE CHECKS PASSED - Patch Session API works end-to-end.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="/project1", help="Parent path for the scratch container")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.target)))
