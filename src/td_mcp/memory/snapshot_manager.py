"""Scene snapshot manager with optional disk persistence."""

from __future__ import annotations

import copy
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SnapshotManager:
    """Stores project snapshots, computes diffs, and optionally persists to disk."""

    def __init__(self, max_snapshots: int = 50, storage_dir: str | None = None):
        self._max_snapshots = max_snapshots
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []
        self._storage_dir: Path | None = None

        if storage_dir:
            self._storage_dir = Path(storage_dir).expanduser()
            self._storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def add_snapshot(self, snapshot: dict[str, Any], name: str | None = None) -> dict[str, Any]:
        snapshot_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "snapshot_schema_version": 1,
            "snapshot_id": snapshot_id,
            "name": name or f"snapshot_{snapshot_id[:8]}",
            "timestamp": now,
            "snapshot": copy.deepcopy(snapshot),
        }
        self._snapshots[snapshot_id] = payload
        self._order.append(snapshot_id)
        self._persist_snapshot(payload)
        self._trim()
        return payload

    def list_snapshots(self, limit: int = 20) -> list[dict[str, Any]]:
        ids = list(reversed(self._order))[:limit]
        result = []
        for snapshot_id in ids:
            item = self._snapshots[snapshot_id]
            snap = item["snapshot"]
            result.append(
                {
                    "snapshot_id": item["snapshot_id"],
                    "name": item["name"],
                    "timestamp": item["timestamp"],
                    "node_count": len(snap.get("nodes", {})),
                    "connection_count": len(snap.get("connections", [])),
                }
            )
        return result

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        item = self._snapshots.get(snapshot_id)
        if item:
            return item
        if not self._storage_dir:
            return None
        loaded = self._load_snapshot_file(self._snapshot_file(snapshot_id))
        if loaded:
            self._snapshots[snapshot_id] = loaded
            if snapshot_id not in self._order:
                self._order.append(snapshot_id)
                self._order.sort(key=self._order_timestamp_key)
            self._trim()
        return loaded

    def stats(self) -> dict[str, Any]:
        return {
            "count": len(self._order),
            "max_snapshots": self._max_snapshots,
            "persistence_enabled": self._storage_dir is not None,
            "storage_dir": str(self._storage_dir) if self._storage_dir else None,
        }

    def diff(
        self,
        snapshot_a: dict[str, Any],
        snapshot_b: dict[str, Any],
    ) -> dict[str, Any]:
        nodes_a = snapshot_a.get("nodes", {})
        nodes_b = snapshot_b.get("nodes", {})

        changed_params: list[dict[str, Any]] = []
        added_expressions: list[dict[str, Any]] = []
        removed_expressions: list[dict[str, Any]] = []
        modified_expressions: list[dict[str, Any]] = []

        for path, node_a in nodes_a.items():
            node_b = nodes_b.get(path)
            if not node_b:
                continue
            params_a = node_a.get("params", node_a.get("parameters", {}))
            params_b = node_b.get("params", node_b.get("parameters", {}))
            for param_name, param_a in params_a.items():
                if param_name not in params_b:
                    continue
                param_b = params_b[param_name]
                # Handle plain scalar params (not dicts)
                if not isinstance(param_a, dict) or not isinstance(param_b, dict):
                    if param_a != param_b:
                        changed_params.append(
                            {
                                "path": path,
                                "param": param_name,
                                "value_a": param_a if not isinstance(param_a, dict) else param_a.get("value"),
                                "value_b": param_b if not isinstance(param_b, dict) else param_b.get("value"),
                            }
                        )
                    continue
                value_a = param_a.get("value")
                value_b = param_b.get("value")
                if value_a != value_b:
                    changed_params.append(
                        {
                            "path": path,
                            "param": param_name,
                            "value_a": value_a,
                            "value_b": value_b,
                        }
                    )
                # Expression diff
                expr_a = param_a.get("expression")
                expr_b = param_b.get("expression")
                if expr_a != expr_b:
                    if expr_a is None and expr_b is not None:
                        added_expressions.append({"path": path, "param": param_name, "expression": expr_b})
                    elif expr_a is not None and expr_b is None:
                        removed_expressions.append({"path": path, "param": param_name, "expression": expr_a})
                    else:
                        modified_expressions.append(
                            {
                                "path": path,
                                "param": param_name,
                                "expression_a": expr_a,
                                "expression_b": expr_b,
                            }
                        )

        added_nodes = sorted(set(nodes_b.keys()) - set(nodes_a.keys()))
        removed_nodes = sorted(set(nodes_a.keys()) - set(nodes_b.keys()))

        # Connection diff — normalize each connection as a comparable tuple
        def _conn_tuple(c: Any) -> tuple:
            return (
                c.get("from", ""),
                c.get("to", ""),
                c.get("from_index", 0),
                c.get("to_index", 0),
            )

        conns_a = {_conn_tuple(c) for c in snapshot_a.get("connections", [])}
        conns_b = {_conn_tuple(c) for c in snapshot_b.get("connections", [])}
        added_connections = sorted(conns_b - conns_a)
        removed_connections = sorted(conns_a - conns_b)

        total_expr = len(added_expressions) + len(removed_expressions) + len(modified_expressions)

        return {
            "changed_params": changed_params,
            "added_nodes": added_nodes,
            "removed_nodes": removed_nodes,
            "added_connections": added_connections,
            "removed_connections": removed_connections,
            "added_expressions": added_expressions,
            "removed_expressions": removed_expressions,
            "modified_expressions": modified_expressions,
            "summary": (
                f"{len(changed_params)} params changed, "
                f"{len(added_nodes)} nodes added, "
                f"{len(removed_nodes)} nodes removed, "
                f"{len(added_connections)} connections added, "
                f"{len(removed_connections)} connections removed, "
                f"{total_expr} expression changes."
            ),
        }

    def _trim(self) -> None:
        while len(self._order) > self._max_snapshots:
            oldest = self._order.pop(0)
            self._snapshots.pop(oldest, None)
            self._delete_snapshot_file(oldest)

    def _load_from_disk(self) -> None:
        if self._storage_dir is None:
            raise RuntimeError("_load_from_disk called without a storage directory")
        loaded: list[dict[str, Any]] = []
        for path in sorted(self._storage_dir.glob("*.json")):
            item = self._load_snapshot_file(path)
            if item:
                loaded.append(item)

        loaded.sort(key=lambda item: str(item.get("timestamp", "")))
        for item in loaded:
            snapshot_id = item["snapshot_id"]
            self._snapshots[snapshot_id] = item
            self._order.append(snapshot_id)
        self._trim()

    def _snapshot_file(self, snapshot_id: str) -> Path:
        if self._storage_dir is None:
            raise RuntimeError("_snapshot_file called without a storage directory")
        return self._storage_dir / f"{snapshot_id}.json"

    def _persist_snapshot(self, payload: dict[str, Any]) -> None:
        if not self._storage_dir:
            return
        file_path = self._snapshot_file(payload["snapshot_id"])
        tmp_path = file_path.with_suffix(".json.tmp")
        try:
            tmp_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
            tmp_path.replace(file_path)
        except Exception as exc:
            logger.error("Failed to write %s: %s", file_path, exc)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    def _load_snapshot_file(self, file_path: Path) -> dict[str, Any] | None:
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        snapshot_id = data.get("snapshot_id")
        snapshot = data.get("snapshot")
        if not isinstance(snapshot_id, str) or not isinstance(snapshot, dict):
            return None
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
        if "name" not in data:
            data["name"] = f"snapshot_{snapshot_id[:8]}"
        data.setdefault("snapshot_schema_version", 1)
        return data

    def _delete_snapshot_file(self, snapshot_id: str) -> None:
        if not self._storage_dir:
            return
        file_path = self._snapshot_file(snapshot_id)
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception:
            return

    def _order_timestamp_key(self, snapshot_id: str) -> str:
        item = self._snapshots.get(snapshot_id, {})
        return str(item.get("timestamp", ""))
