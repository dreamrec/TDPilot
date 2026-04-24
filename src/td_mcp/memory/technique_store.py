"""Technique library with per-project and global scope, JSON persistence."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


DEFAULT_BASE_DIR = "~/.tdpilot/memory"


class TechniqueStore:
    """CRUD for reusable TD network recipes with search, ratings, and promotion."""

    def __init__(self, base_dir: str | None = None, project_name: str | None = None):
        self._base = Path(base_dir or DEFAULT_BASE_DIR).expanduser()
        self._project_name = project_name
        self._global_dir = self._base / "global"
        self._project_dir: Path | None = None
        if project_name:
            safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
            self._project_dir = self._base / "projects" / safe_name

        # Ensure directories exist
        self._global_dir.mkdir(parents=True, exist_ok=True)
        if self._project_dir:
            self._project_dir.mkdir(parents=True, exist_ok=True)

        # In-memory caches keyed by technique id
        self._global: dict[str, dict[str, Any]] = {}
        self._project: dict[str, dict[str, Any]] = {}

        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # Valid state transitions
    _VALID_STATES = frozenset(
        {
            "candidate",
            "validated_local",
            "validated_portable",
            "deprecated",
        }
    )

    def add(
        self,
        technique: dict[str, Any],
        scope: str = "project",
        *,
        name: str = "",
        description: str = "",
        tags: list[str] | None = None,
        notes: str = "",
        compatibility: dict[str, Any] | None = None,
    ) -> str:
        """Add a technique and return its id."""
        technique_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        entry: dict[str, Any] = {
            "id": technique_id,
            "name": name or f"technique_{technique_id[:8]}",
            "description": description,
            "tags": sorted(set(t.lower() for t in (tags or []))),
            "notes": notes,
            "created_at": now,
            "updated_at": now,
            "favorite": False,
            "rating": 0,
            "state": "candidate",
            "validation_result": None,
            "replay_count": 0,
            "last_replayed_at": None,
            "compatibility": compatibility or {},
            "technique": technique,
        }
        store = self._store_for(scope)
        store[technique_id] = entry
        self._save_scope(scope)
        return technique_id

    def get(self, technique_id: str, scope: str = "project") -> dict[str, Any] | None:
        """Return a single technique by id, or None."""
        store = self._store_for(scope)
        return store.get(technique_id)

    def search(
        self,
        query: str = "",
        tags: list[str] | None = None,
        scope: str = "all",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search techniques by text query and/or tags. Returns summaries (no full recipe)."""
        results: list[dict[str, Any]] = []
        stores = self._stores_for_scope(scope)
        query_lower = query.lower()
        tag_set = set(tags or [])

        for store_scope, store in stores:
            for entry in store.values():
                # Tag filter
                if tag_set and not tag_set.intersection(entry.get("tags", [])):
                    continue
                # Text search across name, description, tags, notes
                if query_lower:
                    haystack = " ".join(
                        [
                            entry.get("name", ""),
                            entry.get("description", ""),
                            " ".join(entry.get("tags", [])),
                            entry.get("notes", ""),
                        ]
                    ).lower()
                    if query_lower not in haystack:
                        continue
                results.append(self._summary(entry, store_scope))

        # Sort: favorites first, then by rating desc, then most replayed, then newest
        results.sort(
            key=lambda r: (
                not r.get("favorite", False),
                -(r.get("rating", 0)),
                -(r.get("replay_count", 0)),
                r.get("created_at", ""),
            )
        )
        return results[:limit]

    def list_techniques(
        self,
        scope: str = "all",
        tags: list[str] | None = None,
        favorites_only: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List technique summaries with optional filtering."""
        results: list[dict[str, Any]] = []
        stores = self._stores_for_scope(scope)
        tag_set = set(tags or [])

        for store_scope, store in stores:
            for entry in store.values():
                if favorites_only and not entry.get("favorite"):
                    continue
                if tag_set and not tag_set.intersection(entry.get("tags", [])):
                    continue
                results.append(self._summary(entry, store_scope))

        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results[:limit]

    def record_replay(self, technique_id: str, scope: str = "project") -> bool:
        """Increment replay_count and set last_replayed_at. Returns True on success."""
        store = self._store_for(scope)
        entry = store.get(technique_id)
        if not entry:
            return False
        entry["replay_count"] = entry.get("replay_count", 0) + 1
        entry["last_replayed_at"] = datetime.now(timezone.utc).isoformat()
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_scope(scope)
        return True

    def update(self, technique_id: str, updates: dict[str, Any], scope: str = "project") -> bool:
        """Update mutable fields on a technique. Returns True on success."""
        store = self._store_for(scope)
        entry = store.get(technique_id)
        if not entry:
            return False
        allowed = {"name", "description", "tags", "notes", "validation_result"}
        for key, value in updates.items():
            if key == "state":
                continue  # State changes must go through update_state()
            elif key == "tags":
                entry[key] = sorted(set(t.lower() for t in value)) if isinstance(value, list) else value
            elif key in allowed:
                entry[key] = value
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_scope(scope)
        return True

    def update_validation(
        self,
        technique_id: str,
        validation: dict[str, Any],
        scope: str = "project",
    ) -> bool:
        """Update validation_result and auto-promote/demote state.

        If validation status is 'pass' and current state is 'candidate',
        auto-promotes to 'validated_local'.
        If validation status is 'fail', reverts 'validated_local'/'validated_portable'
        back to 'candidate'.
        Returns True on success, False if technique not found.
        """
        store = self._store_for(scope)
        entry = store.get(technique_id)
        if not entry:
            return False
        entry["validation_result"] = validation
        status = validation.get("status", "")
        current_state = entry.get("state", "candidate")
        if status == "pass" and current_state == "candidate":
            entry["state"] = "validated_local"
        elif status == "fail":
            if current_state == "validated_portable":
                entry["state"] = "validated_local"
            elif current_state == "validated_local":
                entry["state"] = "candidate"
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_scope(scope)
        return True

    def update_state(
        self,
        technique_id: str,
        new_state: str,
        scope: str = "project",
    ) -> bool:
        """Update the state of a technique with validation.

        Returns True on success, False if technique not found or state is invalid.
        """
        if new_state not in self._VALID_STATES:
            return False
        store = self._store_for(scope)
        entry = store.get(technique_id)
        if not entry:
            return False
        entry["state"] = new_state
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_scope(scope)
        return True

    def delete(self, technique_id: str, scope: str = "project") -> bool:
        """Delete a technique. Returns True if it existed."""
        store = self._store_for(scope)
        if technique_id not in store:
            return False
        del store[technique_id]
        self._save_scope(scope)
        return True

    def promote(self, technique_id: str) -> str | None:
        """Copy a project technique to the global library. Returns new global id, or None."""
        entry = self._project.get(technique_id)
        if not entry:
            return None
        import copy

        promoted = copy.deepcopy(entry)
        new_id = str(uuid.uuid4())
        promoted["id"] = new_id
        promoted["promoted_from"] = technique_id
        promoted["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._global[new_id] = promoted
        self._save_scope("global")
        return new_id

    def set_favorite(self, technique_id: str, favorite: bool, scope: str = "project") -> bool:
        store = self._store_for(scope)
        entry = store.get(technique_id)
        if not entry:
            return False
        entry["favorite"] = favorite
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_scope(scope)
        return True

    def set_rating(self, technique_id: str, rating: int, scope: str = "project") -> bool:
        store = self._store_for(scope)
        entry = store.get(technique_id)
        if not entry:
            return False
        entry["rating"] = max(0, min(5, rating))
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_scope(scope)
        return True

    def export_library(self, scope: str = "project") -> dict[str, Any]:
        """Export techniques as a portable JSON-serializable dict."""
        import copy

        store = self._store_for(scope)
        return {
            "version": 1,
            "scope": scope,
            "count": len(store),
            "techniques": copy.deepcopy(dict(store)),
        }

    def import_library(
        self,
        data: dict[str, Any],
        scope: str = "project",
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Import techniques from an exported library dict.

        Returns summary with imported/skipped/overwritten counts.
        """
        techniques = data.get("techniques", {})
        if not isinstance(techniques, dict):
            return {"imported": 0, "skipped": 0, "error": "Invalid format: 'techniques' must be a dict"}

        store = self._store_for(scope)
        imported = 0
        skipped = 0
        overwritten = 0

        for tid, entry in techniques.items():
            if not isinstance(entry, dict) or "technique" not in entry:
                skipped += 1
                continue
            if tid in store and not overwrite:
                skipped += 1
                continue
            if tid in store:
                overwritten += 1
            store[tid] = entry
            imported += 1

        if imported > 0:
            self._save_scope(scope)

        return {"imported": imported, "skipped": skipped, "overwritten": overwritten}

    def stats(self) -> dict[str, Any]:
        return {
            "global_count": len(self._global),
            "project_count": len(self._project),
            "project_name": self._project_name,
            "base_dir": str(self._base),
        }

    # ------------------------------------------------------------------
    # Lazy rebinding — used when the TDPilot server starts before TD is
    # reachable. See _ensure_project_scope in tool_registry.py.
    # ------------------------------------------------------------------

    def rebind_project_scope(self, project_name: str) -> None:
        """Re-target this store at a new project folder without a restart.

        Replaces _project_name / _project_dir, creates the directory,
        drops the in-memory project cache, and reloads from disk. Existing
        global data is untouched. Idempotent if called with the same name.
        """
        if not project_name:
            return
        safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
        self._project_name = project_name
        self._project_dir = self._base / "projects" / safe_name
        self._project_dir.mkdir(parents=True, exist_ok=True)
        self._project = self._load_file(self._project_dir / "techniques.json")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _store_for(self, scope: str) -> dict[str, dict[str, Any]]:
        if scope == "global":
            return self._global
        return self._project

    def _stores_for_scope(self, scope: str) -> list[tuple]:
        """Return list of (scope_label, store_dict) tuples to iterate."""
        if scope == "global":
            return [("global", self._global)]
        if scope == "project":
            return [("project", self._project)]
        # "all" — project first, then global
        stores: list[tuple] = []
        if self._project:
            stores.append(("project", self._project))
        stores.append(("global", self._global))
        return stores

    def _summary(self, entry: dict[str, Any], scope: str) -> dict[str, Any]:
        """Return a summary dict (no full technique/recipe payload)."""
        tech = entry.get("technique", {})
        return {
            "id": entry["id"],
            "name": entry.get("name", ""),
            "description": entry.get("description", ""),
            "tags": entry.get("tags", []),
            "scope": scope,
            "favorite": entry.get("favorite", False),
            "rating": entry.get("rating", 0),
            "created_at": entry.get("created_at", ""),
            "updated_at": entry.get("updated_at", ""),
            "node_count": tech.get("node_count", 0),
            "complexity": tech.get("complexity", "unknown"),
            "replay_count": entry.get("replay_count", 0),
            "last_replayed_at": entry.get("last_replayed_at"),
            "state": entry.get("state", "candidate"),
            "compatibility": entry.get("compatibility", {}),
            "validation_result": entry.get("validation_result"),
        }

    def _file_for(self, scope: str) -> Path:
        if scope == "global":
            return self._global_dir / "techniques.json"
        if self._project_dir is None:
            raise ValueError("No project directory configured for project-scoped techniques")
        return self._project_dir / "techniques.json"

    def _load(self) -> None:
        self._global = self._load_file(self._global_dir / "techniques.json")
        if self._project_dir:
            self._project = self._load_file(self._project_dir / "techniques.json")

    def _load_file(self, path: Path) -> dict[str, dict[str, Any]]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        # Validate entries
        result: dict[str, dict[str, Any]] = {}
        for tid, entry in data.items():
            if isinstance(entry, dict) and "technique" in entry:
                result[tid] = entry
        return result

    def _save_scope(self, scope: str) -> None:
        if scope == "global":
            self._write_file(self._global_dir / "techniques.json", self._global)
        elif scope == "project":
            if not self._project_dir:
                raise ValueError(
                    "Cannot save project-scoped data: TDPILOT_PROJECT_NAME is not set. "
                    "Set the environment variable or use scope='global'."
                )
            self._write_file(self._project_dir / "techniques.json", self._project)

    def _write_file(self, path: Path, data: dict[str, dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception as exc:
            logger.error("Failed to write %s: %s", path, exc)
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
