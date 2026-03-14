"""Technique library with per-project and global scope, JSON persistence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_BASE_DIR = "~/.tdpilot/memory"


class TechniqueStore:
    """CRUD for reusable TD network recipes with search, ratings, and promotion."""

    def __init__(self, base_dir: str | None = None, project_name: str | None = None):
        self._base = Path(base_dir or DEFAULT_BASE_DIR).expanduser()
        self._project_name = project_name
        self._global_dir = self._base / "global"
        self._project_dir: Optional[Path] = None
        if project_name:
            safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
            self._project_dir = self._base / "projects" / safe_name

        # Ensure directories exist
        self._global_dir.mkdir(parents=True, exist_ok=True)
        if self._project_dir:
            self._project_dir.mkdir(parents=True, exist_ok=True)

        # In-memory caches keyed by technique id
        self._global: Dict[str, Dict[str, Any]] = {}
        self._project: Dict[str, Dict[str, Any]] = {}

        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # Valid state transitions
    _VALID_STATES = frozenset({
        "candidate",
        "validated_local",
        "validated_portable",
        "deprecated",
    })

    def add(
        self,
        technique: Dict[str, Any],
        scope: str = "project",
        *,
        name: str = "",
        description: str = "",
        tags: Optional[List[str]] = None,
        notes: str = "",
        compatibility: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a technique and return its id."""
        technique_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        entry: Dict[str, Any] = {
            "id": technique_id,
            "name": name or f"technique_{technique_id[:8]}",
            "description": description,
            "tags": sorted(set(tags or [])),
            "notes": notes,
            "created_at": now,
            "updated_at": now,
            "favorite": False,
            "rating": 0,
            "state": "candidate",
            "validation_result": None,
            "compatibility": compatibility or {},
            "technique": technique,
        }
        store = self._store_for(scope)
        store[technique_id] = entry
        self._save_scope(scope)
        return technique_id

    def get(self, technique_id: str, scope: str = "project") -> Optional[Dict[str, Any]]:
        """Return a single technique by id, or None."""
        store = self._store_for(scope)
        return store.get(technique_id)

    def search(
        self,
        query: str = "",
        tags: Optional[List[str]] = None,
        scope: str = "all",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search techniques by text query and/or tags. Returns summaries (no full recipe)."""
        results: List[Dict[str, Any]] = []
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

        # Sort: favorites first, then by rating desc, then newest
        results.sort(
            key=lambda r: (
                not r.get("favorite", False),
                -(r.get("rating", 0)),
                r.get("created_at", ""),
            )
        )
        return results[:limit]

    def list_techniques(
        self,
        scope: str = "all",
        tags: Optional[List[str]] = None,
        favorites_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List technique summaries with optional filtering."""
        results: List[Dict[str, Any]] = []
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

    def update(self, technique_id: str, updates: Dict[str, Any], scope: str = "project") -> bool:
        """Update mutable fields on a technique. Returns True on success."""
        store = self._store_for(scope)
        entry = store.get(technique_id)
        if not entry:
            return False
        allowed = {"name", "description", "tags", "notes", "state", "validation_result"}
        for key, value in updates.items():
            if key in allowed:
                entry[key] = value
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_scope(scope)
        return True

    def update_validation(
        self,
        technique_id: str,
        validation: Dict[str, Any],
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
        elif status == "fail" and current_state in ("validated_local", "validated_portable"):
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

    def promote(self, technique_id: str) -> Optional[str]:
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

    def stats(self) -> Dict[str, Any]:
        return {
            "global_count": len(self._global),
            "project_count": len(self._project),
            "project_name": self._project_name,
            "base_dir": str(self._base),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _store_for(self, scope: str) -> Dict[str, Dict[str, Any]]:
        if scope == "global":
            return self._global
        return self._project

    def _stores_for_scope(self, scope: str) -> List[tuple]:
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

    def _summary(self, entry: Dict[str, Any], scope: str) -> Dict[str, Any]:
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
            "state": entry.get("state", "candidate"),
            "compatibility": entry.get("compatibility", {}),
            "validation_result": entry.get("validation_result"),
        }

    def _file_for(self, scope: str) -> Path:
        if scope == "global":
            return self._global_dir / "techniques.json"
        assert self._project_dir is not None
        return self._project_dir / "techniques.json"

    def _load(self) -> None:
        self._global = self._load_file(self._global_dir / "techniques.json")
        if self._project_dir:
            self._project = self._load_file(self._project_dir / "techniques.json")

    def _load_file(self, path: Path) -> Dict[str, Dict[str, Any]]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        # Validate entries
        result: Dict[str, Dict[str, Any]] = {}
        for tid, entry in data.items():
            if isinstance(entry, dict) and "technique" in entry:
                result[tid] = entry
        return result

    def _save_scope(self, scope: str) -> None:
        if scope == "global":
            self._write_file(self._global_dir / "techniques.json", self._global)
        elif self._project_dir:
            self._write_file(self._project_dir / "techniques.json", self._project)

    def _write_file(self, path: Path, data: Dict[str, Dict[str, Any]]) -> None:
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
