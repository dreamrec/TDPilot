"""TDPilot Docs Brain — full-corpus search over scraped docs.derivative.ca."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Aliases for card_type values that callers historically passed in plural or
# expanded form. DocsBrain stores doc_type values in singular / canonical form
# (e.g. 'operator', 'release_notes'), so without this map a search with
# card_types=['operators'] silently returned nothing.
#
# Unknown values pass through unchanged so that adding a new doc_type later
# doesn't require an alias entry.
_CARD_TYPE_ALIASES: dict[str, str] = {
    "operators": "operator",
    "palettes": "palette",
    "glossaries": "glossary",
    "snippets": "snippet",
    "release": "release_notes",
    "releases": "release_notes",
}


def _canonical_card_types(card_types: list[str] | None) -> list[str] | None:
    """Normalize any alias in `card_types` to the canonical doc_type value.

    Returns the input unchanged when it is None or empty so the caller's
    'no filter' semantics are preserved.
    """
    if not card_types:
        return card_types
    return [_CARD_TYPE_ALIASES.get(ct, ct) for ct in card_types]


class DocsBrain:
    """Runtime search interface for the docs brain SQLite FTS5 database.

    Drop-in replacement for CardIndex — implements the same public API.
    """

    def __init__(
        self,
        db_path: Path,
        changelog_path: Path | None = None,
        manifest_path: Path | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row

        # Load operator changelog
        self._changelog: dict[str, list[dict]] = {}
        if changelog_path and Path(changelog_path).exists():
            self._changelog = json.loads(Path(changelog_path).read_text("utf-8"))

        # Load build manifest
        self._manifest: dict[str, Any] = {}
        if manifest_path and Path(manifest_path).exists():
            self._manifest = json.loads(Path(manifest_path).read_text("utf-8"))

        # Build operator name lookup set for intent detection
        self._operator_names: set[str] = set()
        try:
            cursor = self._conn.execute(
                "SELECT DISTINCT operator_name FROM chunks WHERE operator_name IS NOT NULL AND operator_name != ''"
            )
            self._operator_names = {row[0] for row in cursor}
        except sqlite3.OperationalError:
            pass

        # Build op_type → operator_name mapping.
        # Convention: lowercase-join every word before the family suffix, then
        # append the suffix verbatim. e.g.
        #   "Composite TOP"     → "compositeTOP"
        #   "Movie File In TOP" → "moviefileinTOP"
        #   "GLSL Multi TOP"    → "glslmultiTOP"
        self._op_type_map: dict[str, str] = {}
        for name in self._operator_names:
            parts = name.split()
            if len(parts) >= 2:
                op_type = "".join(p.lower() for p in parts[:-1]) + parts[-1]
                self._op_type_map[op_type] = name

    def count(self) -> int:
        """Total number of chunks in the index."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM chunks")
        return cursor.fetchone()[0]

    def search(
        self,
        query: str,
        card_types: list[str] | None = None,
        family: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search the docs brain with intent-based routing and boosted ranking."""
        # Normalize plural / expanded aliases (e.g. 'operators' → 'operator')
        # so callers using either form get matching results.
        card_types = _canonical_card_types(card_types)

        # Intent detection: narrow doc_type filter
        intent_filter = self._detect_intent(query)

        # Build FTS5 query — escape special characters
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []

        # Build SQL with optional filters
        conditions = []
        params: list[Any] = []

        if card_types:
            placeholders = ",".join("?" for _ in card_types)
            conditions.append(f"c.doc_type IN ({placeholders})")
            params.extend(card_types)
        elif intent_filter:
            if isinstance(intent_filter, list):
                placeholders = ",".join("?" for _ in intent_filter)
                conditions.append(f"c.doc_type IN ({placeholders})")
                params.extend(intent_filter)
            else:
                conditions.append("c.doc_type = ?")
                params.append(intent_filter)

        if family:
            conditions.append("c.operator_family = ?")
            params.append(family.upper())

        where_clause = ""
        if conditions:
            where_clause = "AND " + " AND ".join(conditions)

        sql = f"""
            SELECT c.*, fts.rank as score
            FROM chunks_fts fts
            JOIN chunks c ON c.rowid = fts.rowid
            WHERE chunks_fts MATCH ?
            {where_clause}
            ORDER BY bm25(chunks_fts, 10.0, 8.0, 5.0, 3.0, 1.0)
            LIMIT ?
        """

        try:
            cursor = self._conn.execute(sql, [fts_query] + params + [limit])
            rows = cursor.fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("FTS5 query failed: %s (query=%r)", exc, fts_query)
            return []

        return [self._row_to_dict(row) for row in rows]

    def get_operator(self, op_type: str) -> dict | None:
        """Look up an operator by op_type (e.g. 'compositeTOP')."""
        operator_name = self._op_type_map.get(op_type)
        if not operator_name:
            return None

        cursor = self._conn.execute(
            """SELECT * FROM chunks
               WHERE operator_name = ? AND doc_type = 'operator'
               ORDER BY chunk_id LIMIT 10""",
            (operator_name,),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        first = dict(rows[0])
        # Build response matching CardIndex shape
        summary_chunks = [dict(r) for r in rows]
        summary = next(
            (c["content"] for c in summary_chunks if "summary" in c["section_title"].lower()),
            summary_chunks[0]["content"] if summary_chunks else "",
        )

        # Collect all parameter names
        all_params = []
        for chunk in summary_chunks:
            params = json.loads(chunk.get("parameter_names", "[]"))
            all_params.extend(p for p in params if p not in all_params)

        result = {
            "op_type": op_type,
            "family": first.get("operator_family", ""),
            "display_name": operator_name,
            "summary": summary[:500],
            "parameters": all_params,
            "docs_url": f"https://docs.derivative.ca/{operator_name.replace(' ', '_')}",
            "recent_changes": self._changelog.get(operator_name, []),
        }
        return result

    def get_palette(self, component_name: str) -> dict | None:
        """Look up a palette component by name."""
        # Try case-insensitive search
        cursor = self._conn.execute(
            """SELECT * FROM chunks
               WHERE doc_type = 'palette' AND LOWER(section_title) = LOWER(?)
               LIMIT 1""",
            (component_name,),
        )
        row = cursor.fetchone()
        if not row:
            # Try content search
            cursor = self._conn.execute(
                """SELECT * FROM chunks
                   WHERE doc_type = 'palette' AND content LIKE ?
                   LIMIT 1""",
                (f"%{component_name}%",),
            )
            row = cursor.fetchone()
        if not row:
            return None

        d = dict(row)
        return {
            "component_name": component_name,
            "summary": d.get("content", "")[:300],
            "doc_type": "palette",
        }

    def get_release(self, build: str) -> dict | None:
        """Look up a specific build's release notes."""
        cursor = self._conn.execute(
            """SELECT * FROM chunks
               WHERE doc_type = 'release_notes' AND build_number = ?
               ORDER BY chunk_id""",
            (build,),
        )
        rows = cursor.fetchall()
        if not rows:
            return None

        entries = []
        for row in rows:
            d = dict(row)
            entries.append({
                "section": d.get("section_title", ""),
                "category": d.get("change_category", "other"),
                "content": d.get("content", ""),
                "mentioned_operators": json.loads(d.get("mentioned_operators", "[]")),
            })

        return {
            "build": build,
            "date": rows[0]["build_date"] or "",
            "entries": entries,
        }

    def check_compatibility(self, op_type: str, current_build: str) -> dict:
        """Check if an operator is compatible with the given build."""
        op = self.get_operator(op_type)
        if op is None:
            return {"status": "caution", "reason": f"No data for '{op_type}'."}
        return {"status": "compatible", "reason": "Operator found in docs corpus."}

    # --- New methods ---

    def get_operator_changelog(self, operator_name: str) -> list[dict]:
        """Get changelog entries for a specific operator."""
        return self._changelog.get(operator_name, [])

    def get_build_manifest(self) -> dict:
        """Get the build manifest with all known builds."""
        return self._manifest

    def search_release_notes(
        self, query: str, build: str | None = None, limit: int = 10
    ) -> list[dict]:
        """Search release notes, optionally filtered by build."""
        results = self.search(query, card_types=["release_notes"], limit=limit)
        if build:
            results = [r for r in results if r.get("build_number") == build]
        return results

    # --- Private helpers ---

    def _detect_intent(self, query: str) -> str | list[str] | None:
        """Classify query intent to narrow search scope."""
        query_lower = query.lower()

        # Build number in query → release notes
        if re.search(r"\d{4}\.\d{4,5}", query):
            return "release_notes"
        if any(kw in query_lower for kw in ("what changed", "release", "new in", "latest build")):
            return "release_notes"

        # Palette prefix
        if query_lower.startswith("palette:") or query_lower.startswith("palette "):
            return "palette"

        # Glossary
        if "glossary" in query_lower or query_lower.startswith("what does ") or query_lower.startswith("define "):
            return "glossary"

        # Operator name match
        for op_name in self._operator_names:
            if op_name.lower() in query_lower:
                return ["operator", "python_api"]

        return None

    def _build_fts_query(self, query: str) -> str:
        """Build a safe FTS5 query string from user input."""
        # Remove FTS5 special characters
        cleaned = re.sub(r'["\(\)\*\^\{\}:]', " ", query)
        terms = cleaned.split()
        if not terms:
            return ""
        # Quote each term and OR them
        quoted = " OR ".join(f'"{t}"' for t in terms if t)
        return quoted

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a sqlite3.Row to a plain dict with parsed JSON fields."""
        d = dict(row)
        for field in ("mentioned_operators", "parameter_names", "python_symbols"):
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        return d
