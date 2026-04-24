"""Tests for seed corpus integrity — validates all JSON knowledge cards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CARDS_DIR = Path(__file__).resolve().parent.parent / "src" / "td_mcp" / "knowledge" / "cards"

# Required fields per card_type
REQUIRED_FIELDS = {
    "operator": ["card_type", "op_type", "family", "summary"],
    "palette": ["card_type", "component_name", "summary"],
    "release": ["card_type", "build"],
    "snippet": ["card_type", "snippet_id", "family", "summary"],
}


def _load_all_json(subdir: str) -> list[tuple[Path, dict]]:
    """Load all JSON files from a cards subdirectory."""
    directory = CARDS_DIR / subdir
    results = []
    for p in sorted(directory.glob("*.json")):
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        results.append((p, data))
    return results


class TestAllJsonValid:
    """Every .json file in cards/ must parse without error."""

    @pytest.fixture(scope="class")
    def all_json_files(self) -> list[Path]:
        return list(CARDS_DIR.rglob("*.json"))

    def test_at_least_one_json(self, all_json_files: list[Path]) -> None:
        assert len(all_json_files) > 0, "No JSON files found in cards directory"

    def test_all_parse(self, all_json_files: list[Path]) -> None:
        for p in all_json_files:
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                pytest.fail(f"{p.name} is not valid JSON: {exc}")


class TestOperatorCards:
    """Operator cards must have required fields and meet minimums."""

    @pytest.fixture(scope="class")
    def operators(self) -> list[tuple[Path, dict]]:
        return _load_all_json("operators")

    def test_at_least_10_operator_cards(self, operators: list[tuple[Path, dict]]) -> None:
        assert len(operators) >= 10, f"Expected >=10 operator cards, found {len(operators)}"

    def test_required_fields(self, operators: list[tuple[Path, dict]]) -> None:
        for path, card in operators:
            for field in REQUIRED_FIELDS["operator"]:
                assert field in card, f"{path.name} missing required field '{field}'"

    def test_card_type_is_operator(self, operators: list[tuple[Path, dict]]) -> None:
        for path, card in operators:
            assert card["card_type"] == "operator", f"{path.name} card_type != 'operator'"

    def test_family_valid(self, operators: list[tuple[Path, dict]]) -> None:
        valid_families = {"TOP", "CHOP", "SOP", "COMP", "DAT", "MAT", "POP"}
        for path, card in operators:
            assert card["family"] in valid_families, f"{path.name} has invalid family '{card['family']}'"


class TestPaletteCards:
    """Palette cards must have required fields."""

    @pytest.fixture(scope="class")
    def palettes(self) -> list[tuple[Path, dict]]:
        return _load_all_json("palette")

    def test_required_fields(self, palettes: list[tuple[Path, dict]]) -> None:
        for path, card in palettes:
            for field in REQUIRED_FIELDS["palette"]:
                assert field in card, f"{path.name} missing required field '{field}'"


class TestReleaseCards:
    """Release cards must exist and have required fields."""

    def test_release_2025_32460_exists(self) -> None:
        path = CARDS_DIR / "release" / "2025.32460.json"
        assert path.exists(), "Release card 2025.32460.json not found"

    def test_required_fields(self) -> None:
        path = CARDS_DIR / "release" / "2025.32460.json"
        card = json.loads(path.read_text(encoding="utf-8"))
        for field in REQUIRED_FIELDS["release"]:
            assert field in card, f"Release card missing required field '{field}'"


class TestSnippetCards:
    """Snippet cards must have required fields."""

    @pytest.fixture(scope="class")
    def snippets(self) -> list[tuple[Path, dict]]:
        return _load_all_json("snippets")

    def test_required_fields(self, snippets: list[tuple[Path, dict]]) -> None:
        for path, card in snippets:
            for field in REQUIRED_FIELDS["snippet"]:
                assert field in card, f"{path.name} missing required field '{field}'"
