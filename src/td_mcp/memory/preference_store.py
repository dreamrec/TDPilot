"""Simple key-value preference store with per-project and global scope."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_BASE_DIR = "~/.tdpilot/memory"


class PreferenceStore:
    """Key-value preferences with project + global scope and JSON persistence."""

    def __init__(self, base_dir: str | None = None, project_name: str | None = None):
        self._base = Path(base_dir or DEFAULT_BASE_DIR).expanduser()
        self._project_name = project_name
        self._global_dir = self._base / "global"
        self._project_dir: Optional[Path] = None
        if project_name:
            safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
            self._project_dir = self._base / "projects" / safe_name

        self._global_dir.mkdir(parents=True, exist_ok=True)
        if self._project_dir:
            self._project_dir.mkdir(parents=True, exist_ok=True)

        self._global: Dict[str, Any] = {}
        self._project: Dict[str, Any] = {}
        self._load()

    def set(self, key: str, value: Any, scope: str = "project") -> None:
        store = self._store_for(scope)
        store[key] = value
        self._save_scope(scope)

    def get(self, key: str, scope: str = "project", default: Any = None) -> Any:
        store = self._store_for(scope)
        return store.get(key, default)

    def list_all(self, scope: str = "project") -> Dict[str, Any]:
        return dict(self._store_for(scope))

    def delete(self, key: str, scope: str = "project") -> bool:
        store = self._store_for(scope)
        if key not in store:
            return False
        del store[key]
        self._save_scope(scope)
        return True

    def stats(self) -> Dict[str, Any]:
        return {
            "global_count": len(self._global),
            "project_count": len(self._project),
            "project_name": self._project_name,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _store_for(self, scope: str) -> Dict[str, Any]:
        if scope == "global":
            return self._global
        return self._project

    def _load(self) -> None:
        self._global = self._load_file(self._global_dir / "preferences.json")
        if self._project_dir:
            self._project = self._load_file(self._project_dir / "preferences.json")

    def _load_file(self, path: Path) -> Dict[str, Any]:
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
        elif self._project_dir:
            self._write_file(self._project_dir / "preferences.json", self._project)

    def _write_file(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
