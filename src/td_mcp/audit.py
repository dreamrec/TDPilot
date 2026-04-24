"""Simple JSONL audit logger for write operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    """Append-only audit logging with best-effort failure tolerance."""

    def __init__(self, file_path: str | None = None):
        self._file_path = Path(file_path).expanduser() if file_path else None
        if self._file_path:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)

    def enabled(self) -> bool:
        return self._file_path is not None

    def log(self, event: str, details: dict[str, Any]) -> None:
        if not self._file_path:
            return

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details,
        }
        try:
            with self._file_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=True))
                fh.write("\n")
        except Exception:
            # Audit failures must never break user operations.
            return
