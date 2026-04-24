#!/usr/bin/env python3
"""Build the TDPilot docs brain from scraped HTML files.

Usage:
    python scripts/build_docs_brain.py --source /path/to/docs.derivative.ca/
    python scripts/build_docs_brain.py  # uses TDPILOT_DOCS_SCRAPE_PATH env var
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from td_mcp.knowledge.docsbrain.chunker import chunk_page, write_chunks_jsonl
from td_mcp.knowledge.docsbrain.indexer import build_index
from td_mcp.knowledge.docsbrain.normalizer import normalize_directory, write_pages_jsonl
from td_mcp.knowledge.docsbrain.release_parser import build_release_artifacts

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the TDPilot docs brain")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to scraped docs.derivative.ca HTML files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "normalized" / "derivative",
        help="Output directory for generated files",
    )
    args = parser.parse_args()

    # Resolve source path
    source = args.source
    if source is None:
        env_path = os.environ.get("TDPILOT_DOCS_SCRAPE_PATH")
        if env_path:
            source = Path(env_path)
        else:
            logger.error("No source path. Use --source or set TDPILOT_DOCS_SCRAPE_PATH")
            sys.exit(1)

    if not source.is_dir():
        logger.error("Source directory not found: %s", source)
        sys.exit(1)

    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    # Stage 1: Normalize
    logger.info("Stage 1: Normalizing HTML files from %s", source)
    pages_path = output / "pages.jsonl"
    pages = normalize_directory(source)
    page_count = write_pages_jsonl(pages, pages_path)
    logger.info("  → %d pages normalized", page_count)

    # Stage 2: Chunk
    logger.info("Stage 2: Chunking pages")
    all_chunks: list[dict] = []
    with open(pages_path, encoding="utf-8") as f:
        for line in f:
            page = json.loads(line)
            # Reconstruct the HTML path from page URL
            page_name = page["url"].replace("https://docs.derivative.ca/", "")
            html_path = source / f"{page_name}.html"
            if html_path.exists():
                chunks = chunk_page(page, html_path)
                all_chunks.extend(chunks)

    chunks_path = output / "chunks.jsonl"
    chunk_count = write_chunks_jsonl(all_chunks, chunks_path)
    logger.info("  → %d chunks created", chunk_count)

    # Stage 3: Index
    logger.info("Stage 3: Building FTS5 index")
    db_path = output / "docsbrain.db"
    indexed = build_index(chunks_path, db_path)
    logger.info("  → %d chunks indexed", indexed)

    # Stage 4: Release notes
    logger.info("Stage 4: Building release note artifacts")
    manifest, changelog = build_release_artifacts(chunks_path, output)
    logger.info(
        "  → %d builds, %d operators with changelog",
        len(manifest.get("builds", [])),
        len(changelog),
    )

    elapsed = time.time() - t0
    logger.info("Done in %.1fs. Output: %s", elapsed, output)


if __name__ == "__main__":
    main()
