"""Parameter safety bounds and rate-limiting."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class Bound:
    min_val: float | None = None
    max_val: float | None = None
    max_rate: float | None = None


class SafetyManager:
    """Stores per-parameter bounds and enforces them on writes."""

    def __init__(self):
        self._bounds: dict[str, Bound] = {}
        self._last_values: dict[str, tuple[float, float]] = {}
        self._mode = "clamp"

    def set_mode(self, mode: str) -> None:
        if mode not in {"clamp", "reject", "warn"}:
            raise ValueError("enforce_mode must be one of: clamp, reject, warn")
        self._mode = mode

    def get_mode(self) -> str:
        return self._mode

    def set_bound(
        self,
        key: str,
        *,
        min_val: float | None,
        max_val: float | None,
        max_rate: float | None,
    ) -> None:
        self._bounds[key] = Bound(min_val=min_val, max_val=max_val, max_rate=max_rate)

    def clear_bound(self, key: str) -> bool:
        return self._bounds.pop(key, None) is not None

    def clear_all(self) -> int:
        count = len(self._bounds)
        self._bounds.clear()
        return count

    def list_bounds(self) -> dict[str, dict[str, float | None]]:
        return {
            key: {"min_val": b.min_val, "max_val": b.max_val, "max_rate": b.max_rate}
            for key, b in self._bounds.items()
        }

    def stats(self) -> dict[str, object]:
        return {
            "mode": self._mode,
            "bounds_count": len(self._bounds),
            "tracked_values": len(self._last_values),
        }

    def apply(self, key: str, value: float) -> tuple[float, str | None]:
        bound = self._bounds.get(key)
        if not bound:
            return value, None

        warning = None
        mode = self._mode

        if bound.min_val is not None and value < bound.min_val:
            if mode == "reject":
                raise ValueError(f"{key}={value} below min bound {bound.min_val}")
            warning = f"{key} below min bound {bound.min_val}"
            if mode == "clamp":
                value = bound.min_val

        if bound.max_val is not None and value > bound.max_val:
            if mode == "reject":
                raise ValueError(f"{key}={value} above max bound {bound.max_val}")
            warning = f"{key} above max bound {bound.max_val}"
            if mode == "clamp":
                value = bound.max_val

        if bound.max_rate is not None and key in self._last_values:
            prev_value, prev_ts = self._last_values[key]
            now = time.time()
            dt = now - prev_ts
            if dt > 0:
                max_delta = bound.max_rate * dt
                requested_delta = value - prev_value
                if abs(requested_delta) > max_delta:
                    if mode == "reject":
                        raise ValueError(
                            f"{key} violates rate bound {bound.max_rate}/s (delta={requested_delta}, dt={dt})"
                        )
                    warning = f"{key} rate-limited to {bound.max_rate}/s"
                    if mode == "clamp":
                        direction = 1.0 if requested_delta > 0 else -1.0
                        value = prev_value + direction * max_delta

        self._last_values[key] = (float(value), time.time())
        return value, warning
