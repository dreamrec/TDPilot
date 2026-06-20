"""Draft structured operator-card candidates from the local DocsBrain corpus."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from td_mcp.brain.atlas_audit import (
    _load_docsbrain_operators,
    _missing_operator_priority,
    _release_operator_mentions,
)
from td_mcp.brain.planner import _PROFILE_SPECS

_PARAM_JUNK = {
    "0",
    "1",
    "2",
    "2x",
    "4x",
    "8",
    "8x",
    "16",
    "32",
    "add",
    "alpha",
    "auto",
    "blue",
    "center",
    "default",
    "fill",
    "fixed",
    "green",
    "hold",
    "input",
    "linear",
    "mirror",
    "none",
    "off",
    "on",
    "output",
    "red",
    "repeat",
    "top",
    "useinput",
    "zero",
}


def draft_missing_operator_cards(
    repo_root: str | Path,
    *,
    limit: int = 20,
    families: list[str] | None = None,
    op_types: list[str] | None = None,
    include_existing: bool = False,
    include_deprecated: bool = False,
) -> list[dict[str, Any]]:
    """Return review-needed operator-card drafts for missing DocsBrain operators.

    Drafts intentionally use ``card_type="operator_draft"`` so they are not
    accidentally counted by the live ``CardIndex``. Reviewers can enrich and
    promote a draft by changing it to a normal structured operator card.
    """
    root = Path(repo_root)
    db_path = root / "data" / "normalized" / "derivative" / "docsbrain.db"
    cards_dir = root / "src" / "td_mcp" / "knowledge" / "cards"
    if not db_path.exists():
        raise FileNotFoundError(f"DocsBrain database not found at {db_path}")

    structured_types = _structured_operator_types(cards_dir / "operators")
    operators = _load_docsbrain_operators(db_path)
    by_op_type = {item["op_type"]: item for item in operators}
    family_filter = {family.upper() for family in families or []}

    if op_types:
        candidates = [by_op_type[op_type] for op_type in op_types if op_type in by_op_type]
    else:
        candidates = list(operators)

    candidates = [
        item
        for item in candidates
        if (include_existing or item["op_type"] not in structured_types)
        and (include_deprecated or not item.get("deprecated"))
        and (not family_filter or item["family"].upper() in family_filter)
    ]

    if not op_types:
        release_mentions = _release_operator_mentions(cards_dir / "release")
        required_profile_operators = {
            str(concept["op_type"])
            for spec in _PROFILE_SPECS.values()
            for concept in spec.concepts
            if concept.get("op_type")
        }
        candidates.sort(
            key=lambda item: (
                -_missing_operator_priority(
                    item,
                    release_mentions=release_mentions,
                    required_profile_operators=required_profile_operators,
                )[0],
                item["family"],
                item["op_type"],
            )
        )

    return [_draft_operator_card(db_path, item) for item in candidates[:limit]]


def write_operator_card_drafts(drafts: list[dict[str, Any]], output_dir: str | Path) -> dict[str, Any]:
    """Write draft cards as ``*.draft.json`` files plus a manifest."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    op_types = []
    draft_filenames = {_draft_card_filename(str(draft["op_type"])) for draft in drafts}
    for stale_path in out.glob("*.draft.json"):
        if stale_path.name not in draft_filenames:
            stale_path.unlink()

    for draft in drafts:
        op_type = str(draft["op_type"])
        op_types.append(op_type)
        (out / _draft_card_filename(op_type)).write_text(
            json.dumps(draft, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    manifest = {
        "schema_version": 1,
        "draft_count": len(drafts),
        "op_types": op_types,
        "generated_at": _now_iso(),
        "review_status": "needs_manual_enrichment",
        "note": "Drafts live outside the loaded structured atlas until reviewed and promoted.",
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _draft_card_filename(op_type: str) -> str:
    return f"{quote(op_type, safe='')}.draft.json"


def _structured_operator_types(operators_dir: Path) -> set[str]:
    types: set[str] = set()
    if not operators_dir.is_dir():
        return types
    for path in operators_dir.glob("*.json"):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        op_type = card.get("op_type")
        if op_type:
            types.add(str(op_type))
    return types


def _draft_operator_card(db_path: Path, operator: dict[str, Any]) -> dict[str, Any]:
    chunks = _operator_chunks(db_path, operator["display_name"])
    summary, summary_chunk_id = _summary_from_chunks(chunks)
    key_params, parameter_chunk_ids = _key_params_from_chunks(chunks)
    content = " ".join(str(chunk.get("content") or "") for chunk in chunks)

    return {
        "card_type": "operator_draft",
        "target_card_type": "operator",
        "op_type": operator["op_type"],
        "family": operator["family"],
        "display_name": operator["display_name"],
        "docs_url": operator["docs_url"],
        "summary": summary,
        "key_params": key_params,
        "common_gotchas": _draft_gotchas(operator, content, key_params),
        "related_snippets": _related_snippets(operator["family"]),
        "build_relevance": "unverified-docsbrain",
        "last_verified": "",
        "review_status": "needs_manual_enrichment",
        "provenance": {
            "source": "docsbrain",
            "docs_url": operator["docs_url"],
            "docsbrain_db": str(db_path),
            "source_chunk_ids": [chunk["chunk_id"] for chunk in chunks if chunk.get("chunk_id")],
            "summary_chunk_id": summary_chunk_id,
            "parameter_chunk_ids": parameter_chunk_ids,
            "generated_at": _now_iso(),
        },
    }


def _operator_chunks(db_path: Path, display_name: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT chunk_id, section_title, parameter_names, content
            FROM chunks
            WHERE doc_type = 'operator' AND operator_name = ?
            ORDER BY
                CASE
                    WHEN lower(section_title) = 'summary' THEN 0
                    WHEN lower(section_title) LIKE 'parameters%' AND lower(section_title) NOT LIKE '%common%' THEN 1
                    WHEN lower(section_title) LIKE 'parameters%' THEN 2
                    ELSE 3
                END,
                chunk_id
            """,
            (display_name,),
        ).fetchall()
    finally:
        conn.close()

    chunks = []
    for row in rows:
        item = dict(row)
        try:
            item["parameter_names"] = json.loads(item.get("parameter_names") or "[]")
        except (json.JSONDecodeError, TypeError):
            item["parameter_names"] = []
        chunks.append(item)
    return chunks


def _summary_from_chunks(chunks: list[dict[str, Any]]) -> tuple[str, str | None]:
    summary_chunk = next(
        (chunk for chunk in chunks if str(chunk.get("section_title") or "").lower() == "summary"),
        chunks[0] if chunks else {},
    )
    raw = str(summary_chunk.get("content") or "")
    text = _clean_text(raw)
    if not text:
        text = "Draft generated from DocsBrain; summary needs manual review."
    return text[:700], summary_chunk.get("chunk_id")


def _key_params_from_chunks(
    chunks: list[dict[str, Any]], *, limit: int = 24
) -> tuple[list[dict[str, Any]], list[str]]:
    params: list[dict[str, Any]] = []
    seen: set[str] = set()
    parameter_chunk_ids: list[str] = []
    for chunk in _parameter_candidate_chunks(chunks):
        raw_params = chunk.get("parameter_names") or []
        content_params = _params_from_content(str(chunk.get("content") or ""))
        if raw_params:
            raw_params = _repair_params_from_content(raw_params, content_params)
        else:
            raw_params = content_params
        if not raw_params:
            continue
        chunk_contributed = False
        for raw in raw_params:
            param = _normalize_draft_param(str(raw))
            if param is None or param["name"] in seen:
                continue
            params.append(param)
            seen.add(param["name"])
            chunk_contributed = True
            if len(params) >= limit:
                break
        if chunk_contributed and chunk.get("chunk_id"):
            parameter_chunk_ids.append(str(chunk["chunk_id"]))
        if len(params) >= limit:
            break
    return params, parameter_chunk_ids


def _parameter_candidate_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parameter_chunks = [
        chunk for chunk in chunks if str(chunk.get("section_title") or "").lower().startswith("parameters")
    ]
    specific_chunks = [
        chunk for chunk in parameter_chunks if "common" not in str(chunk.get("section_title") or "").lower()
    ]
    if any(chunk.get("parameter_names") for chunk in specific_chunks):
        return specific_chunks
    if any(chunk.get("parameter_names") for chunk in parameter_chunks):
        return parameter_chunks
    return chunks


def _repair_params_from_content(raw_params: list[str], content_params: list[str]) -> list[str]:
    if not content_params:
        return raw_params
    content_index = [(candidate, _param_token_set(candidate)) for candidate in content_params]
    repaired = []
    for raw in raw_params:
        if _normalize_draft_param(raw) is not None:
            repaired.append(raw)
            continue
        if len([line for line in raw.splitlines() if line.strip()]) < 2:
            repaired.append(raw)
            continue
        tokens = _param_token_set(raw) - _PARAM_JUNK
        replacement = next(
            (
                candidate
                for candidate, candidate_tokens in content_index
                if tokens and tokens <= candidate_tokens
            ),
            None,
        )
        repaired.append(replacement or raw)
    return repaired


def _param_token_set(raw: str) -> set[str]:
    return {token.lower() for token in re.split(r"[^A-Za-z0-9_]+", raw) if token}


def _params_from_content(content: str) -> list[str]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    params: list[str] = []
    for index in range(1, len(lines) - 1):
        if not _is_content_param_description_start(lines[index + 1]):
            continue
        name = _clean_param_name(lines[index])
        if not name or name.lower() in _PARAM_JUNK:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            continue

        label_start = index - 1
        while label_start > 0 and not _is_content_param_boundary(lines[label_start - 1]):
            label_start -= 1
        label_lines = lines[label_start:index]
        if label_lines:
            params.append("\n".join([*label_lines, name]))
    return params


def _is_content_param_boundary(line: str) -> bool:
    return _is_content_param_description_start(line) or line == "⊞"


def _is_content_param_description_start(line: str) -> bool:
    return line == "-" or line.startswith("- ")


def _normalize_draft_param(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        name = _clean_param_name(lines[-1])
        label = _clean_text(" ".join(lines[:-1]))
    else:
        name = _clean_param_name(lines[0])
        label = name
    label = re.sub(r"\s+-(?=\w)", "-", label)

    if not name or name.lower() in _PARAM_JUNK:
        return None
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        return None
    if name != name.lower():
        return None

    return {
        "name": name,
        "label": label,
        "type": "Unknown",
        "note": f"Auto-drafted from DocsBrain parameter '{label}'.",
        "source": "docsbrain",
        "raw": raw,
    }


def _clean_param_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "", text.strip())


def _draft_gotchas(operator: dict[str, Any], content: str, key_params: list[dict[str, Any]]) -> list[str]:
    text = content.lower()
    gotchas = [
        "Draft generated automatically from DocsBrain; manually verify parameters, gotchas, and planner relevance against the official Derivative page before promotion."
    ]
    if not key_params:
        gotchas.append(
            "DocsBrain did not expose structured parameters for this operator; inspect the official docs page before creating a final card."
        )
    if operator.get("deprecated"):
        gotchas.append(
            "DocsBrain marks this operator deprecated; prefer the documented replacement where possible."
        )
    if any(
        term in text for term in ("license", "hardware", "only available", "requires", "device", "camera")
    ):
        gotchas.append(
            "Official docs mention license, hardware, device, or availability constraints; generated plans should guard operator availability."
        )
    return gotchas


def _related_snippets(family: str) -> list[str]:
    family = family.upper()
    if family in {"CHOP", "COMP", "DAT", "MAT", "POP", "SOP", "TOP"}:
        return [f"{family}_snippets"]
    return []


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()
    text = re.sub(r"\s+\w+_Class$", "", text)
    return text


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


__all__ = ["draft_missing_operator_cards", "write_operator_card_drafts"]
