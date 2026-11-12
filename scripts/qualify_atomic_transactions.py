#!/usr/bin/env python3
"""Exercise native atomic transactions and guarded rollback in an owned TD COMP."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from td_mcp.brain.transaction import apply_transaction
from td_mcp.macros.engine import MacroEngine
from td_mcp.models.brain import TransactionOptions
from td_mcp.models.build import ValidationAssertion, ValidationContract
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.applier import apply_plan
from td_mcp.patch.undo_sentinel import UndoBlockSentinel
from td_mcp.td_client import TDClient, TouchDesignerAPIError


def operation(kind, target=None, **args):
    return {"kind": kind, "target": target, "args": args}


async def qualify():
    client = TDClient(timeout=30)
    root = None
    checks = []
    report = {"ok": False, "checks": checks}
    try:
        report["info"] = await client.request("info")
        cap = await client.request("patch/status")
        assert cap == await client.request("patch/status"), "Receipt session is not stable"
        created = await client.request(
            "node/create",
            {
                "parent_path": "/project1",
                "node_type": "baseCOMP",
                "name": "tdpilot_atomic_test_" + uuid.uuid4().hex[:10],
            },
        )
        root = created["node"]["path"]
        report["root"] = root

        async def apply(ops, label="Atomic qualification"):
            body = {
                "session": cap["session"],
                "request_id": str(uuid.uuid4()),
                "target_root": root,
                "undo_label": label,
                "operations": ops,
            }
            result = await client.request("patch/apply", body)
            return body, result

        async def rollback(body):
            return await client.request(
                "patch/rollback", {"session": cap["session"], "request_id": body["request_id"]}
            )

        def check(name, condition, detail=None):
            checks.append({"name": name, "ok": bool(condition), "detail": detail})
            assert condition, name + ": " + str(detail)

        setup = [
            operation("create_node", root, op_type=t, name=n)
            for n, t in [
                ("a", "noiseTOP"),
                ("b", "constantTOP"),
                ("out", "nullTOP"),
                ("text", "textDAT"),
                ("table", "tableDAT"),
                ("group", "baseCOMP"),
            ]
        ]
        setup += [
            operation("create_node", root + "/group", op_type="textDAT", name="inside"),
            operation("set_params", root + "/a", params={"period": {"expr": "2 + 0.5"}}),
            operation("set_dat_content", root + "/text", text="before\nUnicode: λ\n"),
            operation("set_dat_content", root + "/table", table=[["key", "value"], ["one", "1"]]),
            operation("set_dat_content", root + "/group/inside", text="preserve nested content"),
            operation("connect", **{"from": root + "/a", "to": root + "/out"}),
        ]
        prior_body, prior = await apply(setup, "Unrelated prior edit")
        check("setup", prior["status"] == "clean", prior.get("failed_reason"))
        prior_stack = (await client.request("project/lifecycle", {"action": "status"}))["undo"]["undoStack"]
        mutations = [
            operation("set_params", root + "/a", params={"period": {"mode": "constant", "val": 9}}),
            operation("set_dat_content", root + "/text", text="after\n"),
            operation("set_dat_content", root + "/table", table=[["new", "contents"]]),
            operation("layout", root + "/a", x=987, y=-456),
            operation(
                "route_swap",
                root + "/out",
                **{"from": root + "/b", "to": root + "/out", "old_from": root + "/a"},
            ),
            operation("delete_node", root + "/group", owned=True),
            operation("create_node", root, op_type="glslTOP", name="generated"),
        ]
        body, changed = await apply(mutations)
        check("mixed_apply", changed["status"] == "clean", changed.get("failed_reason"))
        replay = await client.request("patch/apply", body)
        check("replay_returns_same_receipt", replay == changed)
        try:
            await client.request("patch/apply", {**body, "undo_label": "Changed payload"})
            check("reject_reused_id", False)
        except TouchDesignerAPIError:
            check("reject_reused_id", True)
        proof = await rollback(body)
        check("exact_mixed_rollback", proof.get("ok"), proof)
        check("rollback_idempotent", await rollback(body) == proof)
        check(
            "prior_undo_history_preserved",
            (await client.request("project/lifecycle", {"action": "status"}))["undo"]["undoStack"]
            == prior_stack,
        )
        pars = await client.request("node/params", {"path": root + "/a", "names": ["period"]})
        check(
            "prior_expression_restored",
            pars["parameters"]["period"]["expr"] == "2 + 0.5"
            and pars["parameters"]["period"]["value"] == 2.5,
            pars,
        )
        # Deliberate failure after edits, including implicit GLSL source siblings.
        fail_body, failed = await apply(
            mutations + [operation("create_node", root, op_type="notARealTOP", name="failure")]
        )
        check(
            "failed_apply_rolls_back",
            failed["status"] == "broken" and failed.get("rollback", {}).get("ok"),
            failed,
        )
        check(
            "failed_request_replay_does_not_reapply", await client.request("patch/apply", fail_body) == failed
        )
        check(
            "prior_state_survives_failure",
            (await client.request("node/params", {"path": root + "/a", "names": ["period"]}))["parameters"][
                "period"
            ]["value"]
            == 2.5,
        )
        # A raw edit may not create an undo entry. After-state guard must catch it.
        raw_body, raw = await apply([operation("set_params", root + "/a", params={"period": 7})])
        await client.request("node/params/set", {"path": root + "/a", "params": {"period": 8}})
        refusal = await rollback(raw_body)
        check("raw_intervening_edit_blocks_undo", refusal.get("ok") is False, refusal)
        check(
            "raw_intervening_edit_preserved",
            (await client.request("node/params", {"path": root + "/a", "names": ["period"]}))["parameters"][
                "period"
            ]["value"]
            == 8,
        )
        # Restore this known test value to its exact post-apply state for cleanup.
        await client.request("node/params/set", {"path": root + "/a", "params": {"period": 7}})
        check("recover_after_owned_test_edit", (await rollback(raw_body)).get("ok"))
        first_body, first = await apply([operation("set_params", root + "/a", params={"period": 4})])
        second_body, second = await apply(
            [operation("set_params", root + "/b", params={"colorr": 0.2})], "Intervening edit"
        )
        check("intervening_undo_entry_blocks_rollback", (await rollback(first_body)).get("ok") is False)
        check("rollback_newest_first", (await rollback(second_body)).get("ok"))
        check("rollback_older_after_newest", (await rollback(first_body)).get("ok"))
        for name, ops in [
            ("collision", [operation("create_node", root, op_type="noiseTOP", name="a")]),
            ("out_of_scope", [operation("layout", "/project1/tdpilot", x=1, y=1)]),
            ("pulse", [operation("set_params", root + "/a", params={"resetpulse": 1})]),
            ("delete_root", [operation("delete_node", root, owned=True)]),
        ]:
            try:
                _, blocked = await apply(ops)
                check(
                    "reject_" + name,
                    blocked["status"] == "broken" and blocked.get("rollback", {}).get("ok"),
                    blocked,
                )
            except TouchDesignerAPIError:
                check("reject_" + name, True)
        # Host application must use the endpoint, not legacy start/end requests.
        plan = PatchPlan(
            target_root=root,
            source="operations",
            undo_label="Host native",
            validation_plan=ValidationPlan(target_root=root),
            operations=[
                PatchOperation(
                    kind="create_node", target=root, args={"op_type": "constantCHOP", "name": "host"}
                )
            ],
        )
        result = await apply_plan(client, plan, sentinel=UndoBlockSentinel(), auto_validate=False)
        check(
            "host_uses_native_receipt",
            result.status == "clean" and bool(result.native_receipt),
            result.model_dump(mode="json"),
        )
        check("host_rollback", (await client.request("patch/rollback", result.native_receipt)).get("ok"))

        # Simulate an HTTP result lost after TD committed. Recovery must look up
        # the exact receipt, never send a fresh transaction or a blind undo.
        class LostResponseClient(TDClient):
            async def request(self, endpoint, body=None):
                response = await super().request(endpoint, body)
                if endpoint == "patch/apply":
                    raise TimeoutError("deliberately dropped committed response")
                return response

        lost_client = LostResponseClient()
        try:
            lost_result = await apply_plan(
                lost_client, plan, sentinel=UndoBlockSentinel(), auto_validate=False
            )
            check(
                "lost_response_recovered",
                lost_result.native_rollback and lost_result.native_rollback.get("ok"),
                lost_result.model_dump(mode="json"),
            )
            check(
                "lost_response_leaves_no_node",
                root + "/host"
                not in [n["path"] for n in (await client.request("nodes", {"path": root}))["nodes"]],
            )
        finally:
            await lost_client.close()

        macro_plan = plan.model_copy(
            update={
                "operations": [
                    PatchOperation(
                        kind="macro",
                        target=root,
                        args={"macro_type": "feedback_loop", "name_prefix": "macro"},
                    )
                ]
            }
        )
        macro = await apply_plan(
            client,
            macro_plan,
            sentinel=UndoBlockSentinel(),
            auto_validate=False,
            macro_engine=MacroEngine(client),
        )
        check("native_macro_expansion", macro.status == "clean", macro.model_dump(mode="json"))
        check(
            "native_macro_rollback", (await client.request("patch/rollback", macro.native_receipt)).get("ok")
        )
        contract = ValidationContract(
            target_root=root,
            output_path=root + "/host",
            graph_assertions=[
                ValidationAssertion(
                    id="deliberate-missing-output",
                    kind="exists",
                    target=root + "/never_created",
                    probe="node_query",
                    comparator="exists",
                    expected=True,
                )
            ],
        )
        transaction = await apply_transaction(
            client,
            plan,
            sentinel=UndoBlockSentinel(),
            options=TransactionOptions(preflight=False, snapshot_before=False),
            validation_contract=contract,
        )
        check(
            "validation_failure_rolls_back",
            transaction.status == "rolled_back"
            and transaction.rollback_verification.get("ok")
            and not transaction.needs_manual_recovery,
            transaction.model_dump(mode="json"),
        )

        # Setup is our own retained block, safe to roll back only after guards pass.
        check("setup_cleanup_undo", (await rollback(prior_body)).get("ok"))
        report["ok"] = True
    except Exception as exc:
        report["failure"] = str(exc)
    finally:
        if root:
            report["cleanup"] = await client.request("node/delete", {"path": root})
            remaining = await client.request("nodes", {"path": "/project1"})
            report["cleanup_verified"] = root not in [n["path"] for n in remaining["nodes"]]
        report["project_errors"] = await client.request("node/errors", {"path": "/project1"})
        await client.close()
    return report


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = await qualify()
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "checks": len(report["checks"]),
                "cleanup_verified": report["cleanup_verified"],
            }
        )
    )
    if not report["ok"]:
        raise SystemExit(report.get("failure", "qualification failed"))


if __name__ == "__main__":
    asyncio.run(main())
