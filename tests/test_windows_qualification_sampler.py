import importlib.util
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_sampler_checks_pop_migration_without_optional_docsbrain(monkeypatch):
    spec = importlib.util.spec_from_file_location("sampler", "scripts/sample_operator_availability.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "audit_brain_atlas",
        lambda root: {
            "card_count": 0,
            "docsbrain_operator_coverage": {
                "structured_operator_card_count": 0,
                "deprecated_missing_operator_cards": [],
                "priority_missing_operator_cards": [],
            },
        },
    )
    monkeypatch.setattr(module, "_load_latest_release_card", lambda: {})
    monkeypatch.setattr(module, "TDClient", lambda **kwargs: object())

    async def sample(client, targets, **kwargs):
        by_type = {target["op_type"]: target for target in targets}
        assert by_type["glslcreatePOP"]["role"] == "deprecated_gap"
        assert by_type["glsladvancedPOP"]["replacement_for"] == "glslcreatePOP"
        assert by_type["topologyPOP"]["replacement_for"] == "glslcreatePOP"
        return {"ok": True}

    monkeypatch.setattr(module, "sample_operator_availability", sample)
    from types import SimpleNamespace

    result = await module.main_async(
        SimpleNamespace(
            host="127.0.0.1", port=9981, timeout=15, parent_path="/project1", scratch_name="owned"
        )
    )
    assert result["ok"] is True
