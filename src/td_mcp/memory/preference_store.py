"""Simple key-value preference store with per-project and global scope."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


DEFAULT_BASE_DIR = "~/.tdpilot/memory"


class PreferenceStore:
    """Key-value preferences with project + global scope and JSON persistence."""

    def __init__(self, base_dir: str | None = None, project_name: str | None = None):
        self._base = Path(base_dir or DEFAULT_BASE_DIR).expanduser()
        self._project_name = project_name
        self._global_dir = self._base / "global"
        self._project_dir: Path | None = None
        if project_name:
            safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
            self._project_dir = self._base / "projects" / safe_name

        self._global_dir.mkdir(parents=True, exist_ok=True)
        if self._project_dir:
            self._project_dir.mkdir(parents=True, exist_ok=True)

        self._global: dict[str, Any] = {}
        self._project: dict[str, Any] = {}
        self._load()

    def set(self, key: str, value: Any, scope: str = "project") -> None:
        store = self._store_for(scope)
        store[key] = value
        self._save_scope(scope)

    def get(self, key: str, scope: str = "project", default: Any = None) -> Any:
        store = self._store_for(scope)
        return store.get(key, default)

    def list_all(self, scope: str = "project") -> dict[str, Any]:
        return dict(self._store_for(scope))

    def delete(self, key: str, scope: str = "project") -> bool:
        store = self._store_for(scope)
        if key not in store:
            return False
        del store[key]
        self._save_scope(scope)
        return True

    def stats(self) -> dict[str, Any]:
        return {
            "global_count": len(self._global),
            "project_count": len(self._project),
            "project_name": self._project_name,
        }

    # ------------------------------------------------------------------
    # Lazy rebinding — used when the TDPilot server starts before TD is
    # reachable. See _ensure_project_scope in tool_registry.py.
    # ------------------------------------------------------------------

    def rebind_project_scope(self, project_name: str) -> None:
        """Re-target this store at a new project folder without a restart.

        Replaces _project_name / _project_dir, creates the directory,
        drops the in-memory project cache, and reloads from disk.
        Existing global data is untouched.
        """
        if not project_name:
            return
        safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
        self._project_name = project_name
        self._project_dir = self._base / "projects" / safe_name
        self._project_dir.mkdir(parents=True, exist_ok=True)
        self._project = self._load_file(self._project_dir / "preferences.json")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _store_for(self, scope: str) -> dict[str, Any]:
        if scope == "global":
            return self._global
        return self._project

    def _load(self) -> None:
        self._global = self._load_file(self._global_dir / "preferences.json")
        if self._project_dir:
            self._project = self._load_file(self._project_dir / "preferences.json")

    def _load_file(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def _save_scope(self, scope: str) -> None:
        if scope == "global":
            self._write_file(self._global_dir / "preferences.json", self._global)
        elif scope == "project":
            if not self._project_dir:
                raise ValueError(
                    "Cannot save project-scoped data: TDPILOT_PROJECT_NAME is not set. "
                    "Set the environment variable or use scope='global'."
                )
            self._write_file(self._project_dir / "preferences.json", self._project)

    def _write_file(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        try:
            # sort_keys=True: byte-stable output preserves prompt-cache prefix hits.
            # Two stores reaching the same final state via different insertion orders
            # must produce identical bytes on disk (test_memory_byte_stability.py).
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(path)
        except Exception as exc:
            logger.error("Failed to write %s: %s", path, exc)
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
