"""Variant-generation strategies for PatchPlans. v1.5.0 ships
param_jitter only; operator_substitute and topology_perturb are
reserved strategy names that return empty with a skipped note.

See spec §4.7 + §6.6.
"""

from __future__ import annotations

import random
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from td_mcp.models.patch import PatchPlan, PatchVariant

_JITTER_RANGE = 0.3  # ±30% for numeric params
_IMPLEMENTED = {"param_jitter"}
_RESERVED = {"operator_substitute", "topology_perturb"}


def generate_variants(
    base: PatchPlan,
    n: int,
    strategies: list[str],
    seed: int | None = None,
) -> tuple[list[PatchVariant], list[str]]:
    """Generate N variants from a base plan using the given strategies.

    Returns (variants[:n], skipped_strategies). Unknown strategies raise
    ValueError. Reserved strategies are accepted but return empty +
    skipped note.
    """
    rng = random.Random(seed if seed is not None else random.randint(0, 2**31))
    variants: list[PatchVariant] = []
    skipped: list[str] = []

    for strategy in strategies:
        if strategy == "param_jitter":
            variants.extend(_apply_jitter(base, n, rng))
        elif strategy in _RESERVED:
            skipped.append(f"{strategy} (not yet implemented)")
        else:
            raise ValueError(f"unknown strategy: {strategy!r}")

    return variants[:n], skipped


def _apply_jitter(base: PatchPlan, n: int, rng: random.Random) -> list[PatchVariant]:
    variants: list[PatchVariant] = []
    for _ in range(n):
        sub_seed = rng.randint(0, 2**31)
        sub_rng = random.Random(sub_seed)
        new_ops = []
        for op in base.operations:
            new_args = deepcopy(op.args)
            if op.kind == "set_params" and isinstance(new_args.get("params"), dict):
                jittered = {
                    k: _jitter(v, sub_rng) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
                    for k, v in new_args["params"].items()
                }
                new_args["params"] = jittered
            new_ops.append(op.model_copy(update={"args": new_args}))

        # Derive a deterministic id and created_at from sub_seed so that
        # same-seed calls produce bit-identical model_dump() output.
        deterministic_id = str(uuid.UUID(int=sub_seed % (2**128)))
        deterministic_ts = datetime.fromtimestamp(sub_seed % (2**32) / 1000.0, tz=timezone.utc)
        variants.append(
            PatchVariant(
                id=deterministic_id,
                intent=base.intent,
                target_root=base.target_root,
                source_recipe_id=base.source_recipe_id,
                operations=new_ops,
                required_ops=list(base.required_ops),
                risk_flags=list(base.risk_flags),
                undo_label=f"{base.undo_label} (jitter)",
                validation_plan=base.validation_plan.model_copy(),
                base_plan_id=base.id,
                strategy="param_jitter",
                seed=sub_seed,
                created_at=deterministic_ts,
            )
        )
    return variants


def _jitter(value: int | float, rng: random.Random) -> float:
    factor = 1 + rng.uniform(-_JITTER_RANGE, _JITTER_RANGE)
    return float(value) * factor
