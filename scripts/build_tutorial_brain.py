#!/usr/bin/env python3
"""Tutorial brain builder for TDPilot.

Builds an FTS5 brain from video tutorial corpora.
Unlike build_brain.py (HTML-based), this processes:
  - Transcript files (.en.txt)
  - SRT subtitles (.en.srt) for timestamp-based chunking
  - TOE/TOX project files via toeexpand for node graphs, params, GLSL/Python code

Usage:
    python scripts/build_tutorial_brain.py --config data/brains/<brain_name>.yaml \
        --source /path/to/transcripts/
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# ── toeexpand ────────────────────────────────────────────────

TOEEXPAND_PATHS = [
    "/Applications/TouchDesigner.app/Contents/MacOS/toeexpand",
    os.path.expandvars(r"%PROGRAMFILES%\Derivative\TouchDesigner\bin\toeexpand.exe"),
    shutil.which("toeexpand") or "",
]


def find_toeexpand() -> str | None:
    for p in TOEEXPAND_PATHS:
        if p and Path(p).is_file():
            return p
    return None


def expand_toe(toe_path: Path, toeexpand_bin: str) -> Path | None:
    """Run toeexpand on a .toe/.tox file. Returns path to .dir or None."""
    dir_path = toe_path.parent / f"{toe_path.name}.dir"
    toc_path = toe_path.parent / f"{toe_path.name}.toc"
    # Clean previous expansion
    if dir_path.exists():
        shutil.rmtree(dir_path)
    if toc_path.exists():
        toc_path.unlink()

    try:
        subprocess.run(
            [toeexpand_bin, str(toe_path)],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("toeexpand failed on %s: %s", toe_path.name, exc)
        return None

    if dir_path.is_dir():
        return dir_path
    return None


def extract_toe_data(dir_path: Path) -> dict[str, Any]:
    """Extract structured data from an expanded TOE directory.

    Returns:
        {
            "operators": [{"path": "project1/noise1", "type": "TOP:noise", ...}],
            "connections": [{"from": "noise2", "to": "add1", "input": 0}],
            "code_snippets": [{"path": "...", "language": "glsl|python", "code": "..."}],
            "parameters": [{"path": "...", "param": "...", "value": "..."}],
            "build_info": {"version": "...", "build": "..."},
            "operator_summary": "TOP:noise(3), TOP:feedback(2), ..."
        }
    """
    result: dict[str, Any] = {
        "operators": [],
        "connections": [],
        "code_snippets": [],
        "parameters": [],
        "build_info": {},
        "operator_summary": "",
    }

    # Parse .build info
    build_file = dir_path / ".build"
    if build_file.exists():
        for line in build_file.read_text(errors="replace").splitlines():
            if line.startswith("build "):
                result["build_info"]["build"] = line.split(" ", 1)[1].strip()
            elif line.startswith("version "):
                result["build_info"]["version"] = line.split(" ", 1)[1].strip()

    op_type_counts: dict[str, int] = {}

    # Walk all .n files (node definitions)
    for n_file in sorted(dir_path.rglob("*.n")):
        rel = str(n_file.relative_to(dir_path))
        if rel.startswith("."):
            continue  # skip .root, .grps, etc.

        try:
            content = n_file.read_text(errors="replace")
        except OSError:
            continue

        lines = content.strip().splitlines()
        if not lines:
            continue

        # First line is TYPE:subtype (e.g., "TOP:noise", "COMP:base", "DAT:text")
        type_line = lines[0].strip()
        if ":" not in type_line:
            continue

        node_path = rel.removesuffix(".n")
        op_type = type_line

        op_type_counts[op_type] = op_type_counts.get(op_type, 0) + 1

        op_info: dict[str, Any] = {"path": node_path, "type": op_type}

        # Extract input connections
        if "inputs" in content:
            in_block = False
            for line in lines:
                if line.strip() == "inputs":
                    in_block = True
                    continue
                if in_block and line.strip() == "{":
                    continue
                if in_block and line.strip() == "}":
                    break
                if in_block:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        input_idx = parts[0]
                        source_node = parts[1]
                        result["connections"].append(
                            {
                                "from": source_node,
                                "to": node_path.split("/")[-1],
                                "input": int(input_idx),
                            }
                        )

        result["operators"].append(op_info)

    # Read .parm files for interesting parameters (expressions, non-default values)
    interesting_params = set()
    for parm_file in sorted(dir_path.rglob("*.parm")):
        rel = str(parm_file.relative_to(dir_path))
        if rel.startswith("."):
            continue
        try:
            content = parm_file.read_text(errors="replace")
        except OSError:
            continue

        node_path = rel.removesuffix(".parm")
        for line in content.splitlines():
            line = line.strip()
            if not line or line == "?":
                continue
            # Format: paramname flags value [expression]
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            param_name = parts[0]
            rest = parts[2] if len(parts) > 2 else ""
            # Only capture params with expressions or non-trivial values
            if (
                "parent" in rest
                or "op(" in rest
                or "me." in rest
                or "absTime" in rest
                or "ipar" in rest
                or "mod(" in rest
            ):
                result["parameters"].append(
                    {
                        "path": node_path,
                        "param": param_name,
                        "expr": rest,
                    }
                )
                interesting_params.add(param_name)

    # Read .text files (GLSL, Python, DAT content)
    for text_file in sorted(dir_path.rglob("*.text")):
        rel = str(text_file.relative_to(dir_path))
        try:
            code = text_file.read_text(errors="replace")
        except OSError:
            continue

        # Skip tiny/empty files or boilerplate callbacks
        if len(code.strip()) < 20:
            continue
        if "def onSetupParameters" in code and len(code.strip()) < 200:
            continue  # boilerplate callback

        # Detect language
        lang = "python"
        if any(
            kw in code
            for kw in (
                "vec2",
                "vec3",
                "vec4",
                "uniform",
                "fragColor",
                "gl_",
                "void main",
                "iResolution",
                "iTime",
                "float ",
                "sampler2D",
                "#version",
            )
        ):
            lang = "glsl"

        result["code_snippets"].append(
            {
                "path": rel,
                "language": lang,
                "code": code.strip()[:2000],  # cap at 2000 chars
            }
        )

    # Build operator summary
    sorted_ops = sorted(op_type_counts.items(), key=lambda x: -x[1])
    result["operator_summary"] = ", ".join(f"{op}({c})" if c > 1 else op for op, c in sorted_ops)

    return result


def cleanup_expansion(toe_path: Path) -> None:
    """Remove .dir and .toc files created by toeexpand."""
    dir_path = toe_path.parent / f"{toe_path.name}.dir"
    toc_path = toe_path.parent / f"{toe_path.name}.toc"
    if dir_path.exists():
        shutil.rmtree(dir_path)
    if toc_path.exists():
        toc_path.unlink()


# ── ASR Cleanup ──────────────────────────────────────────────

# Common YouTube ASR errors for TouchDesigner terminology
TD_ASR_CORRECTIONS: list[tuple[str, str]] = [
    # Operator families
    (r"\bsoap\b", "SOP"),
    (r"\bchops?\b(?!\s+(?:the|up|down|off))", "CHOP"),
    (r"\btops?\b(?=\s+(?:network|operator|node|input|output|family))", "TOP"),
    (r"\bdats?\b(?=\s+(?:operator|node|table|text))", "DAT"),
    (r"\bcomps?\b(?=\s+(?:operator|node|component|editor))", "COMP"),
    # Common TD terms
    (r"\btouch\s+designer\b", "TouchDesigner"),
    (r"\bG L S L\b", "GLSL"),
    (r"\bS D F\b", "SDF"),
    (r"\bU V\b(?=\s+(?:space|coord|map|math|wrap))", "UV"),
    (r"\bnull\s+soap\b", "Null SOP"),
    (r"\bnull\s+top\b", "Null TOP"),
    (r"\bnoise\s+top\b", "Noise TOP"),
    (r"\bfeedback\s+top\b", "Feedback TOP"),
    (r"\bmath\s+top\b", "Math TOP"),
    (r"\bramp\s+top\b", "Ramp TOP"),
    (r"\blevel\s+top\b", "Level TOP"),
    (r"\bblur\s+top\b", "Blur TOP"),
    (r"\badd\s+top\b", "Add TOP"),
    (r"\bverlay\b", "Voronoi"),  # common ASR for Voronoi
]


def clean_transcript(text: str) -> str:
    """Apply TD-specific ASR corrections to transcript text."""
    for pattern, replacement in TD_ASR_CORRECTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    # Remove excessive filler words
    text = re.sub(r"\b(uh|um)\b\s*", "", text)
    # Collapse multiple spaces/newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── SRT Parser ───────────────────────────────────────────────


def parse_srt(srt_path: Path) -> list[dict[str, Any]]:
    """Parse SRT file into list of {start_ms, end_ms, text} entries."""
    try:
        content = srt_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    entries = []
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        # Find timestamp line
        ts_match = re.match(
            r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})",
            lines[1] if len(lines) > 1 else "",
        )
        if not ts_match:
            continue

        g = ts_match.groups()
        start_ms = int(g[0]) * 3600000 + int(g[1]) * 60000 + int(g[2]) * 1000 + int(g[3])
        end_ms = int(g[4]) * 3600000 + int(g[5]) * 60000 + int(g[6]) * 1000 + int(g[7])
        text = " ".join(lines[2:]).strip()
        if text:
            entries.append({"start_ms": start_ms, "end_ms": end_ms, "text": text})

    # Deduplicate rolling subtitles (YouTube SRT has overlapping entries)
    if not entries:
        return entries

    deduped = [entries[0]]
    for entry in entries[1:]:
        if entry["text"] != deduped[-1]["text"]:
            deduped.append(entry)

    return deduped


def chunk_by_time(
    srt_entries: list[dict[str, Any]],
    chunk_duration_ms: int = 120_000,  # 2-minute chunks
) -> list[dict[str, Any]]:
    """Group SRT entries into time-window chunks."""
    if not srt_entries:
        return []

    chunks = []
    current_texts: list[str] = []
    chunk_start = srt_entries[0]["start_ms"]

    for entry in srt_entries:
        if entry["start_ms"] - chunk_start >= chunk_duration_ms and current_texts:
            chunks.append(
                {
                    "start_ms": chunk_start,
                    "end_ms": entry["start_ms"],
                    "text": " ".join(current_texts),
                }
            )
            current_texts = []
            chunk_start = entry["start_ms"]
        current_texts.append(entry["text"])

    if current_texts:
        chunks.append(
            {
                "start_ms": chunk_start,
                "end_ms": srt_entries[-1]["end_ms"],
                "text": " ".join(current_texts),
            }
        )

    return chunks


def ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS format."""
    s = ms // 1000
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ── Tutorial Processing ──────────────────────────────────────


def classify_tutorial(folder_name: str) -> dict[str, str]:
    """Extract metadata from folder name."""
    match = re.match(
        r"(\d{4}-\d{2}-\d{2})\s*-\s*(.+?)(?:\s+(?:in|with)\s+[Tt]ouch[Dd]esigner)?$",
        folder_name,
    )
    if match:
        return {"date": match.group(1), "title": match.group(2).strip()}
    return {"date": "", "title": folder_name}


# Topic classification keywords
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "simulation": [
        "physarum",
        "verlet",
        "collision",
        "particle",
        "spring",
        "flock",
        "fluid",
        "belousov",
        "falling sand",
        "soft body",
        "elastic",
        "dla",
        "dlg",
        "differential growth",
        "lava lamp",
        "firework",
    ],
    "uv_math": [
        "uv ",
        "uv_",
        "melty uv",
        "uv shred",
        "uv slice",
        "uv partition",
        "uv mountain",
        "uv pick",
        "uv ruler",
        "uv cut",
        "ramp tunnel",
    ],
    "math_vectors": [
        "linear interpolation",
        "unit vector",
        "cross product",
        "perpendicular",
        "vector",
        "matrix",
        "angle",
        "line segment",
        "sdf",
        "intersection",
    ],
    "noise_procedural": ["noise", "recursive displace", "cellular", "fractal", "noisecream", "fractus"],
    "glsl_gpu": ["glsl", "compute shader", "gpu", "tops vs pops"],
    "voronoi_packing": [
        "voronoi",
        "circle packing",
        "sphere packing",
        "lloyd",
        "jfa",
        "shapes packing",
        "close-packing",
    ],
    "feedback_recursive": ["feedback", "recursive", "fdbk", "datamosh"],
    "geometry": [
        "mobius",
        "moebius",
        "snail",
        "pottery",
        "potter",
        "onion",
        "menger",
        "penrose",
        "donut",
        "mesh a spiral",
    ],
    "visual_effects": [
        "mondrian",
        "joy division",
        "ryoji ikeda",
        "kensuke koike",
        "dithering",
        "pointillism",
        "cubism",
        "stroma",
        "weaving",
        "latte art",
    ],
    "algorithmic": [
        "mandelbrot",
        "truchet",
        "substrate",
        "random walker",
        "sokoban",
        "abacus",
        "hex grid",
        "labyrinth",
    ],
}


def classify_topic(title: str) -> str:
    title_lower = title.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                return topic
    return "technique"


def process_tutorial(
    folder_path: Path,
    toeexpand_bin: str | None,
    chunk_duration_ms: int = 120_000,
) -> list[dict[str, Any]]:
    """Process a single tutorial folder into chunks."""
    folder_name = folder_path.name
    meta = classify_tutorial(folder_name)
    topic = classify_topic(meta["title"])

    # Find transcript and SRT
    txt_files = list(folder_path.glob("*.en.txt"))
    srt_files = list(folder_path.glob("*.en.srt"))

    if not txt_files and not srt_files:
        # Check for TOE files even without transcript (teasers with projects)
        toe_files = list(folder_path.glob("*.toe")) + list(folder_path.glob("*.tox"))
        if not toe_files or not toeexpand_bin:
            return []  # truly nothing to process

    # Count frames for metadata
    frames_dir = folder_path / "frames"
    frame_count = len(list(frames_dir.glob("*.png"))) if frames_dir.is_dir() else 0

    # Find TOE/TOX files
    toe_files = list(folder_path.glob("*.toe")) + list(folder_path.glob("*.tox"))

    # Extract TOE data if toeexpand is available
    toe_data_list: list[dict[str, Any]] = []
    if toeexpand_bin and toe_files:
        for toe_file in toe_files:
            dir_path = expand_toe(toe_file, toeexpand_bin)
            if dir_path:
                data = extract_toe_data(dir_path)
                data["toe_name"] = toe_file.stem
                toe_data_list.append(data)
                cleanup_expansion(toe_file)

    # Merge TOE data into a single summary
    all_operators: list[str] = []
    all_connections: list[str] = []
    all_code: list[dict[str, str]] = []
    all_params: list[str] = []
    all_op_summaries: list[str] = []

    for td in toe_data_list:
        all_op_summaries.append(f"[{td['toe_name']}] {td.get('operator_summary', '')}")
        for op in td.get("operators", []):
            all_operators.append(f"{op['path']} ({op['type']})")
        for conn in td.get("connections", []):
            all_connections.append(f"{conn['from']} -> {conn['to']}")
        for snippet in td.get("code_snippets", []):
            all_code.append(snippet)
        for p in td.get("parameters", []):
            all_params.append(f"{p['path']}.{p['param']} = {p['expr']}")

    # Build TOE context string (appended to transcript chunks)
    toe_context_parts: list[str] = []
    if all_op_summaries:
        toe_context_parts.append("Operators: " + "; ".join(all_op_summaries))
    if all_connections:
        # Show unique connections, cap at 30
        unique_conns = list(dict.fromkeys(all_connections))[:30]
        toe_context_parts.append("Connections: " + ", ".join(unique_conns))
    if all_params:
        toe_context_parts.append("Expressions: " + "; ".join(all_params[:20]))

    toe_context = "\n".join(toe_context_parts)

    # Build code chunks (separate chunks for significant code)
    code_chunks: list[dict[str, Any]] = []
    for snippet in all_code:
        lang = snippet["language"]
        code = snippet["code"]
        if len(code.split()) < 10:
            continue
        slug = re.sub(r"[^a-z0-9]+", "_", snippet["path"].lower()).strip("_")
        chunk_id = f"tutorial__{_slugify(meta['title'])}__{lang}_{slug}"
        code_chunks.append(
            {
                "chunk_id": chunk_id,
                "page_id": f"tutorial__{_slugify(meta['title'])}",
                "doc_type": "tutorial_code",
                "section_title": f"{meta['title']} -- {lang.upper()} ({snippet['path']})",
                "operator_family": None,
                "operator_name": None,
                "mentioned_operators": [],
                "parameter_names": [],
                "python_symbols": [],
                "build_number": None,
                "build_date": meta["date"],
                "change_category": topic,
                "token_estimate": _token_estimate(code),
                "content": f"```{lang}\n{code}\n```",
                "source": "toeexpand",
                "url": "",
            }
        )

    # Chunk transcript by time
    chunks: list[dict[str, Any]] = []
    page_id = f"tutorial__{_slugify(meta['title'])}"

    if srt_files:
        srt_entries = parse_srt(srt_files[0])
        time_chunks = chunk_by_time(srt_entries, chunk_duration_ms)

        for i, tc in enumerate(time_chunks, 1):
            text = clean_transcript(tc["text"])
            if len(text.split()) < 15:
                continue

            ts_start = ms_to_timestamp(tc["start_ms"])
            ts_end = ms_to_timestamp(tc["end_ms"])
            section = f"{meta['title']} [{ts_start}--{ts_end}]"

            # Append TOE context to first chunk only (keeps it searchable)
            content = text
            if i == 1 and toe_context:
                content = f"{text}\n\n--- Project Structure ---\n{toe_context}"

            mentioned_ops = _extract_mentioned_operators(text)

            chunks.append(
                {
                    "chunk_id": f"{page_id}__t{i:04d}",
                    "page_id": page_id,
                    "doc_type": "tutorial",
                    "section_title": section,
                    "operator_family": None,
                    "operator_name": None,
                    "mentioned_operators": mentioned_ops,
                    "parameter_names": [],
                    "python_symbols": [],
                    "build_number": None,
                    "build_date": meta["date"],
                    "change_category": topic,
                    "token_estimate": _token_estimate(content),
                    "content": content,
                    "source": "transcript",
                    "url": "",
                }
            )
    elif txt_files:
        # Fallback: chunk plain transcript by word count
        text = clean_transcript(txt_files[0].read_text(encoding="utf-8", errors="replace"))
        words = text.split()
        chunk_size = 400  # ~400 words per chunk
        for i in range(0, len(words), chunk_size):
            chunk_text = " ".join(words[i : i + chunk_size])
            if len(chunk_text.split()) < 15:
                continue

            content = chunk_text
            if i == 0 and toe_context:
                content = f"{chunk_text}\n\n--- Project Structure ---\n{toe_context}"

            mentioned_ops = _extract_mentioned_operators(chunk_text)

            chunks.append(
                {
                    "chunk_id": f"{page_id}__w{i // chunk_size + 1:04d}",
                    "page_id": page_id,
                    "doc_type": "tutorial",
                    "section_title": meta["title"],
                    "operator_family": None,
                    "operator_name": None,
                    "mentioned_operators": mentioned_ops,
                    "parameter_names": [],
                    "python_symbols": [],
                    "build_number": None,
                    "build_date": meta["date"],
                    "change_category": topic,
                    "token_estimate": _token_estimate(content),
                    "content": content,
                    "source": "transcript",
                    "url": "",
                }
            )

    # Add a project overview chunk if we have TOE data and no transcript chunks
    if toe_data_list and not chunks:
        overview = f"Project: {meta['title']}\nDate: {meta['date']}\n"
        if toe_context:
            overview += f"\n{toe_context}"
        chunks.append(
            {
                "chunk_id": f"{page_id}__overview",
                "page_id": page_id,
                "doc_type": "tutorial_project",
                "section_title": f"{meta['title']} -- Project Overview",
                "operator_family": None,
                "operator_name": None,
                "mentioned_operators": [],
                "parameter_names": [],
                "python_symbols": [],
                "build_number": None,
                "build_date": meta["date"],
                "change_category": topic,
                "token_estimate": _token_estimate(overview),
                "content": overview,
                "source": "toeexpand",
                "url": "",
            }
        )

    # Add code chunks
    chunks.extend(code_chunks)

    return chunks


# ── Helpers ──────────────────────────────────────────────────


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def _token_estimate(text: str) -> int:
    return int(len(text.split()) * 1.3)


TD_OPERATOR_PATTERN = re.compile(
    r"\b(noise|feedback|ramp|math|level|blur|add|subtract|multiply|"
    r"composite|over|switch|crop|flip|transform|reorder|select|null|"
    r"constant|circle|grid|rectangle|sphere|torus|line|merge|"
    r"limit|diff|function|render|geo|camera|light|material|"
    r"chop\s+to|sop\s+to|top\s+to|dat\s+to|"
    r"script|text|table|"
    r"glsl|point\s*transform|cross|displace|"
    r"movie\s*file\s*in|cache|resolution|speed|trail)\b",
    re.IGNORECASE,
)

TD_FAMILY_PATTERN = re.compile(r"\b(TOP|SOP|CHOP|DAT|COMP|MAT)\b")


def _extract_mentioned_operators(text: str) -> list[str]:
    """Extract TD operator names mentioned in transcript text."""
    ops = set()
    for match in TD_OPERATOR_PATTERN.finditer(text):
        ops.add(match.group(0).strip().lower())
    for match in TD_FAMILY_PATTERN.finditer(text):
        ops.add(match.group(0))
    return sorted(ops)[:20]  # cap at 20


# ── FTS5 Indexer ─────────────────────────────────────────────


def build_fts_index(chunks: list[dict[str, Any]], db_path: Path, brain_id: str) -> int:
    """Build SQLite FTS5 index from chunk list."""
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
                source TEXT DEFAULT 'transcript',
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
        for chunk in chunks:
            conn.execute(
                """INSERT OR REPLACE INTO chunks
                   (chunk_id, page_id, url, doc_type, section_title,
                    operator_family, operator_name, mentioned_operators,
                    parameter_names, python_symbols, build_number,
                    build_date, change_category, source, token_estimate, content)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    chunk["chunk_id"],
                    chunk["page_id"],
                    chunk.get("url", ""),
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
                    chunk.get("source", "transcript"),
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
                    " ".join(
                        filter(None, [chunk.get("operator_name", ""), *chunk.get("mentioned_operators", [])])
                    ),
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


# ── Main Pipeline ────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tutorial brain builder for TDPilot",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to brain config YAML",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to tutorial corpus root directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: data/normalized/<brain_id>/)",
    )
    parser.add_argument(
        "--no-toeexpand",
        action="store_true",
        help="Skip TOE/TOX expansion (transcript-only mode)",
    )
    parser.add_argument(
        "--toeexpand-bin",
        type=str,
        default=None,
        help="Path to toeexpand binary",
    )
    parser.add_argument(
        "--chunk-duration",
        type=int,
        default=120,
        help="Chunk duration in seconds (default: 120)",
    )
    args = parser.parse_args()

    if yaml is None:
        logger.error("pyyaml is required: pip install pyyaml")
        sys.exit(1)

    config = yaml.safe_load(args.config.read_text("utf-8"))
    brain_id = config["brain_id"]

    if not args.source.is_dir():
        logger.error("Source directory not found: %s", args.source)
        sys.exit(1)

    output = args.output or (Path(__file__).resolve().parent.parent / "data" / "normalized" / brain_id)
    output.mkdir(parents=True, exist_ok=True)

    # Find toeexpand
    toeexpand_bin: str | None = None
    if not args.no_toeexpand:
        toeexpand_bin = args.toeexpand_bin or find_toeexpand()
        if toeexpand_bin:
            logger.info("Using toeexpand: %s", toeexpand_bin)
        else:
            logger.warning("toeexpand not found -- running in transcript-only mode")

    t0 = time.time()

    # Stage 1: Discover tutorials
    logger.info("Stage 1: Discovering tutorials in %s", args.source)
    tutorial_dirs = sorted(
        [d for d in args.source.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]
    )
    logger.info("  -> %d tutorial folders found", len(tutorial_dirs))

    # Stage 2: Process tutorials
    logger.info("Stage 2: Processing tutorials (toeexpand=%s)", bool(toeexpand_bin))
    all_chunks: list[dict[str, Any]] = []
    processed = 0
    skipped = 0
    toe_count = 0
    chunk_duration_ms = args.chunk_duration * 1000

    for i, folder in enumerate(tutorial_dirs, 1):
        if i % 20 == 0 or i == len(tutorial_dirs):
            logger.info("  Processing %d/%d: %s", i, len(tutorial_dirs), folder.name[:60])

        chunks = process_tutorial(folder, toeexpand_bin, chunk_duration_ms)
        if chunks:
            all_chunks.extend(chunks)
            processed += 1
            if any(c.get("source") == "toeexpand" for c in chunks):
                toe_count += 1
        else:
            skipped += 1

    logger.info(
        "  -> %d tutorials processed, %d skipped (teasers), %d with TOE data", processed, skipped, toe_count
    )
    logger.info("  -> %d total chunks", len(all_chunks))

    # Stage 2b: Process _patreon_exclusive TOE files if present
    patreon_dir = args.source / "_patreon_exclusive"
    if patreon_dir.is_dir() and toeexpand_bin:
        logger.info("Stage 2b: Processing Patreon-exclusive TOE files")
        patreon_toes = list(patreon_dir.glob("*.toe")) + list(patreon_dir.glob("*.tox"))
        for toe_file in patreon_toes:
            dir_path = expand_toe(toe_file, toeexpand_bin)
            if not dir_path:
                continue
            data = extract_toe_data(dir_path)
            cleanup_expansion(toe_file)

            if not data["operators"]:
                continue

            page_id = f"patreon__{_slugify(toe_file.stem)}"
            overview = f"Project: {toe_file.stem}\n"
            if data.get("operator_summary"):
                overview += f"Operators: {data['operator_summary']}\n"

            conns = [f"{c['from']} -> {c['to']}" for c in data.get("connections", [])]
            if conns:
                overview += f"Connections: {', '.join(conns[:30])}\n"

            params = [f"{p['path']}.{p['param']} = {p['expr']}" for p in data.get("parameters", [])]
            if params:
                overview += f"Expressions: {'; '.join(params[:20])}\n"

            all_chunks.append(
                {
                    "chunk_id": f"{page_id}__overview",
                    "page_id": page_id,
                    "doc_type": "tutorial_project",
                    "section_title": f"{toe_file.stem} -- Patreon Project",
                    "operator_family": None,
                    "operator_name": None,
                    "mentioned_operators": [],
                    "parameter_names": [],
                    "python_symbols": [],
                    "build_number": data.get("build_info", {}).get("build"),
                    "build_date": None,
                    "change_category": "technique",
                    "token_estimate": _token_estimate(overview),
                    "content": overview,
                    "source": "toeexpand",
                    "url": "",
                }
            )

            # Add code snippets
            for snippet in data.get("code_snippets", []):
                if len(snippet["code"].split()) < 10:
                    continue
                slug = re.sub(r"[^a-z0-9]+", "_", snippet["path"].lower()).strip("_")
                all_chunks.append(
                    {
                        "chunk_id": f"{page_id}__{snippet['language']}_{slug}",
                        "page_id": page_id,
                        "doc_type": "tutorial_code",
                        "section_title": f"{toe_file.stem} -- {snippet['language'].upper()}",
                        "operator_family": None,
                        "operator_name": None,
                        "mentioned_operators": [],
                        "parameter_names": [],
                        "python_symbols": [],
                        "build_number": None,
                        "build_date": None,
                        "change_category": "technique",
                        "token_estimate": _token_estimate(snippet["code"]),
                        "content": f"```{snippet['language']}\n{snippet['code']}\n```",
                        "source": "toeexpand",
                        "url": "",
                    }
                )

        logger.info("  -> %d Patreon TOE files processed", len(patreon_toes))

    # Save chunks.jsonl
    chunks_path = output / "chunks.jsonl"
    with open(chunks_path, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    logger.info("  -> %d total chunks saved to %s", len(all_chunks), chunks_path)

    # Stage 3: Build FTS5 index
    logger.info("Stage 3: Building FTS5 index")
    db_path = output / f"{brain_id}brain.db"
    indexed = build_fts_index(all_chunks, db_path, brain_id)
    logger.info("  -> %d chunks indexed", indexed)

    # Stage 4: Build manifest
    topic_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for chunk in all_chunks:
        cat = chunk.get("change_category", "other")
        topic_counts[cat] = topic_counts.get(cat, 0) + 1
        src = chunk.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    manifest = {
        "brain_id": brain_id,
        "display_name": config.get("display_name", brain_id),
        "description": config.get("description", ""),
        "chunks": indexed,
        "tutorials_processed": processed,
        "tutorials_skipped": skipped,
        "tutorials_with_toe": toe_count,
        "toeexpand_used": bool(toeexpand_bin),
        "chunk_duration_s": args.chunk_duration,
        "topic_distribution": dict(sorted(topic_counts.items(), key=lambda x: -x[1])),
        "source_distribution": source_counts,
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
    logger.info(
        "Done in %.1fs. DB: %.1fMB (%d chunks from %d tutorials). Output: %s",
        elapsed,
        db_size,
        indexed,
        processed,
        output,
    )


if __name__ == "__main__":
    main()
