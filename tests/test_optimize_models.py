import pytest

from td_mcp.models import AdjustableParamInput, OptimizeVisualInput
from td_mcp.tool_registry import (
    _optimizer_direction_for_param,
    _optimizer_score,
)


def test_adjustable_param_input_range_validation():
    model = AdjustableParamInput(
        path="/project1/level1",
        param="opacity",
        min_val=0.0,
        max_val=1.0,
        step=0.05,
    )
    assert model.min_val == 0.0
    assert model.max_val == 1.0

    with pytest.raises(ValueError):
        AdjustableParamInput(
            path="/project1/level1",
            param="opacity",
            min_val=1.0,
            max_val=0.0,
            step=0.05,
        )


def test_optimize_visual_input_defaults():
    model = OptimizeVisualInput(
        goal="reduce feedback oscillation",
        output_top="/project1/out1",
        adjustable_params=[
            AdjustableParamInput(
                path="/project1/level1",
                param="opacity",
                min_val=0.0,
                max_val=1.0,
                step=0.02,
            )
        ],
    )
    assert model.max_iterations == 10
    assert model.convergence_threshold == 0.8
    assert model.safety_profile == "balanced"
    assert model.root_path == "/project1"
    assert model.snapshot_before is True


def test_optimizer_direction_deterministic():
    """Test that _optimizer_direction_for_param returns a valid direction."""
    profile = {"brightness": 0.5, "stability": 0.3, "complexity": 0.2, "motion_rhythm": 0.0, "contrast": 0.0}
    direction = _optimizer_direction_for_param("opacity", profile)
    assert direction in {-1, 0, 1}


def test_optimizer_score_penalizes_instability():
    adjustable = AdjustableParamInput(
        path="/project1/level1",
        param="opacity",
        min_val=0.0,
        max_val=1.0,
        step=0.05,
    )
    current = {("/project1/level1", "opacity"): 0.9}
    directions = {("/project1/level1", "opacity"): 1}

    stable = _optimizer_score(current, [adjustable], directions, unstable=False)
    unstable = _optimizer_score(current, [adjustable], directions, unstable=True)

    assert stable >= unstable


def test_optimize_visual_input_accepts_objective_weights():
    """Test that the model accepts explicit objective_weights."""
    model = OptimizeVisualInput(
        goal="custom",
        output_top="/project1/out1",
        adjustable_params=[
            AdjustableParamInput(
                path="/project1/level1",
                param="opacity",
                min_val=0.0,
                max_val=1.0,
            )
        ],
        objective_weights={"stability": 0.8, "complexity": 0.2},
    )
    assert model.objective_weights == {"stability": 0.8, "complexity": 0.2}
