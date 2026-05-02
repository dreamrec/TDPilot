"""Per-project named-location storage for ``td_locations``.

Stores saved network locations in ``~/.tdpilot/locations/<project_hash>.json``,
one file per project. The hash is a stable function of the TouchDesigner
project name (``project.name`` from the live runtime), so a project keeps
its locations across sessions, plugin reinstalls, and machine moves — but
two projects with the same name will collide. That tradeoff is conscious:
we don't have a stable per-project UUID inside TD, and the alternative
(absolute path hashing) breaks when the user moves the .toe file.

Schema (per project file):

    {
      "schema_version": 1,
      "project_hash": "ab12cd34...",
      "project_label": "live_visuals_v3",
      "locations": [
        {
          "name": "feedback_lab",
          "path": "/project1/feedback_chain",
          "description": "Where the feedbackTOP chain lives",
          "created_at": "2026-05-02T14:30:00+00:00",
          "updated_at": "2026-05-02T14:30:00+00:00"
        }
      ]
    }

Save semantics: name collisions overwrite (with refreshed updated_at).
Delete semantics: returns False if the name doesn't exist.
Rename semantics: returns False if the source name doesn't exist; if the
new name already exists, the rename is rejected to avoid silent merges.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def _install_root() -> Path:
    """Return the on-disk root for TDPilot user data.

    Honors ``TDPILOT_HOME`` (used by tests + isolated runs); defaults to
    ``~/.tdpilot``. Creates the directory tree on first access.
    """
    override = os.environ.get("TDPILOT_HOME")
    base = Path(override).expanduser() if override else Path.home() / ".tdpilot"
    return base


def _locations_dir() -> Path:
    d = _install_root() / "locations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def derive_project_id(project_name: str | None) -> tuple[str, str]:
    """Return ``(project_hash, project_label)`` for a TD project name.

    A 12-char sha256 prefix is enough for human-scale collision avoidance.
    The label is a sanitized version of the project name for surfacing in
    UIs; the hash is what's used for the on-disk filename.
    """
    label = (project_name or "untitled").strip() or "untitled"
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:12]
    return digest, label


def _project_file(project_hash: str) -> Path:
    return _locations_dir() / f"{project_hash}.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_doc(project_hash: str, project_label: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_hash": project_hash,
        "project_label": project_label,
        "locations": [],
    }


class LocationsStore:
    """File-backed CRUD for per-project network locations.

    Each instance is stateless wrt its data — every read/write hits disk so
    multi-process safety follows the "last write wins" filesystem
    semantics. Good enough for human-driven save flows; would need a lock
    file if we ever drove this from concurrent MCP sessions.
    """

    def __init__(self, root: Path | None = None) -> None:
        self._root = root if root is not None else _locations_dir()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, project_hash: str) -> Path:
        return self._root / f"{project_hash}.json"

    def _load(self, project_hash: str, project_label: str) -> dict[str, Any]:
        path = self._path(project_hash)
        if not path.exists():
            return _empty_doc(project_hash, project_label)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return _empty_doc(project_hash, project_label)
        if not isinstance(doc, dict) or "locations" not in doc:
            return _empty_doc(project_hash, project_label)
        # Refresh project_label in case the user renamed the .toe.
        doc["project_label"] = project_label
        doc.setdefault("schema_version", SCHEMA_VERSION)
        doc.setdefault("project_hash", project_hash)
        return doc

    def _write(self, project_hash: str, doc: dict[str, Any]) -> None:
        tmp = self._path(project_hash).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path(project_hash))

    def list_for_project(self, project_hash: str) -> list[dict[str, Any]]:
        path = self._path(project_hash)
        if not path.exists():
            return []
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        entries = doc.get("locations") if isinstance(doc, dict) else None
        return list(entries) if isinstance(entries, list) else []

    def get(self, project_hash: str, name: str) -> dict[str, Any] | None:
        for entry in self.list_for_project(project_hash):
            if entry.get("name") == name:
                return entry
        return None

    def save(
        self,
        *,
        project_hash: str,
        project_label: str,
        name: str,
        path: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        doc = self._load(project_hash, project_label)
        now = _utc_now()
        existing = next(
            (e for e in doc["locations"] if e.get("name") == name),
            None,
        )
        if existing:
            existing["path"] = path
            existing["description"] = description if description is not None else existing.get(
                "description"
            )
            existing["updated_at"] = now
            entry = existing
        else:
            entry = {
                "name": name,
                "path": path,
                "description": description,
                "created_at": now,
                "updated_at": now,
            }
            doc["locations"].append(entry)
        self._write(project_hash, doc)
        return entry

    def delete(self, project_hash: str, name: str) -> bool:
        path = self._path(project_hash)
        if not path.exists():
            return False
        doc = self._load(project_hash, project_label="")
        before = len(doc["locations"])
        doc["locations"] = [e for e in doc["locations"] if e.get("name") != name]
        if len(doc["locations"]) == before:
            return False
        self._write(project_hash, doc)
        return True

    def rename(self, project_hash: str, old_name: str, new_name: str) -> bool:
        if not new_name or new_name == old_name:
            return False
        path = self._path(project_hash)
        if not path.exists():
            return False
        doc = self._load(project_hash, project_label="")
        old_entry = next((e for e in doc["locations"] if e.get("name") == old_name), None)
        if old_entry is None:
            return False
        if any(e.get("name") == new_name for e in doc["locations"]):
            return False
        old_entry["name"] = new_name
        old_entry["updated_at"] = _utc_now()
        self._write(project_hash, doc)
        return True
