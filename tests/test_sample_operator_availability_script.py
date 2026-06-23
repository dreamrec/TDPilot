from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from td_mcp.brain.operator_availability import build_operator_availability_matrix

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sample_operator_availability.py"
_SPEC = importlib.util.spec_from_file_location("sample_operator_availability", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
sample_operator_availability = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sample_operator_availability)


def test_sample_operator_availability_cli_stores_report_by_build_platform_and_addons(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    matrix = build_operator_availability_matrix(
        {"audiodeviceinCHOP"},
        required_ops=["audiofileinCHOP", "audiodeviceinCHOP"],
        td_build="2025.32820",
        platform="macOS",
        installed_addons=["POPX"],
    )

    async def fake_main_async(_args):
        return {
            "schema_version": 1,
            "ok": True,
            "availability_matrix": matrix.model_dump(),
            "results": [],
        }

    monkeypatch.setattr(sample_operator_availability, "main_async", fake_main_async)
    monkeypatch.setattr(
        sys,
        "argv",
        ["sample_operator_availability.py", "--store-root", str(tmp_path)],
    )

    assert sample_operator_availability.main() == 0

    output = json.loads(capsys.readouterr().out)
    expected_path = tmp_path / "2025.32820" / "macos" / "popx" / "operator_availability.json"
    assert output["stored_availability_report"] == str(expected_path)
    assert (
        json.loads(expected_path.read_text(encoding="utf-8"))["availability_matrix"]["td_build"]
        == "2025.32820"
    )
