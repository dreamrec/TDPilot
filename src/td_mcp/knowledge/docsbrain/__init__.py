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


def _normalize_key_param(raw: str) -> dict | None:
    """Turn a raw FTS parameter string into a CardIndex-compatible dict,
    or return ``None`` to signal the entry is junk and should be skipped.

    DocsBrain stores parameters as strings from the FTS parameter_names
    column. Real entries from the scraped docs follow the pattern
    ``"Human Label\\ninternalname"`` (one or more label lines, then the
    TD internal name on its own line). CardIndex JSON cards represent
    key_params as objects like
    ``{"name": "outputresolution", "type": "...", "note": "..."}``.

    v1.4.6 junk filter
    ------------------
    Pre-v1.4.6 this function accepted **any** non-empty string, which
    meant the FTS ``parameter_names`` column bled stray doc words
    (``"Back"``, ``"Z"``, ``"Early Depth"``), menu option values
    (``"useinput"``, ``"2x"``, ``"8"``), and UI fragments
    (``"_separator_"``, ``"Where i is the 0"``) into every operator card.
    Live runs against TD 2025 confirmed this contaminated key_params
    for glslTOP, renderTOP, and other menu-heavy operators.

    The safest filter — without building a per-operator menu-value
    blocklist — is to require the ``"Label\\nname"`` structure: any
    entry without an internal newline is rejected. Real TD param names
    reach this function with that structure because the scraper writes
    label + name on separate lines. Single-line single-word fragments
    from the FTS are overwhelmingly junk.

    The original raw string is preserved under ``raw`` so downstream
    tools can recover it if enrichment is ever added.
    """
    text = (raw or "").strip()
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 1:
        # Single-token entries almost always come from stray doc text or
        # menu option values leaking into FTS `parameter_names`. Real
        # TD param entries arrive as "Label\ninternalname".
        return None
    # Multi-line: last line is the programmatic name; the preceding lines
    # are the human label (joined with spaces).
    return {
        "name": lines[-1],
        "label": " ".join(lines[:-1]),
        "raw": raw,
        "source": "docsbrain",
    }


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

        # v1.4.7 Bug Q/R: reverse lookup so search() can enrich FTS rows with
        # a CardIndex-compatible `op_type` derived from the FTS `operator_name`.
        # Downstream tools (`td_find_official_example`, `td_explain_better_way`,
        # `_is_informative_card`) key off CardIndex field names; without this
        # reverse map, every DocsBrain search result lacked `op_type` and was
        # silently filtered out.
        self._operator_name_to_op_type: dict[str, str] = {v: k for k, v in self._op_type_map.items()}

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

        return [self._normalize_search_row(self._row_to_dict(row)) for row in rows]

    def _normalize_search_row(self, row: dict) -> dict:
        """Enrich a raw FTS row with CardIndex-compatible keys.

        v1.4.7 Bug Q / Bug R fix. FTS chunks expose `operator_name`,
        `section_title`, `content`, etc. — but downstream tools
        (`td_find_official_example`, `td_explain_better_way`,
        `_is_informative_card`) read CardIndex-shape keys (`op_type`,
        `component_name`, `display_name`, `snippet_id`, `summary`). Pre-fix,
        those tools saw empty strings and either emitted blank responses
        (Bug Q) or filtered every candidate out (Bug R).

        This helper is additive: raw FTS fields remain intact so any
        consumer that reads them directly (including the existing
        test_docsbrain_search assertions on `operator_name` /
        `operator_family`) keeps working.
        """
        doc_type = row.get("doc_type", "") or ""
        operator_name = row.get("operator_name") or ""
        section_title = row.get("section_title") or ""
        content = row.get("content") or ""

        if doc_type in ("operator", "python_api"):
            # TD-native operator docs. op_type is the canonical type+family
            # form, recovered via the reverse map built from _op_type_map.
            if operator_name:
                op_type = self._operator_name_to_op_type.get(operator_name, "")
                if op_type and not row.get("op_type"):
                    row["op_type"] = op_type
                if not row.get("display_name"):
                    row["display_name"] = operator_name
            if content and not row.get("summary"):
                row["summary"] = content[:300]
        elif doc_type in ("catalog_operators", "reference"):
            # POPx-style docs. No op_type (non-TD-native naming), but
            # display_name / summary still matter for informative-card
            # filtering.
            if operator_name and not row.get("display_name"):
                row["display_name"] = operator_name
            if content and not row.get("summary"):
                row["summary"] = content[:300]
        elif doc_type == "palette":
            # Section titles look like "Palette:SVG" — strip the prefix so
            # component_name matches the shape that CardIndex JSON cards
            # store (plain component name, no scheme prefix).
            name = section_title
            if name.lower().startswith("palette:"):
                name = name[len("palette:") :].strip()
            if name:
                if not row.get("component_name"):
                    row["component_name"] = name
                if not row.get("display_name"):
                    row["display_name"] = name
            if content and not row.get("summary"):
                row["summary"] = content[:300]
        elif doc_type == "snippet":
            snippet_id = row.get("page_id") or row.get("chunk_id") or ""
            if snippet_id and not row.get("snippet_id"):
                row["snippet_id"] = snippet_id
            if section_title and not row.get("display_name"):
                row["display_name"] = section_title
            if content and not row.get("summary"):
                row["summary"] = content[:300]
        # Other doc_types (general, glossary, release_notes) pass through
        # unchanged — _is_informative_card will correctly filter them out
        # unless a caller explicitly asks for those card_types.
        return row

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

        # Normalize to CardIndex-compatible `key_params` shape (v1.4.5 Fix 3).
        # Before this, tools like `td_get_param_help` that looked up
        # `card["key_params"]` silently got [] when DocsBrain was active,
        # making parameter-help hollow. v1.4.6: _normalize_key_param may
        # return None for junk entries (single-word doc fragments, menu
        # values) — drop those here.
        key_params = [kp for kp in (_normalize_key_param(p) for p in all_params) if kp]

        result = {
            "op_type": op_type,
            "family": first.get("operator_family", ""),
            "display_name": operator_name,
            "summary": summary[:500],
            "parameters": all_params,
            "key_params": key_params,
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
            entries.append(
                {
                    "section": d.get("section_title", ""),
                    "category": d.get("change_category", "other"),
                    "content": d.get("content", ""),
                    "mentioned_operators": json.loads(d.get("mentioned_operators", "[]")),
                }
            )

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

    def search_release_notes(self, query: str, build: str | None = None, limit: int = 10) -> list[dict]:
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
        if (
            "glossary" in query_lower
            or query_lower.startswith("what does ")
            or query_lower.startswith("define ")
        ):
            return "glossary"

        # Operator name match.
        # v1.4.6: the returned doc_type list must cover all brains that store
        # operator-reference chunks. The Derivative brain uses "operator" and
        # "python_api"; the POPx brain uses "catalog_operators" and
        # "reference". Before this fix, POPx brain calls were silently
        # filtered out because the hardcoded `["operator", "python_api"]`
        # list didn't include POPx's doc_types. Doc_types not present in a
        # given brain are no-ops in the SQL IN clause, so the expanded list
        # is safe for both brains.
        for op_name in self._operator_names:
            if op_name.lower() in query_lower:
                return ["operator", "python_api", "catalog_operators", "reference"]

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
