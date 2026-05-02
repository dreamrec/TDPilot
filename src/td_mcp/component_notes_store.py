"""Per-COMP markdown notes for ``td_component_notes``.

Stores per-project + per-COMP-path markdown bodies. The default storage
mode is *external* (JSON in ``~/.tdpilot/component_notes/``) so notes
don't bloat the user's ``.toe`` save files. An optional ``embed=True``
mode also writes a hidden Text DAT named ``tdpilot_notes`` inside the
target COMP — that path is wired by the tool itself via ``/api/exec``,
not this store; the store only owns the host-side JSON.

File layout (per project):

    ~/.tdpilot/component_notes/<project_hash>.json

Schema:

    {
      "schema_version": 1,
      "project_hash": "ab12cd34...",
      "project_label": "live_visuals_v3",
      "notes": {
        "/project1/feedback_chain": {
          "body": "...",
          "tags": ["feedback", "rd"],
          "embedded": false,
          "created_at": "2026-05-02T14:30:00+00:00",
          "updated_at": "2026-05-02T14:30:00+00:00"
        }
      }
    }
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def _install_root() -> Path:
    override = os.environ.get("TDPILOT_HOME")
    base = Path(override).expanduser() if override else Path.home() / ".tdpilot"
    return base


def _notes_dir() -> Path:
    d = _install_root() / "component_notes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_doc(project_hash: str, project_label: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_hash": project_hash,
        "project_label": project_label,
        "notes": {},
    }


class ComponentNotesStore:
    """File-backed CRUD for per-COMP markdown notes.

    Notes are keyed by absolute COMP path within a project. Save semantics:
    overwrite (with refreshed updated_at). Append semantics: timestamp the
    addition, separate from existing body with two newlines + a divider.
    """

    def __init__(self, root: Path | None = None) -> None:
        self._root = root if root is not None else _notes_dir()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, project_hash: str) -> Path:
        return self._root / f"{project_hash}.json"

    def _load(self, project_hash: str, project_label: str = "") -> dict[str, Any]:
        path = self._path(project_hash)
        if not path.exists():
            return _empty_doc(project_hash, project_label)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return _empty_doc(project_hash, project_label)
        if not isinstance(doc, dict) or "notes" not in doc:
            return _empty_doc(project_hash, project_label)
        if project_label:
            doc["project_label"] = project_label
        doc.setdefault("schema_version", SCHEMA_VERSION)
        doc.setdefault("project_hash", project_hash)
        if not isinstance(doc.get("notes"), dict):
            doc["notes"] = {}
        return doc

    def _write(self, project_hash: str, doc: dict[str, Any]) -> None:
        tmp = self._path(project_hash).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path(project_hash))

    def get(self, project_hash: str, comp_path: str) -> dict[str, Any] | None:
        doc = self._load(project_hash)
        entry = doc.get("notes", {}).get(comp_path)
        return dict(entry) if isinstance(entry, dict) else None

    def set(
        self,
        *,
        project_hash: str,
        project_label: str,
        comp_path: str,
        body: str,
        tags: list[str] | None = None,
        embedded: bool = False,
    ) -> dict[str, Any]:
        doc = self._load(project_hash, project_label)
        now = _utc_now()
        existing = doc["notes"].get(comp_path)
        if existing:
            existing["body"] = body
            if tags is not None:
                existing["tags"] = list(tags)
            existing["embedded"] = embedded
            existing["updated_at"] = now
            entry = existing
        else:
            entry = {
                "body": body,
                "tags": list(tags) if tags else [],
                "embedded": embedded,
                "created_at": now,
                "updated_at": now,
            }
            doc["notes"][comp_path] = entry
        self._write(project_hash, doc)
        return entry

    def append(
        self,
        *,
        project_hash: str,
        project_label: str,
        comp_path: str,
        body: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        doc = self._load(project_hash, project_label)
        now = _utc_now()
        existing = doc["notes"].get(comp_path)
        if existing:
            sep = f"\n\n---\n_Appended {now}:_\n\n"
            existing["body"] = (existing.get("body", "") or "") + sep + body
            if tags:
                merged = list(existing.get("tags", []))
                for t in tags:
                    if t not in merged:
                        merged.append(t)
                existing["tags"] = merged
            existing["updated_at"] = now
            entry = existing
        else:
            entry = {
                "body": body,
                "tags": list(tags) if tags else [],
                "embedded": False,
                "created_at": now,
                "updated_at": now,
            }
            doc["notes"][comp_path] = entry
        self._write(project_hash, doc)
        return entry

    def delete(self, project_hash: str, comp_path: str) -> bool:
        path = self._path(project_hash)
        if not path.exists():
            return False
        doc = self._load(project_hash)
        if comp_path not in doc["notes"]:
            return False
        del doc["notes"][comp_path]
        self._write(project_hash, doc)
        return True

    def index(self, project_hash: str) -> list[dict[str, Any]]:
        doc = self._load(project_hash)
        out: list[dict[str, Any]] = []
        for comp_path, entry in doc["notes"].items():
            if not isinstance(entry, dict):
                continue
            body = entry.get("body", "") or ""
            excerpt = body if len(body) <= 200 else body[:200] + "…"
            out.append(
                {
                    "path": comp_path,
                    "body_excerpt": excerpt,
                    "body_bytes": len(body.encode("utf-8")),
                    "tags": list(entry.get("tags", [])),
                    "embedded": bool(entry.get("embedded", False)),
                    "created_at": entry.get("created_at"),
                    "updated_at": entry.get("updated_at"),
                }
            )
        out.sort(key=lambda e: e.get("updated_at") or "", reverse=True)
        return out

    def summarize(self, project_hash: str, scope_path: str | None = None) -> str:
        """Return a markdown summary of all notes (optionally scoped to a subtree).

        ``scope_path`` is a path-prefix filter — passing ``"/project1"`` returns
        only notes for COMPs at or under that path.
        """
        doc = self._load(project_hash)
        entries: list[tuple[str, dict[str, Any]]] = []
        for comp_path, entry in doc["notes"].items():
            if not isinstance(entry, dict):
                continue
            if scope_path and not (comp_path == scope_path or comp_path.startswith(scope_path.rstrip("/") + "/")):
                continue
            entries.append((comp_path, entry))
        if not entries:
            return "_No notes for this project._" if not scope_path else f"_No notes under `{scope_path}`._"
        entries.sort(key=lambda e: e[0])
        lines: list[str] = [f"# Component notes ({len(entries)})", ""]
        for comp_path, entry in entries:
            tags = entry.get("tags") or []
            tag_str = " — " + ", ".join(f"`{t}`" for t in tags) if tags else ""
            lines.append(f"## `{comp_path}`{tag_str}")
            lines.append("")
            body = (entry.get("body") or "").strip()
            if body:
                lines.append(body)
            else:
                lines.append("_(empty)_")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
