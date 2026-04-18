"""Indexer — builds SQLite FTS5 database from chunks.jsonl."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"

_CREATE_CHUNKS = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    page_id TEXT,
    doc_type TEXT,
    section_title TEXT,
    operator_family TEXT,
    operator_name TEXT,
    mentioned_operators TEXT,
    parameter_names TEXT,
    python_symbols TEXT,
    build_number TEXT,
    build_date TEXT,
    change_category TEXT,
    token_estimate INTEGER,
    content TEXT
)
"""

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    section_title,
    operator_name,
    parameter_names,
    python_symbols,
    content,
    content='',
    tokenize='porter unicode61'
)
"""

_CREATE_META = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
)
"""


def build_index(chunks_path: Path, db_path: Path) -> int:
    """Build SQLite FTS5 index from chunks.jsonl.

    Args:
        chunks_path: Path to chunks.jsonl file.
        db_path: Path to output SQLite database.

    Returns:
        Number of chunks indexed.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing DB for clean rebuild
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_CREATE_CHUNKS)
        conn.execute(_CREATE_FTS)
        conn.execute(_CREATE_META)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )

        count = 0
        with open(chunks_path, encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                _insert_chunk(conn, chunk)
                count += 1

        conn.commit()
        logger.info("Indexed %d chunks into %s", count, db_path)
        return count
    finally:
        conn.close()


def _insert_chunk(conn: sqlite3.Connection, chunk: dict[str, Any]) -> None:
    """Insert a chunk into both the chunks table and FTS5 index."""
    conn.execute(
        """INSERT OR REPLACE INTO chunks
           (chunk_id, page_id, doc_type, section_title, operator_family,
            operator_name, mentioned_operators, parameter_names, python_symbols,
            build_number, build_date, change_category, token_estimate, content)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            chunk["chunk_id"],
            chunk["page_id"],
            chunk["doc_type"],
            chunk["section_title"],
            chunk.get("operator_family"),
            chunk.get("operator_name"),
            json.dumps(chunk.get("mentioned_operators", [])),
            json.dumps(chunk.get("parameter_names", [])),
            json.dumps(chunk.get("python_symbols", [])),
            chunk.get("build_number"),
            chunk.get("build_date"),
            chunk.get("change_category"),
            chunk.get("token_estimate", 0),
            chunk["content"],
        ),
    )

    # Insert into contentless FTS5
    conn.execute(
        """INSERT INTO chunks_fts
           (chunk_id, section_title, operator_name, parameter_names,
            python_symbols, content)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            chunk["chunk_id"],
            chunk.get("section_title", ""),
            chunk.get("operator_name", ""),
            " ".join(chunk.get("parameter_names", [])),
            " ".join(chunk.get("python_symbols", [])),
            chunk["content"],
        ),
    )
