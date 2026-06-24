#!/usr/bin/env python3
"""Diagnose local package, plugin, live TD component, and auth-secret sync."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from td_mcp.auth_bootstrap import bootstrap_auth, default_env_file  # noqa: E402
from td_mcp.sync_diagnostics import diagnose_sync  # noqa: E402
from td_mcp.td_client import TDClient  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Probe the live TouchDesigner WebServer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9981)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


async def _main_async(args: argparse.Namespace) -> dict:
    env_file = default_env_file()
    bootstrap_auth(env_file)
    client = TDClient(host=args.host, port=args.port, timeout=args.timeout) if args.live else None
    try:
        return await diagnose_sync(
            client=client,
            host=args.host,
            port=args.port,
            include_live=args.live,
        )
    finally:
        if client is not None:
            await client.close()


def main() -> int:
    args = _parse_args()
    report = asyncio.run(_main_async(args))
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
