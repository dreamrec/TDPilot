#!/usr/bin/env python3
"""Sample live TouchDesigner operator createability for atlas gap review."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from td_mcp.brain.atlas_audit import audit_brain_atlas  # noqa: E402
from td_mcp.brain.operator_availability import (  # noqa: E402
    build_availability_targets,
    sample_operator_availability,
)
from td_mcp.td_client import TDClient  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample live operator availability for atlas gaps.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9981)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--parent-path", default="/project1")
    parser.add_argument("--scratch-name", default="tdpilot_availability_probe")
    parser.add_argument("--out", default="")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> dict:
    atlas_report = audit_brain_atlas(ROOT)
    targets = build_availability_targets(atlas_report)
    client = TDClient(host=args.host, port=args.port, timeout=args.timeout, max_retries=1)
    report = await sample_operator_availability(
        client,
        targets,
        parent_path=args.parent_path,
        scratch_name=args.scratch_name,
    )
    report["atlas_summary"] = {
        "card_count": atlas_report["card_count"],
        "structured_operator_card_count": atlas_report["docsbrain_operator_coverage"][
            "structured_operator_card_count"
        ],
        "deprecated_missing_operator_card_count": len(
            atlas_report["docsbrain_operator_coverage"]["deprecated_missing_operator_cards"]
        ),
        "priority_missing_operator_card_count": len(
            atlas_report["docsbrain_operator_coverage"]["priority_missing_operator_cards"]
        ),
    }
    return report


def main() -> int:
    args = parse_args()
    try:
        report = asyncio.run(main_async(args))
    except Exception as exc:  # noqa: BLE001 - CLI should produce machine-readable failure.
        report = {
            "schema_version": 1,
            "ok": False,
            "error": str(exc),
        }

    output = json.dumps(report, indent=2 if args.pretty else None, sort_keys=args.pretty)
    print(output)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
