#!/usr/bin/env python3
"""Live 2025.33230 qualification in an owned, disposable component.

Checks transaction preflight, expression readback, numerical clamp behavior and
a Time Filter POP preview. Does not change the active project's output route.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from td_mcp.brain.intent_coverage import control_binding_operation
from td_mcp.brain.param_semantics import validate_patch_plan_parameter_contract
from td_mcp.brain.transaction import apply_transaction
from td_mcp.brain.validation_engine import validate_contract
from td_mcp.models.brain import ConceptEdge, TransactionOptions
from td_mcp.models.build import ValidationAssertion, ValidationContract
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.undo_sentinel import UndoBlockSentinel
from td_mcp.report_identity import stamp_report_identity
from td_mcp.td_client import TDClient

TARGETS = [
    ("camera", "cameraCOMP", "tx", (-2.0, 2.0)),
    ("material", "phongMAT", "diffr", (0.0, 1.0)),
    ("particles", "particlePOP", "birthrate", (0.0, 100.0)),
    ("noise", "noisePOP", "amp0", (0.0, 1.0)),
]


def qualification_plan(root: str) -> tuple[PatchPlan, ValidationContract]:
    nodes = [
        ("signal", "constantCHOP"),
        ("source", "circlePOP"),
        *[(name, op_type) for name, op_type, _, _ in TARGETS],
        ("filter", "timefilterPOP"),
        ("particle_state", "nullPOP"),
        ("preview", "rendersimpleTOP"),
        ("out1", "nullTOP"),
    ]
    operations = [
        PatchOperation(kind="create_node", target=root, args={"op_type": op_type, "name": name})
        for name, op_type in nodes
    ]
    assertions = []
    for name, op_type, parameter, bounds in TARGETS:
        edge = ConceptEdge(
            source="signal",
            target=name,
            kind="control",
            binding={
                "target_param": parameter,
                "source_channel": 0,
                "scale": 2,
                "offset": 0.25,
                "output_range": bounds,
            },
        )
        key, value = control_binding_operation(
            edge,
            source_op_type="constantCHOP",
            target_op_type=op_type,
            source_path=root + "/signal",
            target_path=root + "/" + name,
            target_params={},
        )
        operations.append(
            PatchOperation(kind="set_params", target=root + "/" + name, args={"params": {key: value}})
        )
        assertions.append(
            ValidationAssertion(
                id="binding:" + name,
                kind="binding_readback",
                comparator="eq",
                target=root + "/" + name,
                probe="param_query",
                expected={"param": parameter, **value},
            )
        )
    for source, target in [
        ("source", "particles"),
        ("particles", "particle_state"),
        ("source", "noise"),
        ("noise", "filter"),
        ("preview", "out1"),
    ]:
        operations.append(
            PatchOperation(kind="connect", args={"from": root + "/" + source, "to": root + "/" + target})
        )
    operations.extend(
        [
            PatchOperation(
                kind="set_params",
                target=root + "/particles",
                args={"params": {"targetpop": root + "/particle_state"}},
            ),
            PatchOperation(
                kind="set_params",
                target=root + "/filter",
                args={"params": {"filtertype": "gaussian", "attrs": "P", "width": 2, "widthunit": "frames"}},
            ),
            PatchOperation(
                kind="set_params",
                target=root + "/preview",
                args={"params": {"pop": root + "/filter", "normalizegeo": True}},
            ),
        ]
    )
    plan = PatchPlan(
        intent="Qualify bounded controls and Time Filter POP",
        target_root=root,
        source="operations",
        operations=operations,
        undo_label="TDPilot control qualification",
        validation_plan=ValidationPlan(target_root=root),
    )
    contract = ValidationContract(target_root=root, output_path=root + "/out1", runtime_assertions=assertions)
    return plan, contract


async def qualify(parent_path: str) -> dict:
    client = TDClient(max_retries=0)
    root = None
    report = {"ok": False, "cleanup_ok": False}
    try:
        report["info"] = await client.request("info")
        created = await client.request(
            "node/create",
            {
                "parent_path": parent_path,
                "node_type": "baseCOMP",
                "name": "tdpilot_controls_" + uuid.uuid4().hex[:10],
            },
        )
        confirmed = (created.get("node") or {}).get("path", "")
        if not confirmed or confirmed.rsplit("/", 1)[0] != parent_path.rstrip("/"):
            raise RuntimeError("Could not confirm scratch ownership")
        root = confirmed
        plan, contract = qualification_plan(root)
        issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)
        if issues:
            raise RuntimeError(str([item.model_dump() for item in issues]))
        result = await apply_transaction(
            client,
            plan,
            options=TransactionOptions(
                snapshot_before=False, rollback_on_apply_failure=False, rollback_on_validation_failure=False
            ),
            sentinel=UndoBlockSentinel(),
            validation_contract=contract,
        )
        report["transaction"] = result.model_dump(mode="json")
        if result.status not in {"clean", "warnings"} or result.validation_failed:
            raise RuntimeError("Qualification transaction did not validate")
        for pulse in ("initializepulse", "startpulse"):
            pulsed = await client.request("pulse", {"path": root + "/particles", "param": pulse})
            if pulsed.get("success") is not True:
                raise RuntimeError("Particle lifecycle pulse was not confirmed: " + str(pulsed))
        source = await client.request("node/params", {"path": root + "/signal", "names": ["const0value"]})
        if "const0value" not in source.get("parameters", {}):
            raise RuntimeError("Constant CHOP does not expose const0value")
        samples = []
        for signal in (-10.0, 0.0, 0.25, 100.0):
            changed = await client.request(
                "node/params/set", {"path": root + "/signal", "params": {"const0value": signal}}
            )
            if changed.get("error") or changed.get("success") is False:
                raise RuntimeError(str(changed))
            await asyncio.sleep(0.1)
            for name, _, parameter, (low, high) in TARGETS:
                readback = await client.request(
                    "node/params", {"path": root + "/" + name, "names": [parameter]}
                )
                actual = readback["parameters"][parameter]["value"]
                expected = min(high, max(low, signal * 2 + 0.25))
                samples.append(
                    {
                        "target": name,
                        "parameter": parameter,
                        "source": signal,
                        "actual": actual,
                        "expected": expected,
                        "ok": math.isclose(actual, expected, abs_tol=1e-6),
                    }
                )
        report["samples"] = samples
        report["binding_readback"] = (await validate_contract(client, contract)).model_dump(mode="json")
        report["visual"] = await client.request(
            "analyze_frame", {"path": root + "/out1", "modes": ["luminance"]}
        )
        report["particle_state"] = await client.request(
            "pop/inspect", {"path": root + "/particle_state", "count": 1, "delayed": False}
        )
        report["errors"] = await client.request("node/errors", {"path": root, "recurse": True})
        if report["errors"].get("issues"):
            report["particle_connections"] = await client.request(
                "node/connections", {"path": root + "/particles"}
            )
            report["particle_params"] = await client.request(
                "node/params",
                {"path": root + "/particles", "names": ["targetpop", "maxparticles", "preroll"]},
            )
        luminance = report["visual"].get("modes", {}).get("luminance", {})
        report["ok"] = (
            all(s["ok"] for s in samples)
            and report["binding_readback"]["ok"]
            and float(luminance.get("max", 0)) > 0
            and not report["errors"].get("issues")
        )
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        if root:
            try:
                deleted = await client.request("node/delete", {"path": root})
                report["cleanup_ok"] = deleted.get("success") is True
            except Exception as exc:
                report["cleanup_error"] = str(exc)
        await client.close()
    report["ok"] = report["ok"] and report["cleanup_ok"]
    return stamp_report_identity(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--parent-path", default="/project1")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = asyncio.run(qualify(args.parent_path))
    serialized = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    print(serialized)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
