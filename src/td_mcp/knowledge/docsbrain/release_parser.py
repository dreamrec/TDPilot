"""Release parser — builds build manifest and per-operator changelog from chunks."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _parse_build_sort_key(build: str) -> int:
    """Convert build string to sortable integer. E.g. '2025.32460' -> 202532460."""
    try:
        parts = build.split(".")
        return int(parts[0]) * 100000 + int(parts[1])
    except (IndexError, ValueError):
        return 0


def _extract_operator_bullet(content: str, operator_name: str) -> str:
    """Extract the specific bullet text for an operator from chunk content."""
    # Look for lines starting with the operator name
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith(operator_name):
            # Strip the operator name prefix and separator
            text = re.sub(rf"^{re.escape(operator_name)}\s*[-\u2013\u2014:]\s*", "", line)
            return text.strip()
    # Fallback: return first mention context
    return content[:200]


def build_release_artifacts(
    chunks_path: Path, output_dir: Path
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Build build_manifest.json and operator_changelog.json from release note chunks.

    Args:
        chunks_path: Path to chunks.jsonl.
        output_dir: Directory to write output files.

    Returns:
        Tuple of (manifest_dict, changelog_dict).
    """
    builds: dict[str, dict[str, Any]] = {}
    changelog: dict[str, list[dict[str, Any]]] = defaultdict(list)

    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            if chunk["doc_type"] != "release_notes":
                continue
            build_num = chunk.get("build_number")
            if not build_num:
                continue

            # Track build info
            if build_num not in builds:
                builds[build_num] = {
                    "build": build_num,
                    "date": chunk.get("build_date", ""),
                }

            # Extract per-operator entries
            category = chunk.get("change_category", "other")
            content = chunk.get("content", "")
            for op_name in chunk.get("mentioned_operators", []):
                bullet_text = _extract_operator_bullet(content, op_name)
                changelog[op_name].append(
                    {
                        "build": build_num,
                        "category": category,
                        "text": bullet_text,
                    }
                )

    # Sort builds newest first
    sorted_builds = sorted(
        builds.values(),
        key=lambda b: _parse_build_sort_key(b["build"]),
        reverse=True,
    )

    manifest = {
        "latest_build": sorted_builds[0]["build"] if sorted_builds else "",
        "latest_date": sorted_builds[0].get("date", "") if sorted_builds else "",
        "builds": sorted_builds,
    }

    # Write to disk
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    changelog_path = output_dir / "operator_changelog.json"
    changelog_path.write_text(json.dumps(dict(changelog), indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(
        "Release artifacts: %d builds, %d operators with changelog entries",
        len(sorted_builds),
        len(changelog),
    )

    return manifest, dict(changelog)
