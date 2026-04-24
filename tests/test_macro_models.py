from td_mcp.models import CreateMacroInput, GetMacroParamsInput, MacroType


def test_create_macro_input_defaults():
    model = CreateMacroInput(macro_type=MacroType.FEEDBACK_LOOP)
    assert model.parent_path == "/project1"
    assert model.nodeX == 0
    assert model.nodeY == 0
    assert model.params is None


def test_get_macro_params_input():
    model = GetMacroParamsInput(macro_type=MacroType.POST_PROCESSING)
    assert model.macro_type.value == "post_processing"
