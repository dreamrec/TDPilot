from __future__ import annotations

import pytest

from td_mcp.brain.param_semantics_drafts import (
    confirm_param_semantics_drafts_with_live_readback,
    draft_param_semantics_from_docs,
)
from td_mcp.models.brain import ParamSemantics


class FakeCardIndex:
    def __init__(self, cards: dict[str, dict]):
        self.cards = cards

    def get_operator(self, op_type: str):
        return self.cards.get(op_type)


def _card(op_type: str, key_params: list[dict]) -> dict:
    return {
        "card_type": "operator",
        "op_type": op_type,
        "family": "TOP",
        "display_name": op_type,
        "docs_url": f"https://docs.derivative.ca/{op_type}",
        "summary": "Official operator card.",
        "key_params": key_params,
    }


def test_drafts_param_semantics_from_official_operator_cards():
    index = FakeCardIndex(
        {
            "exampleTOP": _card(
                "exampleTOP",
                [
                    {"name": "active", "label": "Active", "type": "Toggle", "note": "Enable output."},
                    {"name": "target", "label": "Target TOP", "type": "TOP Path", "note": "Source TOP."},
                    {"name": "size", "label": "Size", "type": "Float2", "note": "Width and height."},
                    {"name": "mode", "label": "Mode", "type": "Menu", "note": "Blend mode menu."},
                ],
            )
        }
    )

    report = draft_param_semantics_from_docs(index, ["exampleTOP"], existing_registry=[])

    assert report.operator_count == 1
    assert report.missing_docs == []
    assert [draft.name for draft in report.drafts] == ["active", "target", "size", "mode"]
    by_name = {draft.name: draft for draft in report.drafts}
    assert by_name["active"].value_kind == "bool"
    assert by_name["target"].value_kind == "op_ref"
    assert by_name["target"].expected_family == "TOP"
    assert by_name["size"].value_kind == "tuple"
    assert by_name["size"].tuple_size == 2
    assert by_name["mode"].value_kind == "enum"
    assert all(draft.needs_live_readback is True for draft in report.drafts)
    assert all(draft.official_source.startswith("https://docs.derivative.ca/") for draft in report.drafts)


def test_drafts_skip_existing_verified_semantics():
    existing = ParamSemantics(
        op_type="exampleTOP",
        name="target",
        label="Target TOP",
        value_kind="op_ref",
        expected_family="TOP",
        default_strategy="use_created_internal_operator_reference",
        cook_risk="high",
        validation_rule="non_empty_operator_reference",
        official_source="https://docs.derivative.ca/exampleTOP",
    )
    index = FakeCardIndex(
        {
            "exampleTOP": _card(
                "exampleTOP",
                [
                    {"name": "target", "label": "Target TOP", "type": "TOP Path", "note": "Source TOP."},
                    {"name": "gain", "label": "Gain", "type": "Float", "note": "Output gain."},
                ],
            )
        }
    )

    report = draft_param_semantics_from_docs(index, ["exampleTOP"], existing_registry=[existing])

    assert [draft.name for draft in report.drafts] == ["gain"]
    assert report.skipped_existing == ["exampleTOP.target"]


def test_drafts_report_missing_or_unofficial_docs_without_guessing():
    index = FakeCardIndex(
        {
            "blogTOP": {
                "op_type": "blogTOP",
                "docs_url": "https://example.com/blogTOP",
                "key_params": [{"name": "gain", "type": "Float"}],
            }
        }
    )

    report = draft_param_semantics_from_docs(index, ["missingTOP", "blogTOP"], existing_registry=[])

    assert report.drafts == []
    assert report.missing_docs == ["missingTOP", "blogTOP"]


class FakeTDClient:
    def __init__(self, scripted: dict):
        self.scripted = scripted
        self.calls: list[tuple[str, dict | None]] = []
        self.closed = False

    async def request(self, endpoint: str, params: dict | None = None):
        self.calls.append((endpoint, params))
        response = self.scripted.get(endpoint)
        if callable(response):
            return response(params or {})
        if isinstance(response, BaseException):
            raise response
        return response or {}

    async def close(self):
        self.closed = True


def _drafts_for_live_confirmation():
    index = FakeCardIndex(
        {
            "exampleTOP": _card(
                "exampleTOP",
                [
                    {"name": "active", "label": "Active", "type": "Toggle", "note": "Enable output."},
                    {"name": "target", "label": "Target TOP", "type": "TOP Path", "note": "Source TOP."},
                    {"name": "size", "label": "Size", "type": "Float2", "note": "Width and height."},
                ],
            )
        }
    )
    return draft_param_semantics_from_docs(index, ["exampleTOP"]).drafts


@pytest.mark.asyncio
async def test_confirm_drafted_param_semantics_from_live_readback():
    drafts = _drafts_for_live_confirmation()

    def create(params):
        return {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"}

    client = FakeTDClient(
        {
            "node/create": create,
            "node/params": {
                "parameters": {
                    "active": {"name": "active", "label": "Active", "type": "Toggle", "value": True},
                    "target": {
                        "name": "target",
                        "label": "Target TOP",
                        "type": "TOP Path",
                        "value": "/project1/source",
                    },
                    "size": {
                        "name": "size",
                        "label": "Size",
                        "type": "Float2",
                        "value": [1920, 1080],
                    },
                }
            },
            "node/delete": {"ok": True},
        }
    )

    report = await confirm_param_semantics_drafts_with_live_readback(
        client,
        drafts,
        parent_path="/project1",
        scratch_name="tdpilot_param_probe",
    )

    assert report.ok is True
    assert report.operator_count == 1
    assert report.draft_count == 3
    assert report.confirmed_count == 3
    assert report.blocked_count == 0
    assert report.cleanup_ok is True
    assert client.closed is True
    assert [item.name for item in report.confirmed_semantics] == ["active", "target", "size"]
    by_name = {item.name: item for item in report.confirmed_semantics}
    assert by_name["active"].value_kind == "bool"
    assert by_name["target"].value_kind == "op_ref"
    assert by_name["target"].expected_family == "TOP"
    assert by_name["size"].value_kind == "tuple"
    assert by_name["size"].tuple_size == 2
    assert all(item.default_strategy.startswith("live_confirmed_") for item in report.confirmed_semantics)
    assert ("node/params", {"path": "/project1/tdpilot_param_probe/probe_00_exampleTOP"}) in client.calls
    assert ("node/delete", {"path": "/project1/tdpilot_param_probe"}) in client.calls


@pytest.mark.asyncio
async def test_live_readback_blocks_missing_draft_parameter():
    drafts = [draft for draft in _drafts_for_live_confirmation() if draft.name == "target"]

    client = FakeTDClient(
        {
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params": {"parameters": {}},
            "node/delete": {"ok": True},
        }
    )

    report = await confirm_param_semantics_drafts_with_live_readback(client, drafts)

    assert report.ok is False
    assert report.confirmed_semantics == []
    assert report.blocked_count == 1
    assert report.blocked[0]["param"] == "exampleTOP.target"
    assert report.blocked[0]["reason"] == "missing_live_parameter"


@pytest.mark.asyncio
async def test_live_readback_blocks_contradictory_tuple_shape():
    drafts = [draft for draft in _drafts_for_live_confirmation() if draft.name == "size"]

    client = FakeTDClient(
        {
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params": {
                "parameters": {
                    "size": {
                        "name": "size",
                        "label": "Size",
                        "type": "Float3",
                        "value": [1, 2, 3],
                    }
                }
            },
            "node/delete": {"ok": True},
        }
    )

    report = await confirm_param_semantics_drafts_with_live_readback(client, drafts)

    assert report.ok is False
    assert report.confirmed_semantics == []
    assert report.blocked == [
        {
            "op_type": "exampleTOP",
            "param": "exampleTOP.size",
            "reason": "tuple_shape_mismatch",
            "live_type": "Float3",
            "live_value": [1, 2, 3],
        }
    ]
