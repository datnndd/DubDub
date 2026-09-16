import ast
from pathlib import Path


WEBUI_PATH = Path(__file__).resolve().parents[1] / 'webui.py'


def _webui_module():
    return ast.parse(WEBUI_PATH.read_text(encoding='utf-8'))


def test_translation_ui_exposes_dubbed_audio_only_option():
    module = _webui_module()
    checkbox = next(
        node for node in ast.walk(module)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'only_out_dubbed_audio' for target in node.targets)
    )

    assert isinstance(checkbox.value, ast.Call)
    assert isinstance(checkbox.value.func, ast.Attribute)
    assert checkbox.value.func.attr == 'Checkbox'
    info = next(keyword.value for keyword in checkbox.value.keywords if keyword.arg == 'info')
    assert isinstance(info, ast.Constant)
    assert '视频慢速' in info.value


def test_translation_handler_passes_dubbed_audio_only_to_task_config():
    module = _webui_module()
    handler = next(
        node for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef) and node.name == 'run_translation'
    )
    argument_names = [argument.arg for argument in handler.args.args]
    pairs = []
    for dictionary in ast.walk(handler):
        if isinstance(dictionary, ast.Dict):
            for key, value in zip(dictionary.keys, dictionary.values):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Name):
                    pairs.append((key.value, value.id))

    assert 'only_out_dubbed_audio_val' in argument_names
    assert ('only_out_dubbed_audio', 'only_out_dubbed_audio_val') in pairs


def test_translation_start_button_passes_dubbed_audio_only_value():
    module = _webui_module()
    start_click = next(
        node for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'click'
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == 'start_btn'
    )
    inputs = next(keyword.value for keyword in start_click.keywords if keyword.arg == 'inputs')

    assert isinstance(inputs, ast.List)
    assert any(isinstance(item, ast.Name) and item.id == 'only_out_dubbed_audio' for item in inputs.elts)
