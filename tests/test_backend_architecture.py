"""Mechanical checks for the accepted web-only dependency direction."""

from pathlib import Path


FORBIDDEN_WEBUI_LOOKUPS = ('sys.modules["webui"]', 'sys.modules.get("webui")')


def reverse_webui_dependencies(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if any(marker in path.read_text(encoding="utf-8") for marker in FORBIDDEN_WEBUI_LOOKUPS)
    ]


def test_backend_does_not_reach_into_webui_entrypoint():
    violations = reverse_webui_dependencies(Path("videotrans"))
    assert not violations, (
        "Backend modules must not inspect the webui launcher "
        "(docs/decisions/0002-web-only-runtime.md): "
        + ", ".join(map(str, violations))
    )


def test_reverse_dependency_check_detects_forbidden_fixture(tmp_path):
    fixture = tmp_path / "bad.py"
    fixture.write_text('value = sys.modules.get("webui")\n', encoding="utf-8")
    assert reverse_webui_dependencies(tmp_path) == [fixture]


def test_webui_is_a_thin_launcher():
    source = Path("webui.py").read_text(encoding="utf-8")
    assert '__all__ = ["create_app", "main"]' in source
    assert "videotrans.core" not in source
    assert "videotrans.api.catalog" not in source
