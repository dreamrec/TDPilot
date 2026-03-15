#!/usr/bin/env python3
"""Download TDPilot brain databases from Google Drive.

The brains are hosted in a shared Google Drive folder. This script downloads
them to the local data/normalized/ directories where TDPilot expects them.

Usage:
    python scripts/download_brains.py              # download all brains
    python scripts/download_brains.py --brain derivative  # just derivative
    python scripts/download_brains.py --brain popx        # just POPx
    python scripts/download_brains.py --list              # show available brains
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Google Drive shared folder:
# https://drive.google.com/drive/folders/1lc1S6NBQgpAzA2G2KsHkR0gV7_SdzseO
DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1lc1S6NBQgpAzA2G2KsHkR0gV7_SdzseO"

# Brain manifest — maps brain name → files to download
BRAINS = {
    "derivative": {
        "description": "Official TouchDesigner docs (docs.derivative.ca) — 25,887 chunks, 674 operators",
        "output_dir": "data/normalized/derivative",
        "files": [
            {
                "name": "docsbrain.db",
                "drive_id": "1yDJ8LYpv_lBmIzFMfN7DrBgb7RB39u1b",
                "size_mb": 164,
            },
            {
                "name": "build_manifest.json",
                "drive_id": "12sR9Et2s6qrDEDYZB-mBYHZi8u_Sy35J",
                "size_mb": 0.001,
            },
            {
                "name": "operator_changelog.json",
                "drive_id": "18eLY03sFo0jlyrJOe3btSI5X5mHnp0f_",
                "size_mb": 0.3,
            },
        ],
    },
    "popx": {
        "description": "POPx operator reference (popsextension.com) — 480 chunks, 59 operators",
        "output_dir": "data/normalized/popx",
        "files": [
            {
                "name": "popxbrain.db",
                "drive_id": "1a2KXRiR03FHlwQhYVws_nK5sQtovpTu0",
                "size_mb": 1.3,
            },
            {
                "name": "build_manifest.json",
                "drive_id": "16L2YkwyO0h8Zr1OnRR0iHHxAzQJ629u1",
                "size_mb": 0.001,
            },
            {
                "name": "operator_changelog.json",
                "drive_id": "16dyAWyA9tR_0zlnGbbDhBZuvF_DxjLZJ",
                "size_mb": 0.001,
            },
        ],
    },
}


def _gdrive_download_url(file_id: str) -> str:
    """Construct a direct download URL for a Google Drive file."""
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _gdrive_confirm_url(file_id: str, confirm_token: str) -> str:
    """Construct confirmed download URL for large files (>100MB)."""
    return f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm_token}"


def _download_file(file_id: str, dest: Path, size_mb: float) -> bool:
    """Download a file from Google Drive with progress reporting.

    Handles the large-file confirmation page that Google Drive shows
    for files >100MB.
    """
    url = _gdrive_download_url(file_id)
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "TDPilot-BrainDownloader/1.0")

        with urllib.request.urlopen(req, timeout=30) as response:
            # Check if we got the virus scan warning page (large files)
            content_type = response.headers.get("Content-Type", "")

            if "text/html" in content_type:
                # Large file — need to extract confirm token
                html = response.read().decode("utf-8", errors="replace")
                # Look for confirm token in the HTML
                import re
                match = re.search(r'confirm=([0-9A-Za-z_-]+)', html)
                if match:
                    confirm = match.group(1)
                    url = _gdrive_confirm_url(file_id, confirm)
                else:
                    # Try the uuid approach
                    match = re.search(r'name="uuid" value="([^"]+)"', html)
                    if match:
                        uuid_val = match.group(1)
                        url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t&uuid={uuid_val}"
                    else:
                        # Just try with confirm=t
                        url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"

                req2 = urllib.request.Request(url)
                req2.add_header("User-Agent", "TDPilot-BrainDownloader/1.0")
                response = urllib.request.urlopen(req2, timeout=300)

            # Stream download with progress
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024  # 1MB chunks

            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded / total * 100
                        mb = downloaded / 1024 / 1024
                        sys.stdout.write(
                            f"\r  downloading {dest.name}: {mb:.1f}MB / {total/1024/1024:.1f}MB ({pct:.0f}%)"
                        )
                    else:
                        mb = downloaded / 1024 / 1024
                        sys.stdout.write(f"\r  downloading {dest.name}: {mb:.1f}MB")
                    sys.stdout.flush()

            print()  # newline after progress
            return True

    except urllib.error.URLError as exc:
        logger.error("Download failed for %s: %s", dest.name, exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error downloading %s: %s", dest.name, exc)
        return False


def download_brain(brain_name: str, project_root: Path) -> bool:
    """Download all files for a brain."""
    if brain_name not in BRAINS:
        logger.error("Unknown brain: %s (available: %s)", brain_name, ", ".join(BRAINS))
        return False

    brain = BRAINS[brain_name]
    output_dir = project_root / brain["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    total_mb = sum(f["size_mb"] for f in brain["files"])
    logger.info("Downloading %s brain (~%.0fMB) → %s", brain_name, total_mb, output_dir)

    all_ok = True
    for file_info in brain["files"]:
        dest = output_dir / file_info["name"]

        # Skip if already exists and has reasonable size
        if dest.exists():
            existing_mb = dest.stat().st_size / 1024 / 1024
            expected_mb = file_info["size_mb"]
            if existing_mb >= expected_mb * 0.9:
                logger.info("  %s already exists (%.1fMB), skipping", dest.name, existing_mb)
                continue

        ok = _download_file(file_info["drive_id"], dest, file_info["size_mb"])
        if not ok:
            all_ok = False

    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download TDPilot brain databases from Google Drive"
    )
    parser.add_argument(
        "--brain", choices=list(BRAINS.keys()),
        help="Download a specific brain (default: all)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available brains and exit",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if files exist",
    )
    args = parser.parse_args()

    if args.list:
        print("Available brains:")
        print(f"  Shared folder: {DRIVE_FOLDER_URL}\n")
        for name, brain in BRAINS.items():
            total_mb = sum(f["size_mb"] for f in brain["files"])
            print(f"  {name}: {brain['description']} (~{total_mb:.0f}MB)")
            for f in brain["files"]:
                print(f"    - {f['name']} ({f['size_mb']}MB)")
        return

    project_root = Path(__file__).resolve().parent.parent

    if args.force:
        # Remove existing files
        for name in (BRAINS if args.brain is None else {args.brain: BRAINS[args.brain]}):
            brain = BRAINS[name]
            output_dir = project_root / brain["output_dir"]
            for f in brain["files"]:
                path = output_dir / f["name"]
                if path.exists():
                    path.unlink()
                    logger.info("Removed existing %s", path)

    t0 = time.time()

    brains_to_download = [args.brain] if args.brain else list(BRAINS.keys())
    all_ok = True

    for brain_name in brains_to_download:
        ok = download_brain(brain_name, project_root)
        if not ok:
            all_ok = False

    elapsed = time.time() - t0

    if all_ok:
        logger.info("All brains downloaded in %.1fs", elapsed)
    else:
        logger.error("Some downloads failed. Re-run or check your connection.")
        sys.exit(1)


if __name__ == "__main__":
    main()
