#!/usr/bin/env python3
"""Generate POPX skill reference files from local docs and example metadata."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

DEFAULT_EXPORT_PATH = Path(__file__).resolve().parent.parent / "references" / "raw-example-export.pyrepr"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "references"

GENERIC_PAGES = {
    "",
    "About",
    "Children",
    "Common",
    "Custom",
    "Drag/Drop",
    "Extensions",
    "Instance",
    "Instance 2",
    "Layout",
    "Look",
    "Panel",
}

IGNORE_PARAM_NAMES = {
    "Toxsavebuild",
    "Version",
    "dropparm",
    "ext0object",
    "ext0promote",
    "externaltox",
    "opviewer",
    "pageindex",
    "parentshortcut",
}


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def text_or_empty(node: Tag | None) -> str:
    if node is None:
        return ""
    return normalize_space(node.get_text(" ", strip=True))


def first_paragraphs(main: Tag, count: int = 3) -> list[str]:
    paragraphs: list[str] = []
    for child in main.find_all(["section", "p"], recursive=False):
        if child.name == "p":
            text = text_or_empty(child)
            if text:
                paragraphs.append(text)
        elif child.name == "section":
            for p in child.find_all("p", recursive=False):
                text = text_or_empty(p)
                if text:
                    paragraphs.append(text)
            if paragraphs:
                break
        if len(paragraphs) >= count:
            break
    return paragraphs[:count]


def parse_options(group: Tag) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for option in group.select(".param-subparam"):
        label = text_or_empty(option.select_one(".param-label"))
        name = text_or_empty(option.select_one(".param-name"))
        if label or name:
            options.append({"label": label, "name": name})
    return options


def parse_parameter_blocks(section: Tag) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for node in section.find_all(["div"], recursive=False):
        classes = set(node.get("class", []))
        if "parameter-item" in classes:
            items.append(
                {
                    "kind": "parameter",
                    "label": text_or_empty(node.select_one(".param-label")),
                    "name": text_or_empty(node.select_one(".param-name")),
                    "description": text_or_empty(node.select_one(".param-description")),
                    "options": [],
                }
            )
        elif "param-group" in classes:
            items.append(
                {
                    "kind": "group",
                    "label": text_or_empty(node.select_one(".param-label")),
                    "name": text_or_empty(node.select_one(".param-name")),
                    "description": text_or_empty(node.select_one(".param-group-description")),
                    "options": parse_options(node),
                }
            )
    return [item for item in items if item["label"] or item["name"]]


def parse_parameter_pages(main: Tag) -> list[dict[str, Any]]:
    headings = list(main.select("h3.page-heading"))
    if not headings:
        return []
    pages: list[dict[str, Any]] = []
    for heading in headings:
        page_name = text_or_empty(heading)
        current = heading.next_sibling
        blocks: list[dict[str, Any]] = []
        while current is not None:
            if (
                isinstance(current, Tag)
                and current.name == "h3"
                and "page-heading" in current.get("class", [])
            ):
                break
            if isinstance(current, Tag):
                blocks.extend(parse_parameter_blocks(current))
            current = current.next_sibling
        if blocks:
            pages.append(
                {
                    "page": page_name,
                    "count": len(blocks),
                    "parameters": blocks,
                }
            )
    return pages


def parse_doc_page(path: Path, docs_root: Path) -> dict[str, Any]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    main = soup.select_one("main.main-content")

    rel_path = path.relative_to(docs_root).as_posix()
    rel_parts = rel_path.split("/")
    if main is None:
        refresh = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
        target = ""
        if refresh and refresh.get("content"):
            match = re.search(r"url=(.+)$", refresh["content"], re.I)
            if match:
                target = normalize_space(match.group(1))
        title = normalize_space(soup.title.get_text(" ", strip=True)) if soup.title else rel_parts[-2]
        return {
            "title": title,
            "version": "",
            "meta_description": f"Redirect page to {target}" if target else "Redirect page",
            "summary": [f"This page redirects to `{target}`."]
            if target
            else ["This page redirects elsewhere in the POPX docs."],
            "headings": [],
            "category": rel_parts[0],
            "subcategory": rel_parts[1] if len(rel_parts) > 2 else "",
            "rel_path": rel_path,
            "slug": "/".join(rel_parts[:-1]).replace("/", "::"),
            "parameter_pages": [],
            "parameter_count": 0,
            "key_parameters": [],
            "redirect_target": target,
        }

    h1 = main.select_one("h1")
    title = text_or_empty(h1)
    version = text_or_empty(main.select_one(".operator-version"))
    if version and title.endswith(version):
        title = normalize_space(title[: -len(version)])
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = normalize_space(meta_tag["content"])

    summary_section = main.select_one("#summary")
    summary_paras = []
    if summary_section is not None:
        summary_paras = [text_or_empty(p) for p in summary_section.find_all("p", recursive=False)]
    if not summary_paras:
        summary_paras = first_paragraphs(main)
    summary_paras = [p for p in summary_paras if p][:3]

    parameter_pages = parse_parameter_pages(main)
    headings = [text_or_empty(tag) for tag in main.find_all(["h2", "h3"]) if text_or_empty(tag)]

    category = rel_parts[0]
    subcategory = rel_parts[1] if len(rel_parts) > 2 else ""
    slug = "/".join(rel_parts[:-1]).replace("/", "::")
    key_parameters: list[str] = []
    for page in parameter_pages:
        for item in page["parameters"]:
            label = item["label"] or item["name"]
            if label:
                key_parameters.append(label)
            if len(key_parameters) >= 12:
                break
        if len(key_parameters) >= 12:
            break

    return {
        "title": title,
        "version": version,
        "meta_description": meta_desc,
        "summary": summary_paras,
        "headings": headings,
        "category": category,
        "subcategory": subcategory,
        "rel_path": rel_path,
        "slug": slug,
        "parameter_pages": parameter_pages,
        "parameter_count": sum(page["count"] for page in parameter_pages),
        "key_parameters": key_parameters,
    }


def load_examples(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8").lstrip("\ufeff")
    data = ast.literal_eval(raw)
    if not isinstance(data, dict):
        raise ValueError("Example export must be a dict")
    return data


def keyword_set(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in re.findall(r"[a-z0-9]+", part.lower()):
            if len(token) >= 3:
                tokens.add(token)
    return tokens


def link_examples_to_docs(examples: list[dict[str, Any]], docs: list[dict[str, Any]]) -> None:
    doc_tokens: list[tuple[dict[str, Any], set[str], str]] = []
    for doc in docs:
        tokens = keyword_set(doc["title"], doc["subcategory"], doc["slug"])
        phrase = normalize_space(doc["title"])
        doc_tokens.append((doc, tokens, phrase))

    for example in examples:
        haystack = normalize_space(
            " ".join(
                [
                    example["name"],
                    example.get("description", ""),
                    " ".join(node["name"] for node in example.get("top_nodes", [])),
                ]
            )
        )
        haystack_tokens = keyword_set(
            example["name"],
            example.get("description", ""),
            " ".join(node["name"] for node in example.get("top_nodes", [])),
        )
        related: list[tuple[int, str]] = []
        for doc, tokens, phrase in doc_tokens:
            overlap = len(tokens & haystack_tokens)
            phrase_score = 0
            if phrase and phrase in haystack:
                phrase_score = 6
            score = overlap + phrase_score
            if score > 0:
                related.append((score, doc["title"]))
        related.sort(key=lambda item: (-item[0], item[1]))
        example["related_docs"] = [title for _, title in related[:6]]


def looks_like_filesystem_path(value: str) -> bool:
    if "://" in value:
        return False
    if value.startswith("/EXAMPLE_LOADER") or value.startswith("/POPX_1_2_1"):
        return False
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return True
    if value.startswith("/") and Path(value).suffix:
        return True
    return "/examples/" in value or "\\examples\\" in value


def relative_example_path(value: str, examples_root: Path | None) -> str:
    if not value:
        return value
    normalized = value.replace("\\", "/")
    if examples_root is not None:
        try:
            rel = Path(normalized).resolve().relative_to(examples_root.resolve())
            return rel.as_posix()
        except Exception:
            pass
    marker = "/examples/"
    if marker in normalized:
        suffix = normalized.split(marker, 1)[1]
        return f"examples/{suffix}"
    return Path(normalized).name


def normalize_snapshot_value(value: Any, examples_root: Path | None) -> Any:
    if isinstance(value, str):
        if looks_like_filesystem_path(value):
            return relative_example_path(value, examples_root)
        return value
    if isinstance(value, list):
        return [normalize_snapshot_value(item, examples_root) for item in value]
    if isinstance(value, dict):
        return {key: normalize_snapshot_value(item, examples_root) for key, item in value.items()}
    return value


def normalize_examples_payload(
    examples_payload: dict[str, Any], examples_root: Path | None
) -> dict[str, Any]:
    normalized = normalize_snapshot_value(examples_payload, examples_root)
    if not isinstance(normalized, dict):
        raise ValueError("Normalized example payload must be a dict")
    return normalized


def format_param(param: dict[str, Any]) -> str:
    value = param.get("value")
    if isinstance(value, list):
        rendered = ", ".join(str(v) for v in value)
        value_text = f"[{rendered}]"
    else:
        value_text = str(value)
    return f"`{param['name']}` = `{value_text}`"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def render_overview(
    docs: list[dict[str, Any]],
    examples_payload: dict[str, Any],
) -> str:
    doc_counts = Counter()
    for doc in docs:
        key = doc["category"]
        if doc["subcategory"]:
            key = f"{doc['category']}/{doc['subcategory']}"
        doc_counts[key] += 1

    lines = [
        "# POPX Overview",
        "",
        "## Snapshot",
        "",
        "- This skill uses bundled POPX references generated from a local docs mirror and a live example-loader export.",
        "- The bundled references are path-independent and remain usable if the original source folders move.",
        "- Rebuilds are optional and require explicit source paths.",
        "",
        "## Corpus",
        "",
        f"- Doc pages: {len(docs)}",
        f"- Example files: {len(examples_payload.get('examples', []))}",
        f"- POPX version in example loader: `{examples_payload.get('version', '')}`",
        f"- Project used for extraction: `{examples_payload.get('project_name', '')}`",
        "",
        "## Doc Categories",
        "",
    ]
    for key, count in sorted(doc_counts.items()):
        lines.append(f"- `{key}`: {count}")
    lines.extend(
        [
            "",
            "## How To Use These References",
            "",
            "- Open `guides.md` for installation, getting started, and release notes.",
            "- Open the operator category file that matches the requested POPX operator family.",
            "- Open `examples.md` when the user refers to a shipped example, wants a known-good setup, or wants working values from an example network.",
            "- Run `python3 scripts/search_popx_refs.py <query>` for a quick cross-reference across docs and examples.",
        ]
    )
    return "\n".join(lines)


def render_doc_group(title: str, docs: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", ""]
    if docs:
        lines.append("## Table Of Contents")
        lines.append("")
        for doc in docs:
            anchor = doc["title"].lower()
            anchor = re.sub(r"[^a-z0-9]+", "-", anchor).strip("-")
            lines.append(f"- [{doc['title']}](#{anchor})")
        lines.append("")

    for doc in docs:
        lines.append(f"## {doc['title']}")
        lines.append("")
        lines.append(f"- Source: `{doc['rel_path']}`")
        if doc["version"]:
            lines.append(f"- Version: `{doc['version']}`")
        if doc["meta_description"]:
            lines.append(f"- Meta: {doc['meta_description']}")
        if doc["summary"]:
            lines.append("- Summary:")
            for paragraph in doc["summary"]:
                lines.append(f"  {paragraph}")
        if doc["parameter_pages"]:
            page_summary = ", ".join(f"{page['page']} ({page['count']})" for page in doc["parameter_pages"])
            lines.append(f"- Parameter pages: {page_summary}")
        if doc["key_parameters"]:
            lines.append("- Key parameters: " + ", ".join(f"`{name}`" for name in doc["key_parameters"]))
        lines.append("")
    return "\n".join(lines)


def render_examples(examples_payload: dict[str, Any]) -> str:
    examples = examples_payload.get("examples", [])
    lines = [
        "# POPX Examples",
        "",
        "- Package paths below are normalized to be location-independent.",
        f"- Example count: {len(examples)}",
        f"- Loader path used for extraction: `{examples_payload.get('loader_path', '')}`",
        "",
        "## Table Of Contents",
        "",
    ]
    for example in examples:
        anchor = re.sub(r"[^a-z0-9]+", "-", example["name"].lower()).strip("-")
        lines.append(f"- [{example['name']}](#{anchor})")
    lines.append("")

    for example in examples:
        lines.append(f"## {example['name']}")
        lines.append("")
        lines.append(f"- Package item: `{example['file']}`")
        description = example.get("description", "").strip()
        if description:
            lines.append(f"- Description: {description}")
        if example.get("related_docs"):
            lines.append("- Related docs: " + ", ".join(f"`{name}`" for name in example["related_docs"]))
        top_nodes = example.get("top_nodes", [])
        if top_nodes:
            rendered = ", ".join(
                f"`{node['name']}` ({node['family']}/{node['type']})" for node in top_nodes[:14]
            )
            lines.append(f"- Top nodes: {rendered}")
        notable = example.get("notable_nodes", [])
        if notable:
            lines.append("- Working values:")
            for node in notable[:8]:
                params = node.get("interesting_params", [])[:8]
                if not params:
                    continue
                rendered = ", ".join(format_param(param) for param in params)
                lines.append(f"  `{node['name']}`: {rendered}")
        lines.append("")
    return "\n".join(lines)


def build_catalog(
    docs: list[dict[str, Any]],
    examples_payload: dict[str, Any],
) -> dict[str, Any]:
    examples = examples_payload.get("examples", [])
    link_examples_to_docs(examples, docs)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "mode": "bundled-path-independent-snapshot",
            "refresh_requires_docs_root": True,
            "refresh_examples_root_optional": True,
        },
        "counts": {
            "docs": len(docs),
            "examples": len(examples),
        },
        "docs": docs,
        "examples": examples,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-root", type=Path, default=None)
    parser.add_argument("--examples-root", type=Path, default=None)
    parser.add_argument("--example-export", type=Path, default=DEFAULT_EXPORT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    docs_root_arg = args.docs_root or (
        Path(os.environ["POPX_DOCS_ROOT"]) if os.environ.get("POPX_DOCS_ROOT") else None
    )
    if docs_root_arg is None:
        raise SystemExit("Missing docs root. Pass --docs-root or set POPX_DOCS_ROOT to rebuild references.")
    docs_root = docs_root_arg.expanduser().resolve()
    examples_root = None
    if args.examples_root is not None:
        examples_root = args.examples_root.expanduser().resolve()
    elif os.environ.get("POPX_EXAMPLES_ROOT"):
        examples_root = Path(os.environ["POPX_EXAMPLES_ROOT"]).expanduser().resolve()
    export_path = args.example_export.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    docs = [parse_doc_page(path, docs_root) for path in sorted(docs_root.rglob("index.html"))]
    examples_payload = normalize_examples_payload(load_examples(export_path), examples_root)
    catalog = build_catalog(docs, examples_payload)

    guides = [doc for doc in docs if doc["category"] in {"guides", "release-notes", "contact", "legal"}]
    groups = {
        "guides.md": ("POPX Guides", guides),
        "operators-generators.md": (
            "POPX Generators",
            [doc for doc in docs if doc["category"] == "operators" and doc["subcategory"] == "generators"],
        ),
        "operators-falloffs.md": (
            "POPX Falloffs",
            [doc for doc in docs if doc["category"] == "operators" and doc["subcategory"] == "falloffs"],
        ),
        "operators-modifiers.md": (
            "POPX Modifiers",
            [doc for doc in docs if doc["category"] == "operators" and doc["subcategory"] == "modifiers"],
        ),
        "operators-tools.md": (
            "POPX Tools",
            [doc for doc in docs if doc["category"] == "operators" and doc["subcategory"] == "tools"],
        ),
        "operators-simulations.md": (
            "POPX Simulations",
            [doc for doc in docs if doc["category"] == "operators" and doc["subcategory"] == "simulations"],
        ),
    }

    write_text(
        output_dir / "overview.md",
        render_overview(docs, examples_payload),
    )
    for filename, (title, grouped_docs) in groups.items():
        write_text(output_dir / filename, render_doc_group(title, grouped_docs))
    write_text(output_dir / "examples.md", render_examples(examples_payload))
    write_text(output_dir / "catalog.json", json.dumps(catalog, indent=2))
    write_text(output_dir / "raw-example-export.pyrepr", repr(examples_payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
