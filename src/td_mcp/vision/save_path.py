"""Server-side validation for TD-side capture save paths.

``td_screenshot`` and ``td_capture_frame`` accept an optional ``save_path``
that makes the TouchDesigner component write the captured image to disk and
return metadata instead of in-band base64. TD-side file writes have been this
repo's RCE surface before (see docs/SECURITY.md and
docs/TD_INTRICACIES_AND_PATTERNS.md §28), so the MCP server validates every
save path BEFORE it is sent to TouchDesigner:

- a bare filename (no path separators) resolves into the allowlisted capture
  directory ``~/.tdpilot/captures/``
- anything else must be an absolute path (``~`` is expanded first)
- ``..`` traversal segments are rejected on the RAW input, before resolution
- NUL bytes are rejected
- extension whitelist: ``.png`` / ``.jpg`` / ``.jpeg`` (case-insensitive)
- symlinks are resolved BEFORE the containment check
- the resolved path must stay under the user's home directory (which contains
  the ``~/.tdpilot/captures/`` default)

The TD component mirrors these checks (defense in depth), but the server-side
validator is the primary gate: nothing that fails here ever reaches TD.
"""

from __future__ import annotations

from pathlib import Path

ALLOWED_SAVE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})
DEFAULT_CAPTURE_DIR = "~/.tdpilot/captures"


class SavePathError(ValueError):
    """Raised when a capture save_path fails validation."""


def validate_save_path(raw: str) -> str:
    """Validate a capture save path and return the resolved absolute path.

    Raises :class:`SavePathError` on any violation. Returns the
    symlink-resolved absolute path string to send to TouchDesigner.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise SavePathError("save_path must be a non-empty string")
    candidate = raw.strip()
    if "\x00" in candidate:
        raise SavePathError("save_path must not contain NUL bytes")

    # Reject traversal on the raw input, before any resolution can mask it.
    segments = candidate.replace("\\", "/").split("/")
    if ".." in segments:
        raise SavePathError("save_path must not contain '..' segments")

    if "/" not in candidate and "\\" not in candidate:
        # Bare filename — resolve into the allowlisted capture directory.
        base = Path(DEFAULT_CAPTURE_DIR).expanduser()
        candidate_path = base / candidate
    else:
        candidate_path = Path(candidate).expanduser()
        if not candidate_path.is_absolute():
            raise SavePathError(
                "save_path must be an absolute path, or a bare filename "
                f"(which saves under {DEFAULT_CAPTURE_DIR}/)"
            )

    if candidate_path.suffix.lower() not in ALLOWED_SAVE_EXTENSIONS:
        raise SavePathError(
            "save_path extension must be one of: " + ", ".join(sorted(ALLOWED_SAVE_EXTENSIONS))
        )

    # Symlink-resolve BEFORE the containment check so a symlinked directory
    # cannot smuggle the write outside the allowed root.
    resolved = candidate_path.resolve()
    if resolved.suffix.lower() not in ALLOWED_SAVE_EXTENSIONS:
        raise SavePathError(
            "resolved save_path extension must be one of: " + ", ".join(sorted(ALLOWED_SAVE_EXTENSIONS))
        )

    home = Path.home().resolve()
    if resolved != home and home not in resolved.parents:
        raise SavePathError("save_path must resolve under the user's home directory")
    if resolved == home or resolved.is_dir():
        raise SavePathError("save_path must name a file, not a directory")

    return str(resolved)


__all__ = ["ALLOWED_SAVE_EXTENSIONS", "DEFAULT_CAPTURE_DIR", "SavePathError", "validate_save_path"]
