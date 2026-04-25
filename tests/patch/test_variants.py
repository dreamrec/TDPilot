"""Tests for src/td_mcp/patch/variants.py."""

from __future__ import annotations

import pytest

from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.variants import generate_variants


def _plan(ops=None):
    return PatchPlan(
        target_root="/p",
        source="operations",
        operations=ops or [],
        undo_label="base",
        validation_plan=ValidationPlan(target_root="/p"),
    )


def test_fixed_seed_reproducible():
    base = _plan([PatchOperation(kind="set_params", target="/p/n1", args={"params": {"freq": 1.0}})])
    v1, _ = generate_variants(base, n=3, strategies=["param_jitter"], seed=42)
    v2, _ = generate_variants(base, n=3, strategies=["param_jitter"], seed=42)
    assert [x.model_dump() for x in v1] == [y.model_dump() for y in v2]


def test_different_seed_differs():
    base = _plan([PatchOperation(kind="set_params", target="/p/n1", args={"params": {"freq": 1.0}})])
    v1, _ = generate_variants(base, n=2, strategies=["param_jitter"], seed=1)
    v2, _ = generate_variants(base, n=2, strategies=["param_jitter"], seed=999)
    # First variant's freq param should differ between seeds
    freq1 = v1[0].operations[0].args["params"]["freq"]
    freq2 = v2[0].operations[0].args["params"]["freq"]
    assert freq1 != freq2


def test_n_limit_respected():
    base = _plan([PatchOperation(kind="set_params", target="/p/n", args={"params": {"a": 1.0}})])
    variants, _ = generate_variants(base, n=5, strategies=["param_jitter"], seed=0)
    assert len(variants) == 5


def test_operator_substitute_skipped():
    base = _plan()
    variants, skipped = generate_variants(base, n=2, strategies=["operator_substitute"], seed=0)
    assert variants == []
    assert any("operator_substitute" in s for s in skipped)


def test_unknown_strategy_raises():
    base = _plan()
    with pytest.raises(ValueError, match="unknown strategy"):
        generate_variants(base, n=1, strategies=["bogus"], seed=0)


def test_non_numeric_params_untouched():
    base = _plan(
        [
            PatchOperation(
                kind="set_params",
                target="/p/n",
                args={"params": {"freq": 2.0, "label": "hello", "enabled": True}},
            )
        ]
    )
    variants, _ = generate_variants(base, n=1, strategies=["param_jitter"], seed=0)
    params = variants[0].operations[0].args["params"]
    assert params["label"] == "hello"  # untouched
    assert params["enabled"] is True  # untouched
    assert params["freq"] != 2.0  # jittered
    assert 1.4 <= params["freq"] <= 2.6  # within ±30%
