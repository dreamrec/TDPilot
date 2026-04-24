#!/usr/bin/env python3
"""Search generated POPX references."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).resolve().parent.parent / "references" / "catalog.json"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def score_text(query: str, text: str) -> int:
    if not text:
        return 0
    haystack = normalize(text)
    if query == haystack:
        return 10
    if query in haystack:
        return 4
    score = 0
    for token in query.split():
        if token in haystack:
            score += 1
    return score


def format_doc(doc: dict[str, Any], score: int) -> str:
    summary = " ".join(doc.get("summary", [])) or doc.get("meta_description", "")
    params = ", ".join(doc.get("key_parameters", [])[:6])
    return f"[doc score={score}] {doc['title']} | {doc['rel_path']}\n  summary: {summary}\n  params: {params}"


def format_example(example: dict[str, Any], score: int) -> str:
    desc = example.get("description", "")
    docs = ", ".join(example.get("related_docs", [])[:4])
    return (
        f"[example score={score}] {example['name']} | {example['file']}\n"
        f"  description: {desc}\n"
        f"  related docs: {docs}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Search query")
    parser.add_argument("--docs", action="store_true", help="Search docs only")
    parser.add_argument("--examples", action="store_true", help="Search examples only")
    parser.add_argument("--limit", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    query = normalize(args.query)
    search_docs = args.docs or not args.examples
    search_examples = args.examples or not args.docs

    results: list[tuple[int, str]] = []

    if search_docs:
        for doc in data.get("docs", []):
            score = 0
            score += score_text(query, doc.get("title", "")) * 3
            score += score_text(query, doc.get("meta_description", ""))
            score += score_text(query, " ".join(doc.get("summary", []))) * 2
            score += score_text(query, " ".join(doc.get("key_parameters", [])))
            if score:
                results.append((score, format_doc(doc, score)))

    if search_examples:
        for example in data.get("examples", []):
            score = 0
            score += score_text(query, example.get("name", "")) * 3
            score += score_text(query, example.get("description", "")) * 2
            score += score_text(query, " ".join(example.get("related_docs", [])))
            score += score_text(
                query,
                " ".join(node.get("name", "") for node in example.get("top_nodes", [])),
            )
            if score:
                results.append((score, format_example(example, score)))

    results.sort(key=lambda item: (-item[0], item[1]))
    for _, rendered in results[: args.limit]:
        print(rendered)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
