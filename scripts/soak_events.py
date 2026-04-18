#!/usr/bin/env python3
"""Synthetic TD event flood / reconnect soak test for the MCP event channel."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets


def percentile(values: list[float], p: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if p <= 0:
        return ordered[0]
    if p >= 100:
        return ordered[-1]
    pos = (len(ordered) - 1) * (p / 100.0)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    w = pos - lo
    return ordered[lo] * (1.0 - w) + ordered[hi] * w


async def connect_with_timing(ws_url: str, timeout: float) -> tuple[Any, float]:
    started = time.perf_counter()
    ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=timeout)
    elapsed = (time.perf_counter() - started) * 1000.0
    return ws, elapsed


async def run_soak(args: argparse.Namespace) -> dict[str, Any]:
    interval = 60.0 / float(args.events_per_min)
    started = time.perf_counter()
    deadline = started + float(args.duration_sec)

    sent_ok = 0
    send_errors = 0
    attempted = 0
    reconnect_ms: list[float] = []
    event_latency_ms: list[float] = []

    ws, reconnect_cost = await connect_with_timing(args.ws_url, args.connect_timeout)
    reconnect_ms.append(reconnect_cost)
    connection_started = time.perf_counter()

    seq = 0
    while time.perf_counter() < deadline:
        now = time.time()
        event = {
            "type": args.event_type,
            "timestamp": now,
            "data": {
                "path": args.path,
                "channel": args.channel,
                "name": args.param,
                "value": float(seq % 100) / 100.0,
                "seq": seq,
            },
        }

        if args.reconnect_every_sec > 0:
            elapsed_conn = time.perf_counter() - connection_started
            if elapsed_conn >= args.reconnect_every_sec:
                try:
                    await ws.close()
                except Exception:
                    pass
                ws, reconnect_cost = await connect_with_timing(args.ws_url, args.connect_timeout)
                reconnect_ms.append(reconnect_cost)
                connection_started = time.perf_counter()

        attempted += 1
        send_started = time.perf_counter()
        try:
            await ws.send(json.dumps(event, separators=(",", ":")))
            sent_ok += 1
            event_latency_ms.append((time.perf_counter() - send_started) * 1000.0)
        except Exception:
            send_errors += 1
            try:
                await ws.close()
            except Exception:
                pass
            ws, reconnect_cost = await connect_with_timing(args.ws_url, args.connect_timeout)
            reconnect_ms.append(reconnect_cost)
            connection_started = time.perf_counter()

        seq += 1
        await asyncio.sleep(max(0.0, interval))

    try:
        await ws.close()
    except Exception:
        pass

    elapsed = time.perf_counter() - started
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": {"ws_url": args.ws_url},
        "config": {
            "duration_sec": args.duration_sec,
            "events_per_min": args.events_per_min,
            "event_type": args.event_type,
            "path": args.path,
            "reconnect_every_sec": args.reconnect_every_sec,
        },
        "results": {
            "elapsed_sec": elapsed,
            "attempted": attempted,
            "sent_ok": sent_ok,
            "send_errors": send_errors,
            "drop_rate_pct": ((attempted - sent_ok) / attempted * 100.0) if attempted else 0.0,
            "effective_events_per_min": (sent_ok / elapsed) * 60.0 if elapsed > 0 else 0.0,
            "send_latency_ms": {
                "mean": statistics.fmean(event_latency_ms) if event_latency_ms else math.nan,
                "p95": percentile(event_latency_ms, 95),
                "p99": percentile(event_latency_ms, 99),
            },
            "reconnect_ms": {
                "count": len(reconnect_ms),
                "median": percentile(reconnect_ms, 50),
                "p95": percentile(reconnect_ms, 95),
                "max": max(reconnect_ms) if reconnect_ms else math.nan,
            },
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synthetic MCP event soak test")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:9982")
    parser.add_argument("--duration-sec", type=int, default=300)
    parser.add_argument("--events-per-min", type=int, default=1000)
    parser.add_argument("--event-type", default="chop_change")
    parser.add_argument("--path", default="/project1/audio1")
    parser.add_argument("--channel", default="chan1")
    parser.add_argument("--param", default="value0")
    parser.add_argument("--reconnect-every-sec", type=int, default=0)
    parser.add_argument("--connect-timeout", type=float, default=5.0)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = asyncio.run(run_soak(args))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    output = json.dumps(report, indent=2)
    print(output)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
