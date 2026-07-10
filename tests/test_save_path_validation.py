"""Tests for the capture save_path validator + save_path plumbing on
td_screenshot / td_capture_frame.

The validator is the server-side security gate in front of the TD-side disk
write (docs/SECURITY.md; TD-side path writes were this repo's RCE surface
twice), so the adversarial cases here are the contract:

- absolute-path requirement (bare filenames go to ~/.tdpilot/captures/)
- extension whitelist .png/.jpg/.jpeg
- '..' traversal rejection on the RAW input
- symlink resolution BEFORE the home-containment check
- home-directory containment
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as _registry
from td_mcp.registry import tools_data, tools_vision
from td_mcp.vision.save_path import (
    ALLOWED_SAVE_EXTENSIONS,
    SavePathError,
    validate_save_path,
)


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``~`` / ``Path.home()`` at an isolated tmp directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # windows expanduser
    return home


# ---------------------------------------------------------------------------
# Validator — accepted inputs
# ---------------------------------------------------------------------------


class TestValidateSavePathAccepts:
    def test_bare_filename_resolves_into_default_capture_dir(self, fake_home: Path):
        resolved = validate_save_path("shot.png")
        assert resolved == str((fake_home / ".tdpilot" / "captures" / "shot.png").resolve())

    def test_absolute_path_under_home(self, fake_home: Path):
        target = fake_home / "renders" / "frame.jpg"
        resolved = validate_save_path(str(target))
        assert resolved == str(target.resolve())

    def test_tilde_path_under_home(self, fake_home: Path):
        resolved = validate_save_path("~/captures/frame.jpeg")
        assert resolved == str((fake_home / "captures" / "frame.jpeg").resolve())

    def test_uppercase_extension_accepted(self, fake_home: Path):
        resolved = validate_save_path(str(fake_home / "SHOT.PNG"))
        assert resolved.endswith("SHOT.PNG")

    def test_all_whitelisted_extensions(self, fake_home: Path):
        for ext in sorted(ALLOWED_SAVE_EXTENSIONS):
            assert validate_save_path(f"ok{ext}")


# ---------------------------------------------------------------------------
# Validator — adversarial inputs
# ---------------------------------------------------------------------------


class TestValidateSavePathRejects:
    @pytest.mark.parametrize("raw", ["", "   ", None, 42])
    def test_empty_or_non_string(self, fake_home: Path, raw):
        with pytest.raises(SavePathError):
            validate_save_path(raw)  # type: ignore[arg-type]

    def test_relative_path_with_separators(self, fake_home: Path):
        with pytest.raises(SavePathError, match="absolute"):
            validate_save_path("captures/shot.png")

    @pytest.mark.parametrize(
        "raw",
        [
            "../escape.png",
            "/anywhere/../etc/shot.png",
            "~/captures/../../evil.png",
            "..\\windows\\escape.png",
            "sub/../shot.png",
        ],
    )
    def test_traversal_segments_rejected(self, fake_home: Path, raw: str):
        with pytest.raises(SavePathError, match="'\\.\\.'"):
            validate_save_path(raw)

    @pytest.mark.parametrize(
        "raw",
        [
            "shot.exe",
            "shot.py",
            "shot.toe",
            "shot",
            "shot.png.exe",
            "~/x/shot.gif",
            "~/x/shot.tox",
        ],
    )
    def test_extension_whitelist(self, fake_home: Path, raw: str):
        with pytest.raises(SavePathError, match="extension"):
            validate_save_path(raw)

    def test_outside_home_rejected(self, fake_home: Path):
        # Absolute paths outside home must be rejected. Build them from the
        # home drive/anchor so they are genuinely absolute on THIS platform —
        # a Unix-style "/etc/x.png" is not absolute on Windows (no drive
        # letter), where it would trip the earlier "must be absolute" guard
        # instead of the home-containment check.
        anchor = Path(fake_home).anchor  # "/" on POSIX, "C:\\" on Windows
        for raw in (
            f"{anchor}var_not_home/outside.png",
            f"{anchor}etc_not_home/shadow.jpg",
        ):
            with pytest.raises(SavePathError, match="home"):
                validate_save_path(raw)

    def test_nul_byte_rejected(self, fake_home: Path):
        with pytest.raises(SavePathError, match="NUL"):
            validate_save_path("shot\x00.png")

    def test_symlinked_directory_escape_rejected(self, fake_home: Path, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        link = fake_home / "innocent"
        link.symlink_to(outside, target_is_directory=True)
        with pytest.raises(SavePathError, match="home"):
            validate_save_path(str(link / "shot.png"))

    def test_symlinked_file_extension_swap_rejected(self, fake_home: Path):
        real = fake_home / "actually.sh"
        real.write_text("#!/bin/sh\n", encoding="utf-8")
        link = fake_home / "shot.png"
        link.symlink_to(real)
        with pytest.raises(SavePathError, match="extension"):
            validate_save_path(str(link))

    def test_existing_directory_rejected(self, fake_home: Path):
        target = fake_home / "dir.png"
        target.mkdir()
        with pytest.raises(SavePathError, match="directory"):
            validate_save_path(str(target))


# ---------------------------------------------------------------------------
# Tool plumbing — td_capture_frame / td_screenshot
# ---------------------------------------------------------------------------


class _RecordingClient:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def request(self, endpoint, body):
        self.calls.append((endpoint, body))
        assert endpoint == "screenshot"
        payload = {
            "success": True,
            "path": body["path"],
            "width": 320,
            "height": 180,
            "format": "png",
            "size_bytes": 1234,
            "data_omitted": True,
        }
        if body.get("save_path"):
            payload["saved_to"] = body["save_path"]
        return payload


def _ctx():
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context={}))


@pytest.mark.asyncio
async def test_capture_frame_save_path_returns_metadata_and_saved_to(monkeypatch, fake_home):
    client = _RecordingClient()
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)

    out = await tools_vision.td_capture_frame(_ctx(), path="/project1/out1", save_path="verify.png")
    payload = json.loads(out)

    assert len(client.calls) == 1
    _endpoint, body = client.calls[0]
    expected = str((fake_home / ".tdpilot" / "captures" / "verify.png").resolve())
    assert body["save_path"] == expected
    assert body["include_data"] is False
    assert payload["success"] is True
    assert payload["saved_to"] == expected
    assert payload["data_omitted"] is True
    assert "data_base64" not in payload


@pytest.mark.asyncio
async def test_capture_frame_save_path_overrides_confirm(monkeypatch, fake_home):
    client = _RecordingClient()
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)

    out = await tools_vision.td_capture_frame(
        _ctx(), path="/project1/out1", confirm=True, save_path="verify.jpg"
    )
    payload = json.loads(out)

    assert client.calls[0][1]["include_data"] is False
    assert "data_base64" not in payload
    assert payload["data_omitted"] is True


@pytest.mark.asyncio
async def test_capture_frame_invalid_save_path_never_reaches_td(monkeypatch, fake_home):
    client = _RecordingClient()
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)

    out = await tools_vision.td_capture_frame(_ctx(), path="/project1/out1", save_path="/etc/../etc/pwn.png")
    payload = json.loads(out)

    assert client.calls == []
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_screenshot_save_path_forwards_validated_path(monkeypatch, fake_home):
    client = _RecordingClient()
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)

    out = await tools_data.td_screenshot(_ctx(), path="/project1/out1", save_path="~/caps/x.jpeg")
    payload = json.loads(out)

    assert len(client.calls) == 1
    _, body = client.calls[0]
    assert body["save_path"] == str((fake_home / "caps" / "x.jpeg").resolve())
    assert body["include_data"] is False
    assert payload["saved_to"] == body["save_path"]


@pytest.mark.asyncio
async def test_screenshot_invalid_save_path_never_reaches_td(monkeypatch, fake_home):
    client = _RecordingClient()
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)

    out = await tools_data.td_screenshot(_ctx(), path="/project1/out1", save_path="/private/var/outside.png")
    payload = json.loads(out)

    assert client.calls == []
    assert payload["success"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_screenshot_without_save_path_keeps_legacy_body(monkeypatch, fake_home):
    client = _RecordingClient()
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: client)

    await tools_data.td_screenshot(_ctx(), path="/project1/out1", quality=0.25)

    assert client.calls == [("screenshot", {"path": "/project1/out1", "quality": 0.25})]


# ---------------------------------------------------------------------------
# TD-side mirror validator (defense in depth)
# ---------------------------------------------------------------------------


def _load_td_side_validator():
    """AST-extract the TD-side validator (the callbacks module can't be
    imported outside TouchDesigner) and load it as a real module — the same
    pattern as tests/test_td_component_security_behavior.py."""
    source = Path(__file__).resolve().parents[1] / "td_component" / "mcp_webserver_callbacks.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    chunks = ["import os"]
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "_SCREENSHOT_SAVE_EXTENSIONS" in targets:
                chunks.append(ast.unparse(node))
        elif isinstance(node, ast.FunctionDef) and node.name == "_validate_screenshot_save_path":
            chunks.append(ast.unparse(node))
    assert len(chunks) == 3, "TD-side save_path validator not found in callbacks source"
    fd, path = tempfile.mkstemp(suffix=".py", prefix="_td_save_path_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n\n".join(chunks))
        spec = importlib.util.spec_from_file_location("_td_save_path_extracted", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        os.unlink(path)
    return module._validate_screenshot_save_path


class TestTdSideMirrorValidator:
    def test_rejects_relative_traversal_extension_and_outside_home(self, fake_home: Path):
        validator = _load_td_side_validator()
        assert validator("relative.png") is not None
        assert validator(str(fake_home) + "/../escape.png") is not None
        assert validator(str(fake_home / "shot.exe")) is not None
        assert validator("/private/var/outside.png") is not None
        assert validator("") is not None
        assert validator(None) is not None

    def test_accepts_absolute_whitelisted_path_under_home(self, fake_home: Path):
        validator = _load_td_side_validator()
        assert validator(str(fake_home / "captures" / "ok.png")) is None
        assert validator(str(fake_home / "ok.jpeg")) is None
