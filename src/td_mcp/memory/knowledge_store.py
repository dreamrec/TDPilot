"""Knowledge library — free-form markdown technique essays with per-project + global scope.

Parallel to ``technique_store.py`` but for prose-with-math reference content
(BZ reaction equations, feedback recipes, "why this approach works" essays)
rather than replayable network recipes. Storage layout mirrors TechniqueStore:

    ~/.tdpilot/knowledge/
        global/
            index.json
            entries/<id>.md
        projects/<safe_name>/
            index.json
            entries/<id>.md

Each entry has a markdown body file plus an index.json record with metadata
(name, description, tags, source, created/updated timestamps, favorite, rating).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


DEFAULT_BASE_DIR = "~/.tdpilot/knowledge"

# Hard cap on a single entry body — knowledge essays should be reference-sized,
# not whole books. Anything larger is probably a wrong-tool-for-the-job signal.
MAX_BODY_BYTES = 200_000


class KnowledgeStore:
    """CRUD for free-form markdown knowledge entries with search, ratings, scopes.

    Schema (per entry, in index.json):
        id: UUID
        name: short title
        description: one-line summary
        tags: lowercase strings
        source: optional attribution (e.g. "youtube tutorial", "blog post")
        notes: free-form
        created_at, updated_at: ISO timestamps
        favorite: bool
        rating: 0-5
        body_path: relative path to the markdown file
        body_bytes: cached size for listing performance

    The body itself lives in entries/<id>.md so it can be read/edited
    by the user with any text editor without going through MCP.
    """

    def __init__(self, base_dir: str | None = None, project_name: str | None = None):
        self._base = Path(base_dir or DEFAULT_BASE_DIR).expanduser()
        self._project_name = project_name
        self._global_dir = self._base / "global"
        self._project_dir: Path | None = None
        if project_name:
            safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
            self._project_dir = self._base / "projects" / safe_name

        self._global_dir.mkdir(parents=True, exist_ok=True)
        (self._global_dir / "entries").mkdir(parents=True, exist_ok=True)
        if self._project_dir:
            self._project_dir.mkdir(parents=True, exist_ok=True)
            (self._project_dir / "entries").mkdir(parents=True, exist_ok=True)

        # In-memory caches keyed by id (metadata only — body loaded on demand).
        self._global: dict[str, dict[str, Any]] = {}
        self._project: dict[str, dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(
        self,
        body: str,
        *,
        name: str = "",
        description: str = "",
        tags: list[str] | None = None,
        source: str = "",
        notes: str = "",
        scope: str = "project",
    ) -> str:
        """Create a new knowledge entry. Returns the new id.

        Body is the markdown content. It is written to entries/<id>.md and
        the metadata record goes into index.json for the chosen scope.
        """
        if not isinstance(body, str):
            raise TypeError("body must be a string")
        if len(body.encode("utf-8")) > MAX_BODY_BYTES:
            raise ValueError(f"body exceeds MAX_BODY_BYTES ({MAX_BODY_BYTES}); split into multiple entries")

        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        record: dict[str, Any] = {
            "id": entry_id,
            "name": name or f"entry_{entry_id[:8]}",
            "description": description,
            "tags": sorted({t.lower() for t in (tags or [])}),
            "source": source,
            "notes": notes,
            "created_at": now,
            "updated_at": now,
            "favorite": False,
            "rating": 0,
            "body_path": f"entries/{entry_id}.md",
            "body_bytes": len(body.encode("utf-8")),
        }

        scope_dir = self._dir_for(scope)
        body_path = scope_dir / record["body_path"]
        self._write_text(body_path, body)

        store = self._store_for(scope)
        store[entry_id] = record
        self._save_index(scope)
        return entry_id

    def get(self, entry_id: str, scope: str = "project") -> dict[str, Any] | None:
        """Return the full entry (metadata + body), or None if missing."""
        store = self._store_for(scope)
        record = store.get(entry_id)
        if record is None:
            return None
        scope_dir = self._dir_for(scope)
        body_path = scope_dir / record["body_path"]
        body = self._read_text(body_path)
        # Return a copy with body inlined; don't mutate the cached metadata.
        out = dict(record)
        out["body"] = body
        return out

    def search(
        self,
        query: str = "",
        tags: list[str] | None = None,
        scope: str = "all",
        limit: int = 20,
        full_text: bool = False,
    ) -> list[dict[str, Any]]:
        """Search by text query and/or tags. Returns summaries (no bodies).

        With ``full_text=False`` (default), the query matches against name +
        description + tags + source + notes. Cheap.
        With ``full_text=True``, also reads each body file. Slower but more
        thorough — use sparingly.
        """
        results: list[dict[str, Any]] = []
        stores = self._stores_for_scope(scope)
        query_lower = query.lower()
        tag_set = set(tags or [])

        for scope_label, store in stores:
            for record in store.values():
                # Tag filter
                if tag_set and not tag_set.intersection(record.get("tags", [])):
                    continue
                if query_lower:
                    haystack_parts = [
                        record.get("name", ""),
                        record.get("description", ""),
                        " ".join(record.get("tags", [])),
                        record.get("source", ""),
                        record.get("notes", ""),
                    ]
                    if full_text:
                        scope_dir = self._dir_for(scope_label)
                        body = self._read_text(scope_dir / record["body_path"])
                        haystack_parts.append(body or "")
                    haystack = " ".join(haystack_parts).lower()
                    if query_lower not in haystack:
                        continue
                results.append(self._summary(record, scope_label))

        # Sort: favorites first, then rating desc, then newest.
        results.sort(
            key=lambda r: (
                not r.get("favorite", False),
                -(r.get("rating", 0)),
                r.get("created_at", ""),
            )
        )
        return results[:limit]

    def list_entries(
        self,
        scope: str = "all",
        tags: list[str] | None = None,
        favorites_only: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List entry summaries with optional filtering."""
        results: list[dict[str, Any]] = []
        stores = self._stores_for_scope(scope)
        tag_set = set(tags or [])

        for scope_label, store in stores:
            for record in store.values():
                if favorites_only and not record.get("favorite"):
                    continue
                if tag_set and not tag_set.intersection(record.get("tags", [])):
                    continue
                results.append(self._summary(record, scope_label))

        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results[:limit]

    def update(
        self,
        entry_id: str,
        updates: dict[str, Any],
        scope: str = "project",
    ) -> bool:
        """Update mutable fields. Body updates go through ``update_body``."""
        store = self._store_for(scope)
        record = store.get(entry_id)
        if not record:
            return False
        allowed = {"name", "description", "source", "notes"}
        for key, value in updates.items():
            if key == "tags":
                record[key] = sorted({t.lower() for t in value}) if isinstance(value, list) else value
            elif key in allowed:
                record[key] = value
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_index(scope)
        return True

    def update_body(self, entry_id: str, body: str, scope: str = "project") -> bool:
        """Replace the markdown body of an entry."""
        if not isinstance(body, str):
            return False
        if len(body.encode("utf-8")) > MAX_BODY_BYTES:
            raise ValueError(f"body exceeds MAX_BODY_BYTES ({MAX_BODY_BYTES}); split into multiple entries")
        store = self._store_for(scope)
        record = store.get(entry_id)
        if not record:
            return False
        scope_dir = self._dir_for(scope)
        body_path = scope_dir / record["body_path"]
        self._write_text(body_path, body)
        record["body_bytes"] = len(body.encode("utf-8"))
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_index(scope)
        return True

    def delete(self, entry_id: str, scope: str = "project") -> bool:
        store = self._store_for(scope)
        record = store.get(entry_id)
        if not record:
            return False
        scope_dir = self._dir_for(scope)
        body_path = scope_dir / record["body_path"]
        try:
            if body_path.exists():
                body_path.unlink()
        except OSError as exc:
            logger.warning("Failed to remove body file %s: %s", body_path, exc)
        del store[entry_id]
        self._save_index(scope)
        return True

    def promote(self, entry_id: str) -> str | None:
        """Copy a project entry to global. Returns new global id or None."""
        record = self._project.get(entry_id)
        if not record:
            return None
        # Read the body, then add fresh under global scope.
        scope_dir = self._dir_for("project")
        body = self._read_text(scope_dir / record["body_path"]) or ""
        new_id = self.add(
            body,
            name=record.get("name", ""),
            description=record.get("description", ""),
            tags=list(record.get("tags", [])),
            source=record.get("source", ""),
            notes=record.get("notes", ""),
            scope="global",
        )
        # Track promotion lineage.
        self._global[new_id]["promoted_from"] = entry_id
        self._save_index("global")
        return new_id

    def set_favorite(self, entry_id: str, favorite: bool, scope: str = "project") -> bool:
        store = self._store_for(scope)
        record = store.get(entry_id)
        if not record:
            return False
        record["favorite"] = bool(favorite)
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_index(scope)
        return True

    def set_rating(self, entry_id: str, rating: int, scope: str = "project") -> bool:
        store = self._store_for(scope)
        record = store.get(entry_id)
        if not record:
            return False
        record["rating"] = max(0, min(5, int(rating)))
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_index(scope)
        return True

    def stats(self) -> dict[str, Any]:
        return {
            "global_count": len(self._global),
            "project_count": len(self._project),
            "project_name": self._project_name,
            "base_dir": str(self._base),
        }

    def rebind_project_scope(self, project_name: str) -> None:
        """Re-target this store at a new project folder (mirrors TechniqueStore)."""
        if not project_name:
            return
        safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in project_name)
        self._project_name = project_name
        self._project_dir = self._base / "projects" / safe_name
        self._project_dir.mkdir(parents=True, exist_ok=True)
        (self._project_dir / "entries").mkdir(parents=True, exist_ok=True)
        self._project = self._load_index(self._project_dir / "index.json")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _store_for(self, scope: str) -> dict[str, dict[str, Any]]:
        if scope == "global":
            return self._global
        return self._project

    def _dir_for(self, scope: str) -> Path:
        if scope == "global":
            return self._global_dir
        if self._project_dir is None:
            raise ValueError(
                "No project directory configured for project-scoped knowledge. "
                "Set TDPILOT_PROJECT_NAME or use scope='global'."
            )
        return self._project_dir

    def _stores_for_scope(self, scope: str) -> list[tuple]:
        if scope == "global":
            return [("global", self._global)]
        if scope == "project":
            return [("project", self._project)]
        # "all" — project first, then global
        out: list[tuple] = []
        if self._project:
            out.append(("project", self._project))
        out.append(("global", self._global))
        return out

    def _summary(self, record: dict[str, Any], scope: str) -> dict[str, Any]:
        return {
            "id": record["id"],
            "name": record.get("name", ""),
            "description": record.get("description", ""),
            "tags": record.get("tags", []),
            "source": record.get("source", ""),
            "scope": scope,
            "favorite": record.get("favorite", False),
            "rating": record.get("rating", 0),
            "body_bytes": record.get("body_bytes", 0),
            "created_at": record.get("created_at", ""),
            "updated_at": record.get("updated_at", ""),
        }

    def _load(self) -> None:
        self._global = self._load_index(self._global_dir / "index.json")
        if self._project_dir:
            self._project = self._load_index(self._project_dir / "index.json")

    def _load_index(self, path: Path) -> dict[str, dict[str, Any]]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for eid, record in data.items():
            if isinstance(record, dict) and "body_path" in record:
                out[eid] = record
        return out

    def _save_index(self, scope: str) -> None:
        store = self._store_for(scope)
        scope_dir = self._dir_for(scope)
        path = scope_dir / "index.json"
        self._write_json(path, store)

    def _write_text(self, path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(path)

    def _read_text(self, path: Path) -> str | None:
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return None

    def _write_json(self, path: Path, data: dict[str, dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(path)
        except Exception as exc:
            logger.error("Failed to write %s: %s", path, exc)
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
