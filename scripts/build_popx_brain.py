#!/usr/bin/env python3
"""Build the TDPilot POPx brain from scraped popsextension.com HTML files.

Usage:
    python scripts/build_popx_brain.py --source /path/to/popsextension.com/
    python scripts/build_popx_brain.py  # uses TDPILOT_POPX_SCRAPE_PATH env var
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Page classification ──────────────────────────────────────────────

# Category from URL path: docs/operators/falloffs/* → operator_falloff
_CATEGORY_MAP = {
    "falloffs": "operator_falloff",
    "generators": "operator_generator",
    "modifiers": "operator_modifier",
    "simulations": "operator_simulation",
    "tools": "operator_tool",
}

_POPX_VERSION_RE = re.compile(r"v(\d+\.\d+\.\d+)")


def classify_popx_page(rel_path: str) -> str | None:
    """Classify a POPx page by its path relative to site root."""
    parts = rel_path.replace("\\", "/").split("/")
    # docs/operators/{category}/{name}/index.html
    if "operators" in parts:
        idx = parts.index("operators")
        if idx + 1 < len(parts):
            cat = parts[idx + 1]
            return _CATEGORY_MAP.get(cat, "operator")
    if "guides" in parts:
        return "guide"
    if "release-notes" in parts:
        return "release_notes"
    if "contact" in parts:
        return None  # skip contact pages
    if rel_path.endswith("index.html") and parts[0] != "docs":
        return "homepage"
    return "general"


def derive_popx_page_id(rel_path: str) -> str:
    """Derive stable page ID from relative path."""
    page_id = rel_path.replace("\\", "/")
    page_id = page_id.replace("/index.html", "")
    page_id = page_id.lower().replace("/", "__").replace("-", "_")
    return page_id


def derive_popx_url(rel_path: str) -> str:
    """Reconstruct source URL."""
    clean = rel_path.replace("\\", "/").replace("/index.html", "")
    return f"https://www.popsextension.com/{clean}"


def extract_popx_operator_category(rel_path: str) -> str | None:
    """Extract operator category (falloffs, generators, etc.)."""
    parts = rel_path.replace("\\", "/").split("/")
    if "operators" in parts:
        idx = parts.index("operators")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def extract_popx_operator_name(rel_path: str) -> str | None:
    """Extract operator name from path like docs/operators/modifiers/pivot/."""
    parts = rel_path.replace("\\", "/").split("/")
    if "operators" in parts:
        idx = parts.index("operators")
        if idx + 2 < len(parts):
            name = parts[idx + 2]
            # Title-case: "move-along-curve" → "Move Along Curve"
            return name.replace("-", " ").title()
    return None


def slugify(text: str) -> str:
    """Convert heading to slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


# ── Normalizer ───────────────────────────────────────────────────────

# Boilerplate selectors to strip
_STRIP_SELECTORS = ["script", "style", "#navbar-container", "#sidebar-container", "#mobile-menu-container"]


def normalize_popx_file(filepath: Path, rel_path: str) -> dict[str, Any] | None:
    """Normalize one POPx HTML page."""
    doc_type = classify_popx_page(rel_path)
    if doc_type is None:
        return None

    try:
        html = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", filepath, exc)
        return None

    soup = BeautifulSoup(html, "html.parser")

    # POPx content lives in <main class="main-content">
    content_div = soup.find("main", class_="main-content")
    if content_div is None:
        logger.warning("No <main class='main-content'> in %s", rel_path)
        return None

    # Extract title from <h1>
    h1 = content_div.find("h1")
    title = ""
    if h1:
        # Strip version span
        version_span = h1.find("span", class_="operator-version")
        version = ""
        if version_span:
            version = version_span.get_text(strip=True)
            version_span.decompose()
        title = h1.get_text(strip=True)

    # Extract headings
    headings = [tag.get_text(strip=True) for tag in content_div.find_all(["h2", "h3", "h4"])]

    # Strip boilerplate
    for sel in _STRIP_SELECTORS:
        for el in content_div.select(sel):
            el.decompose()

    text = content_div.get_text(separator="\n", strip=True)
    if not text.strip():
        return None

    return {
        "page_id": derive_popx_page_id(rel_path),
        "url": derive_popx_url(rel_path),
        "title": title,
        "doc_type": doc_type,
        "operator_category": extract_popx_operator_category(rel_path),
        "operator_name": extract_popx_operator_name(rel_path),
        "headings": headings,
        "text": text,
        "text_hash": hashlib.sha256(text.encode()).hexdigest(),
    }


def normalize_popx_directory(site_dir: Path) -> Iterator[dict[str, Any]]:
    """Normalize all HTML in a POPx scrape directory."""
    if not site_dir.is_dir():
        raise FileNotFoundError(f"Not found: {site_dir}")
    for filepath in sorted(site_dir.rglob("*.html")):
        rel = str(filepath.relative_to(site_dir))
        record = normalize_popx_file(filepath, rel)
        if record is not None:
            yield record


# ── Chunker ──────────────────────────────────────────────────────────


def _extract_parameters(section: Tag) -> list[dict[str, str]]:
    """Extract structured parameters from POPx parameter divs."""
    params = []
    for item in section.select(".parameter-item, .param-group"):
        label_el = item.select_one(".param-label")
        name_el = item.select_one(".param-name")
        desc_el = item.select_one(".param-description, .param-group-description")
        if label_el:
            params.append(
                {
                    "label": label_el.get_text(strip=True),
                    "name": name_el.get_text(strip=True) if name_el else "",
                    "description": desc_el.get_text(strip=True) if desc_el else "",
                }
            )
    return params


def _section_text(section_tag: Tag) -> str:
    """Get clean text from a section."""
    return section_tag.get_text(separator="\n", strip=True)


def _token_estimate(text: str) -> int:
    return int(len(text.split()) * 1.3)


def chunk_popx_page(page: dict[str, Any], html_path: Path) -> list[dict[str, Any]]:
    """Split a POPx page into chunks by <section> and <h2>/<h3>."""
    try:
        html = html_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main", class_="main-content")
    if main is None:
        return []

    # Strip nav/scripts
    for sel in _STRIP_SELECTORS:
        for el in main.select(sel):
            el.decompose()

    chunks = []
    page_id = page["page_id"]
    doc_type = page["doc_type"]
    op_name = page.get("operator_name")
    op_cat = page.get("operator_category")
    seq = 0

    # Try section-based chunking first (POPx uses <section id="...">)
    sections = main.find_all("section")

    if sections:
        for section in sections:
            section_id = section.get("id", "")
            heading = section.find(["h2", "h3"])
            section_title = heading.get_text(strip=True) if heading else section_id.replace("-", " ").title()

            text = _section_text(section)
            if not text or len(text.split()) < 5:
                continue

            # Extract parameter names if this is the Parameters section
            param_names = []
            if section_id == "parameters" or "parameter" in section_title.lower():
                params = _extract_parameters(section)
                param_names = [p["label"] for p in params]

            seq += 1
            slug = slugify(section_title)
            chunk_id = f"{page_id}__{slug}__{seq:04d}"

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "page_id": page_id,
                    "doc_type": doc_type,
                    "section_title": section_title,
                    "operator_family": op_cat,
                    "operator_name": op_name,
                    "mentioned_operators": [],
                    "parameter_names": param_names,
                    "python_symbols": [],
                    "build_number": None,
                    "build_date": None,
                    "change_category": None,
                    "token_estimate": _token_estimate(text),
                    "content": text,
                }
            )
    else:
        # Fallback: heading-based chunking
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
                chunks.append(
                    {
                        "chunk_id": f"{page_id}__intro__{seq:04d}",
                        "page_id": page_id,
                        "doc_type": doc_type,
                        "section_title": page["title"],
                        "operator_family": op_cat,
                        "operator_name": op_name,
                        "mentioned_operators": [],
                        "parameter_names": [],
                        "python_symbols": [],
                        "build_number": None,
                        "build_date": None,
                        "change_category": None,
                        "token_estimate": _token_estimate(intro),
                        "content": intro,
                    }
                )

            for h_tag in headings:
                h_text = h_tag.get_text(strip=True)
                # Collect content until next same-level heading
                parts = []
                current = h_tag.next_sibling
                while current:
                    if isinstance(current, Tag) and current.name in ("h2", "h3", "h4"):
                        lvl = int(current.name[1])
                        h_lvl = int(h_tag.name[1])
                        if lvl <= h_lvl:
                            break
                    if isinstance(current, Tag):
                        parts.append(current.get_text(separator="\n", strip=True))
                    current = current.next_sibling
                text = "\n".join(p for p in parts if p)
                if not text or len(text.split()) < 5:
                    continue
                seq += 1
                slug = slugify(h_text)
                chunks.append(
                    {
                        "chunk_id": f"{page_id}__{slug}__{seq:04d}",
                        "page_id": page_id,
                        "doc_type": doc_type,
                        "section_title": h_text,
                        "operator_family": op_cat,
                        "operator_name": op_name,
                        "mentioned_operators": [],
                        "parameter_names": [],
                        "python_symbols": [],
                        "build_number": None,
                        "build_date": None,
                        "change_category": None,
                        "token_estimate": _token_estimate(text),
                        "content": text,
                    }
                )
        else:
            # No structure — whole page as one chunk
            seq += 1
            chunks.append(
                {
                    "chunk_id": f"{page_id}__full__{seq:04d}",
                    "page_id": page_id,
                    "doc_type": doc_type,
                    "section_title": page["title"],
                    "operator_family": op_cat,
                    "operator_name": op_name,
                    "mentioned_operators": [],
                    "parameter_names": [],
                    "python_symbols": [],
                    "build_number": None,
                    "build_date": None,
                    "change_category": None,
                    "token_estimate": _token_estimate(page["text"]),
                    "content": page["text"],
                }
            )

    return chunks


# ── Release notes parser (POPx-specific) ─────────────────────────────

_POPX_VERSION_HEADING_RE = re.compile(r"Version\s+(\d+\.\d+(?:\.\d+)?)")


def parse_popx_releases(chunks_path: Path, output_dir: Path) -> tuple[dict, dict]:
    """Build release artifacts from POPx release note chunks."""
    builds = []
    operator_changelog: dict[str, list] = {}

    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            if chunk["doc_type"] != "release_notes":
                continue
            # Try to extract version from section title
            m = _POPX_VERSION_HEADING_RE.search(chunk["section_title"])
            if m:
                version = m.group(1)
                builds.append(
                    {
                        "version": version,
                        "content": chunk["content"][:500],
                    }
                )

    manifest = {"product": "POPx", "builds": builds}
    manifest_path = output_dir / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    changelog_path = output_dir / "operator_changelog.json"
    changelog_path.write_text(json.dumps(operator_changelog, indent=2))

    return manifest, operator_changelog


# ── Indexer (reuses same FTS5 schema as derivative brain) ─────────────

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


def build_popx_index(chunks_path: Path, db_path: Path) -> int:
    """Build SQLite FTS5 index from chunks.jsonl."""
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

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
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("brain_name", "popx"),
        )

        count = 0
        with open(chunks_path, encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                # Insert into chunks table
                conn.execute(
                    """INSERT OR REPLACE INTO chunks
                       (chunk_id, page_id, doc_type, section_title, operator_family,
                        operator_name, mentioned_operators, parameter_names,
                        python_symbols, build_number, build_date, change_category,
                        token_estimate, content)
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
                # Insert into FTS5
                conn.execute(
                    """INSERT INTO chunks_fts
                       (chunk_id, section_title, operator_name, parameter_names,
                        python_symbols, content)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        chunk["chunk_id"],
                        chunk.get("section_title", ""),
                        chunk.get("operator_name", ""),
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


# ── Refs repo ingestion (catalog.json + markdown) ────────────────────


def _chunk_catalog_examples(catalog_path: Path) -> list[dict[str, Any]]:
    """Create chunks from catalog.json examples — one chunk per example."""
    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)

    chunks = []
    for i, ex in enumerate(catalog.get("examples", []), 1):
        name = ex.get("name", f"example_{i}")
        desc = ex.get("description", "")
        nodes = ex.get("top_nodes", [])
        node_text = "\n".join(
            f"  - {n['name']} ({n['type']} {n['family']}): pages={', '.join(n.get('custom_pages', []))}"
            for n in nodes
        )
        content = f"Example: {name}\n\n{desc}"
        if node_text:
            content += f"\n\nNodes:\n{node_text}"

        chunk_id = f"catalog_example__{slugify(name)}__{i:04d}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "page_id": "catalog__examples",
                "doc_type": "example",
                "section_title": f"Example: {name}",
                "operator_family": None,
                "operator_name": None,
                "mentioned_operators": [],
                "parameter_names": [],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": _token_estimate(content),
                "content": content,
            }
        )

    # Also create chunks from catalog docs entries (structured summaries)
    for i, doc in enumerate(catalog.get("docs", []), 1):
        title = doc.get("title", "")
        summary = "\n".join(doc.get("summary", []))
        meta = doc.get("meta_description", "")
        cat = doc.get("category", "")
        subcat = doc.get("subcategory", "")

        if not summary and not meta:
            continue

        content = f"{title}\n\n{meta}\n\n{summary}" if summary else f"{title}\n\n{meta}"
        op_name = title if cat == "operators" else None
        op_family = subcat if cat == "operators" else None

        chunk_id = f"catalog_doc__{slugify(title)}__{i:04d}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "page_id": f"catalog__{slugify(doc.get('slug', title))}",
                "doc_type": f"catalog_{cat}",
                "section_title": f"{title} (catalog summary)",
                "operator_family": op_family,
                "operator_name": op_name,
                "mentioned_operators": [],
                "parameter_names": [p.get("label", "") for p in doc.get("key_parameters", [])],
                "python_symbols": [],
                "build_number": None,
                "build_date": None,
                "change_category": None,
                "token_estimate": _token_estimate(content),
                "content": content,
            }
        )

    return chunks


def _chunk_markdown_refs(refs_dir: Path) -> list[dict[str, Any]]:
    """Create chunks from the markdown reference files."""
    chunks = []
    for md_file in sorted(refs_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue

        # Split by ## headings
        sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
        page_id = f"ref__{slugify(md_file.stem)}"

        for i, section in enumerate(sections, 1):
            section = section.strip()
            if not section or len(section.split()) < 10:
                continue

            # Extract heading
            heading_match = re.match(r"^##\s+(.+)", section)
            section_title = heading_match.group(1).strip() if heading_match else md_file.stem

            chunk_id = f"{page_id}__{slugify(section_title)}__{i:04d}"

            # Try to extract operator name from section title
            op_name = None
            if md_file.stem.startswith("operators-"):
                # Sections like "## Pivot" in operators-modifiers.md
                if heading_match and not heading_match.group(1).startswith("#"):
                    op_name = heading_match.group(1).strip()

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "page_id": page_id,
                    "doc_type": "reference",
                    "section_title": section_title,
                    "operator_family": md_file.stem.replace("operators-", "")
                    if md_file.stem.startswith("operators-")
                    else None,
                    "operator_name": op_name,
                    "mentioned_operators": [],
                    "parameter_names": [],
                    "python_symbols": [],
                    "build_number": None,
                    "build_date": None,
                    "change_category": None,
                    "token_estimate": _token_estimate(section),
                    "content": section,
                }
            )

    return chunks


# ── Main pipeline ────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the TDPilot POPx brain")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to scraped popsextension.com site root",
    )
    parser.add_argument(
        "--refs",
        type=Path,
        default=None,
        help="Path to TDPilot-popx-refs repo (catalog.json + markdown files)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "normalized" / "popx",
        help="Output directory for generated files",
    )
    args = parser.parse_args()

    source = args.source
    if source is None:
        env_path = os.environ.get("TDPILOT_POPX_SCRAPE_PATH")
        if env_path:
            source = Path(env_path)
        else:
            logger.error("No source path. Use --source or set TDPILOT_POPX_SCRAPE_PATH")
            sys.exit(1)

    if not source.is_dir():
        logger.error("Source directory not found: %s", source)
        sys.exit(1)

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    # Stage 1: Normalize
    logger.info("Stage 1: Normalizing POPx HTML from %s", source)
    pages_path = output / "pages.jsonl"
    count = 0
    with open(pages_path, "w", encoding="utf-8") as f:
        for page in normalize_popx_directory(source):
            f.write(json.dumps(page, ensure_ascii=False) + "\n")
            count += 1
    logger.info("  → %d pages normalized", count)

    # Stage 2: Chunk HTML pages
    logger.info("Stage 2: Chunking pages")
    all_chunks: list[dict] = []
    with open(pages_path, encoding="utf-8") as f:
        for line in f:
            page = json.loads(line)
            # Reconstruct HTML path from relative URL
            url_path = page["url"].replace("https://www.popsextension.com/", "")
            html_path = source / url_path / "index.html"
            if not html_path.exists():
                html_path = source / f"{url_path}.html"
            if not html_path.exists() and url_path == "":
                html_path = source / "index.html"
            if html_path.exists():
                chunks = chunk_popx_page(page, html_path)
                all_chunks.extend(chunks)
    logger.info("  → %d chunks from HTML", len(all_chunks))

    # Stage 2b: Ingest popx-refs repo if provided
    refs = args.refs
    if refs is None:
        env_refs = os.environ.get("TDPILOT_POPX_REFS_PATH")
        if env_refs:
            refs = Path(env_refs)
    if refs and refs.is_dir():
        logger.info("Stage 2b: Ingesting popx-refs from %s", refs)
        catalog_path = refs / "catalog.json"
        if catalog_path.exists():
            cat_chunks = _chunk_catalog_examples(catalog_path)
            all_chunks.extend(cat_chunks)
            logger.info("  → %d chunks from catalog.json", len(cat_chunks))
        md_chunks = _chunk_markdown_refs(refs)
        all_chunks.extend(md_chunks)
        logger.info("  → %d chunks from markdown refs", len(md_chunks))

    chunks_path = output / "chunks.jsonl"
    with open(chunks_path, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    logger.info("  → %d total chunks", len(all_chunks))

    # Stage 3: Index
    logger.info("Stage 3: Building FTS5 index")
    db_path = output / "popxbrain.db"
    indexed = build_popx_index(chunks_path, db_path)
    logger.info("  → %d chunks indexed", indexed)

    # Stage 4: Release notes
    logger.info("Stage 4: Building release artifacts")
    manifest, changelog = parse_popx_releases(chunks_path, output)
    logger.info("  → %d versions tracked", len(manifest.get("builds", [])))

    elapsed = time.time() - t0
    db_size = db_path.stat().st_size / 1024 / 1024
    logger.info("Done in %.1fs. DB size: %.1fMB. Output: %s", elapsed, db_size, output)


if __name__ == "__main__":
    main()
