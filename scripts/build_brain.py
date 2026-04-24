#!/usr/bin/env python3
"""Generic config-driven brain builder for TDPilot.

Reads a YAML config that describes how to parse scraped HTML from any
documentation site and produces an FTS5 SQLite brain database.

Usage:
    python scripts/build_brain.py --config configs/example.yaml --source /path/to/scrape/
    python scripts/build_brain.py --help
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sqlite3
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    BeautifulSoup = None  # type: ignore[assignment,misc]
    Tag = None  # type: ignore[assignment,misc]


# ── Config ────────────────────────────────────────────────────


def load_config(config_path: Path) -> dict[str, Any]:
    """Load and validate a brain YAML config."""
    if yaml is None:
        logger.error("pyyaml is required: pip install pyyaml")
        sys.exit(1)

    raw = yaml.safe_load(config_path.read_text("utf-8"))
    required = ("brain_id", "display_name", "content_selector")
    for key in required:
        if key not in raw:
            logger.error("Config missing required key: %s", key)
            sys.exit(1)
    return raw


# ── Normalizer ────────────────────────────────────────────────


def _classify_page(rel_path: str, rules: list[dict]) -> str:
    """Classify a page by matching its path against config rules."""
    from fnmatch import fnmatch

    for rule in rules:
        pattern = rule.get("pattern", "*")
        if fnmatch(rel_path, pattern):
            return rule.get("doc_type", "general")
    return "general"


def _extract_operator_name(rel_path: str, rules: list[dict]) -> str | None:
    """Extract operator name from path if the matching rule says to."""
    from fnmatch import fnmatch

    for rule in rules:
        pattern = rule.get("pattern", "*")
        if fnmatch(rel_path, pattern) and rule.get("extract_operator_name"):
            # Use the last meaningful path segment as operator name
            parts = rel_path.replace("\\", "/").split("/")
            parts = [p for p in parts if p and p != "index.html"]
            if parts:
                return parts[-1].replace("-", " ").replace("_", " ").title()
    return None


def normalize_file(
    filepath: Path,
    rel_path: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Normalize one HTML file according to config."""
    if BeautifulSoup is None:
        logger.error("beautifulsoup4 is required: pip install beautifulsoup4")
        sys.exit(1)

    rules = config.get("page_rules", [])
    doc_type = _classify_page(rel_path, rules)

    try:
        html = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", filepath, exc)
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Find content area
    content_sel = config["content_selector"]
    content_div = soup.select_one(content_sel)
    if content_div is None:
        return None

    # Strip unwanted elements
    for sel in config.get("strip_selectors", []):
        for el in content_div.select(sel):
            el.decompose()

    # Extract title
    h1 = content_div.find("h1")
    title = h1.get_text(strip=True) if h1 else ""

    text = content_div.get_text(separator="\n", strip=True)
    if not text.strip():
        return None

    source_url = config.get("source_url", "")
    page_id = rel_path.replace("\\", "/").replace("/index.html", "").lower()
    page_id = re.sub(r"[^a-z0-9]+", "_", page_id).strip("_")

    return {
        "page_id": page_id,
        "url": f"{source_url.rstrip('/')}/{rel_path.replace('/index.html', '')}",
        "title": title,
        "doc_type": doc_type,
        "operator_name": _extract_operator_name(rel_path, rules),
        "text": text,
        "text_hash": hashlib.sha256(text.encode()).hexdigest(),
    }


def normalize_directory(
    site_dir: Path,
    config: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    """Normalize all HTML in a scrape directory."""
    for filepath in sorted(site_dir.rglob("*.html")):
        rel = str(filepath.relative_to(site_dir))
        record = normalize_file(filepath, rel, config)
        if record is not None:
            yield record


# ── Chunker ───────────────────────────────────────────────────


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def _token_estimate(text: str) -> int:
    return int(len(text.split()) * 1.3)


def chunk_page(page: dict[str, Any], html_path: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Split a page into chunks by headings."""
    if BeautifulSoup is None:
        return []

    try:
        html = html_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    soup = BeautifulSoup(html, "html.parser")
    content_sel = config["content_selector"]
    main = soup.select_one(content_sel)
    if main is None:
        return []

    for sel in config.get("strip_selectors", []):
        for el in main.select(sel):
            el.decompose()

    chunks = []
    page_id = page["page_id"]
    doc_type = page["doc_type"]
    op_name = page.get("operator_name")
    seq = 0

    headings = main.find_all(["h2", "h3", "h4"])
    if headings:
        # Intro before first heading
        intro_parts = []
        for sibling in main.children:
            if isinstance(sibling, Tag) and sibling.name in ("h2", "h3", "h4"):
                break
            if isinstance(sibling, Tag):
                intro_parts.append(sibling.get_text(separator="\n", strip=True))
        intro = "\n".join(p for p in intro_parts if p)
        if intro and len(intro.split()) >= 10:
            seq += 1
            chunks.append(_make_chunk(page_id, seq, page["title"], doc_type, op_name, intro))

        for h_tag in headings:
            h_text = h_tag.get_text(strip=True)
            parts = []
            current = h_tag.next_sibling
            while current:
                if isinstance(current, Tag) and current.name in ("h2", "h3", "h4"):
                    if int(current.name[1]) <= int(h_tag.name[1]):
                        break
                if isinstance(current, Tag):
                    parts.append(current.get_text(separator="\n", strip=True))
                current = current.next_sibling
            text = "\n".join(p for p in parts if p)
            if not text or len(text.split()) < 5:
                continue
            seq += 1
            chunks.append(_make_chunk(page_id, seq, h_text, doc_type, op_name, text))
    else:
        # No headings — whole page as one chunk
        text = page.get("text", "")
        if text and len(text.split()) >= 10:
            seq += 1
            chunks.append(_make_chunk(page_id, seq, page["title"], doc_type, op_name, text))

    return chunks


def _make_chunk(
    page_id: str,
    seq: int,
    section_title: str,
    doc_type: str,
    operator_name: str | None,
    content: str,
) -> dict[str, Any]:
    slug = _slugify(section_title)
    return {
        "chunk_id": f"{page_id}__{slug}__{seq:04d}",
        "page_id": page_id,
        "doc_type": doc_type,
        "section_title": section_title,
        "operator_family": None,
        "operator_name": operator_name,
        "mentioned_operators": [],
        "parameter_names": [],
        "python_symbols": [],
        "build_number": None,
        "build_date": None,
        "change_category": None,
        "token_estimate": _token_estimate(content),
        "content": content,
    }


# ── Indexer ───────────────────────────────────────────────────


def build_fts_index(chunks_path: Path, db_path: Path, brain_id: str) -> int:
    """Build SQLite FTS5 index from chunks.jsonl."""
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                page_id TEXT,
                url TEXT,
                page_title TEXT,
                doc_type TEXT,
                section_title TEXT,
                operator_family TEXT,
                operator_name TEXT,
                mentioned_operators TEXT DEFAULT '[]',
                parameter_names TEXT DEFAULT '[]',
                python_symbols TEXT DEFAULT '[]',
                build_number TEXT,
                build_date TEXT,
                change_category TEXT,
                source TEXT DEFAULT 'html',
                token_estimate INTEGER,
                content TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                section_title, operator_name, parameter_names,
                python_symbols, content,
                content='',
                tokenize='porter unicode61'
            );
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("brain_name", brain_id),
        )

        count = 0
        with open(chunks_path, encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                conn.execute(
                    """INSERT OR REPLACE INTO chunks
                       (chunk_id, page_id, doc_type, section_title,
                        operator_family, operator_name, mentioned_operators,
                        parameter_names, python_symbols, build_number,
                        build_date, change_category, token_estimate, content)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                conn.execute(
                    """INSERT INTO chunks_fts
                       (rowid, section_title, operator_name, parameter_names,
                        python_symbols, content)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        count + 1,
                        chunk.get("section_title", ""),
                        chunk.get("operator_name", "") or "",
                        " ".join(chunk.get("parameter_names", [])),
                        " ".join(chunk.get("python_symbols", [])),
                        chunk["content"],
                    ),
                )
                count += 1

        conn.commit()
        return count
    finally:
        conn.close()


# ── Main pipeline ─────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generic config-driven brain builder for TDPilot",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to brain config YAML file",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to scraped HTML site root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: data/normalized/<brain_id>/)",
    )
    parser.add_argument(
        "--refs",
        type=Path,
        default=None,
        help="Optional path to reference markdown files to ingest",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    brain_id = config["brain_id"]

    if not args.source.is_dir():
        logger.error("Source directory not found: %s", args.source)
        sys.exit(1)

    output = args.output or (Path(__file__).resolve().parent.parent / "data" / "normalized" / brain_id)
    output.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    # Stage 1: Normalize
    logger.info("Stage 1: Normalizing HTML from %s", args.source)
    pages_path = output / "pages.jsonl"
    page_count = 0
    with open(pages_path, "w", encoding="utf-8") as f:
        for page in normalize_directory(args.source, config):
            f.write(json.dumps(page, ensure_ascii=False) + "\n")
            page_count += 1
    logger.info("  → %d pages normalized", page_count)

    # Stage 2: Chunk
    logger.info("Stage 2: Chunking pages")
    all_chunks: list[dict] = []
    with open(pages_path, encoding="utf-8") as f:
        for line in f:
            page = json.loads(line)
            url_path = page["url"].replace(config.get("source_url", "").rstrip("/") + "/", "")
            html_path = args.source / url_path / "index.html"
            if not html_path.exists():
                html_path = args.source / f"{url_path}.html"
            if not html_path.exists() and not url_path:
                html_path = args.source / "index.html"
            if html_path.exists():
                chunks = chunk_page(page, html_path, config)
                all_chunks.extend(chunks)

    # Stage 2b: Ingest markdown refs if provided
    if args.refs and args.refs.is_dir():
        logger.info("Stage 2b: Ingesting markdown refs from %s", args.refs)
        for md_file in sorted(args.refs.glob("*.md")):
            text = md_file.read_text(encoding="utf-8", errors="replace")
            sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
            ref_page_id = f"ref__{_slugify(md_file.stem)}"
            for i, section in enumerate(sections, 1):
                section = section.strip()
                if not section or len(section.split()) < 10:
                    continue
                heading_match = re.match(r"^##\s+(.+)", section)
                title = heading_match.group(1).strip() if heading_match else md_file.stem
                all_chunks.append(_make_chunk(ref_page_id, i, title, "reference", None, section))

    chunks_path = output / "chunks.jsonl"
    with open(chunks_path, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    logger.info("  → %d total chunks", len(all_chunks))

    # Stage 3: Index
    logger.info("Stage 3: Building FTS5 index")
    db_path = output / f"{brain_id}brain.db"
    indexed = build_fts_index(chunks_path, db_path, brain_id)
    logger.info("  → %d chunks indexed", indexed)

    # Stage 4: Build manifest
    manifest = {
        "brain_id": brain_id,
        "display_name": config["display_name"],
        "chunks": indexed,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    manifest_path = output / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Empty changelog placeholder
    changelog_path = output / "operator_changelog.json"
    if not changelog_path.exists():
        changelog_path.write_text("{}")

    elapsed = time.time() - t0
    db_size = db_path.stat().st_size / 1024 / 1024
    logger.info("Done in %.1fs. DB: %.1fMB (%d chunks). Output: %s", elapsed, db_size, indexed, output)


if __name__ == "__main__":
    main()
