"""Lightweight in-process telemetry collector."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class TelemetryCollector:
    """Tracks counters and latency snapshots for server diagnostics."""

    counters: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int))
    latency_ms: defaultdict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _lock: Lock = field(default_factory=Lock)

    def increment(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[key] += amount

    def record_latency(self, tool_name: str, elapsed_ms: float) -> None:
        with self._lock:
            samples = self.latency_ms[tool_name]
            samples.append(elapsed_ms)
            # Keep bounded memory. We only need recent trend, not full history.
            if len(samples) > 5000:
                del samples[: len(samples) - 5000]

    def timed(self, tool_name: str):
        start = time.perf_counter()

        def finish() -> None:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.record_latency(tool_name, elapsed_ms)

        return finish

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            avg_latency = {
                name: (sum(values) / len(values)) if values else 0.0
                for name, values in self.latency_ms.items()
            }
            return {
                "counters": dict(self.counters),
                "latency_avg_ms": avg_latency,
            }
