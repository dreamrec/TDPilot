from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_release_notes_freshness.py"
_SPEC = importlib.util.spec_from_file_location("check_release_notes_freshness", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
freshness = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(freshness)


# ── pure-function tests ──────────────────────────────────────────────


def test_parse_build_key_orders_chronologically():
    keys = [freshness.parse_build_key(b) for b in ["2025.32460", "2025.32820", "2026.10000"]]
    assert keys == sorted(keys)
    assert freshness.parse_build_key("2025.32820") > freshness.parse_build_key("2025.32460")


def test_parse_build_key_handles_garbage():
    assert freshness.parse_build_key("not-a-build") == (0, 0)
    assert freshness.parse_build_key("") == (0, 0)


def test_extract_derivative_builds_dedupes_preserving_order():
    html = """
    <table>
      <tr><td>2025.32820</td><td>May 06, 2026</td></tr>
      <tr><td>2025.32460</td><td>Mar 10, 2026</td></tr>
      <tr><td>2025.32280</td><td>Jan 20, 2026</td></tr>
    </table>
    <h2>Build_2025.32820_May_06_2026</h2>
    <p>See also build 2025.32460.</p>
    """
    builds = freshness.extract_derivative_builds(html)
    assert builds == ["2025.32820", "2025.32460", "2025.32280"]


def test_extract_derivative_builds_empty_when_no_match():
    assert freshness.extract_derivative_builds("<p>nothing here</p>") == []


def test_seed_card_latest_build_picks_newest(tmp_path: Path):
    for build in ("2025.32460", "2025.32820", "2025.32280"):
        (tmp_path / f"{build}.json").write_text(json.dumps({"build": build}))
    assert freshness.seed_card_latest_build(tmp_path) == "2025.32820"


def test_seed_card_latest_build_returns_none_for_empty_dir(tmp_path: Path):
    assert freshness.seed_card_latest_build(tmp_path) is None


def test_seed_card_latest_build_returns_none_for_missing_dir(tmp_path: Path):
    assert freshness.seed_card_latest_build(tmp_path / "nope") is None


# ── main() integration tests ─────────────────────────────────────────


def _write_cards(tmp_path: Path, *builds: str) -> Path:
    cards = tmp_path / "release"
    cards.mkdir()
    for b in builds:
        (cards / f"{b}.json").write_text(json.dumps({"build": b}))
    return cards


def _fixture_html(tmp_path: Path, *builds: str) -> Path:
    fixture = tmp_path / "release_notes.html"
    rows = "\n".join(f"<tr><td>{b}</td></tr>" for b in builds)
    fixture.write_text(f"<table>{rows}</table>", encoding="utf-8")
    return fixture


def test_main_passes_when_seed_matches_derivative(tmp_path: Path, capsys):
    cards = _write_cards(tmp_path, "2025.32820", "2025.32460")
    fixture = _fixture_html(tmp_path, "2025.32820", "2025.32460", "2025.32280")
    code = freshness.main(["--cards-dir", str(cards), "--offline-fixture", str(fixture)])
    assert code == 0
    out = capsys.readouterr().out
    assert "matches or exceeds" in out


def test_main_fails_when_seed_one_behind_with_default_exact_match_policy(tmp_path: Path, capsys):
    cards = _write_cards(tmp_path, "2025.32460")
    fixture = _fixture_html(tmp_path, "2025.32820", "2025.32460", "2025.32280")
    code = freshness.main(["--cards-dir", str(cards), "--offline-fixture", str(fixture)])
    assert code == 1
    err = capsys.readouterr().err
    assert "1 builds behind" in err
    assert "--max-drift=0" in err


def test_main_fails_when_seed_two_behind(tmp_path: Path, capsys):
    cards = _write_cards(tmp_path, "2025.32280")
    fixture = _fixture_html(tmp_path, "2025.32820", "2025.32460", "2025.32280")
    code = freshness.main(["--cards-dir", str(cards), "--offline-fixture", str(fixture)])
    assert code == 1
    err = capsys.readouterr().err
    assert "2 builds behind" in err
    assert "2025.32820.json" in err


def test_main_respects_custom_max_drift(tmp_path: Path):
    cards = _write_cards(tmp_path, "2025.32280")
    fixture = _fixture_html(tmp_path, "2025.32820", "2025.32460", "2025.32280")
    code = freshness.main(["--cards-dir", str(cards), "--offline-fixture", str(fixture), "--max-drift", "2"])
    assert code == 0


def test_main_fails_when_no_cards_present(tmp_path: Path, capsys):
    cards = tmp_path / "empty"
    cards.mkdir()
    fixture = _fixture_html(tmp_path, "2025.32820")
    code = freshness.main(["--cards-dir", str(cards), "--offline-fixture", str(fixture)])
    assert code == 1
    assert "no release cards" in capsys.readouterr().err


def test_main_soft_passes_when_html_has_no_builds(tmp_path: Path, capsys):
    cards = _write_cards(tmp_path, "2025.32820")
    fixture = tmp_path / "garbled.html"
    fixture.write_text("<p>nothing relevant</p>")
    code = freshness.main(["--cards-dir", str(cards), "--offline-fixture", str(fixture)])
    assert code == 0
    out = capsys.readouterr().out
    assert "soft-passing" in out


def test_main_strict_network_fails_on_unparseable_html(tmp_path: Path, capsys):
    cards = _write_cards(tmp_path, "2025.32820")
    fixture = tmp_path / "garbled.html"
    fixture.write_text("<p>nothing relevant</p>")
    code = freshness.main(
        [
            "--cards-dir",
            str(cards),
            "--offline-fixture",
            str(fixture),
            "--strict-network",
        ]
    )
    assert code == 1
    assert "no build numbers parsed" in capsys.readouterr().err


# ── shipped-corpus invariant ─────────────────────────────────────────


def test_shipped_seed_corpus_tracks_touchdesigner_2025_33070_or_newer():
    """The cards we ship must include the current official build known when
    this invariant was updated. Future bumps naturally raise this floor.
    """
    from td_mcp.knowledge import card_index  # noqa: F401  — confirm package import works

    cards_dir = Path(__file__).resolve().parents[1] / "src" / "td_mcp" / "knowledge" / "cards" / "release"
    latest = freshness.seed_card_latest_build(cards_dir)
    assert latest is not None, "shipped corpus has no release cards"
    assert freshness.parse_build_key(latest) >= freshness.parse_build_key("2025.33070"), (
        f"shipped newest release card is {latest}, expected >= 2025.33070"
    )


def test_touchdesigner_2025_33070_release_card_covers_new_runtime_surface():
    cards_dir = Path(__file__).resolve().parents[1] / "src" / "td_mcp" / "knowledge" / "cards"
    card = json.loads((cards_dir / "release" / "2025.33070.json").read_text(encoding="utf-8"))

    assert card["release_date"] == "2026-07-16"
    assert {(item["type"], item["family"]) for item in card["new_ops"]} == {
        ("gltfinCOMP", "COMP"),
        ("gltfoutCOMP", "COMP"),
        ("scriptPOP", "POP"),
    }
    changed = {item["type"]: item["change"] for item in card["changed_ops"]}
    assert "full POP reconstruction" in changed["dattoPOP"]
    assert "Local Address" in changed["webserverDAT"]
    assert any("OP_CommonAPIVersion" in warning for warning in card["migration_warnings"])
