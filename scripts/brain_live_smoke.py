#!/usr/bin/env python3
"""Run TDPilot brain live-smoke scenario planning."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from td_mcp.brain.live_smoke import build_live_smoke_report  # noqa: E402


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
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = "live" if args.live else "dry_run"
    report = asyncio.run(
        build_live_smoke_report(
            mode=mode,
            host=args.host,
            port=args.port,
            timeout=args.timeout,
        )
    )
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
