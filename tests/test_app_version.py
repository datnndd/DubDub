"""The runtime app version must come from package metadata, not a stale literal
(prevents the recurring "0.4.0"/"0.2.7" drift — Greptile #145)."""
import re
from importlib.metadata import version

from core.version import APP_VERSION


def test_app_version_is_semver():
    assert re.match(r"^\d+\.\d+\.\d+", APP_VERSION), APP_VERSION


def test_app_version_matches_installed_package_metadata():
    # In any synced env the package is installed; APP_VERSION must equal it
    # (i.e. it's read from pyproject, not hardcoded).
    assert APP_VERSION == version("omnivoice")


def test_all_version_files_in_lockstep():
    """``frontend/package.json`` is the SINGLE SOURCE OF TRUTH for the app
    version: vite injects ``__APP_VERSION__`` from it (first-run footer + every
    bug report).

    The other two declarations are toolchain-required CI-guarded mirrors —
    pyproject.toml (uv needs a literal) and backend/core/version.py's
    ``_FALLBACK_VERSION`` (the last resort, whose drift to "0.3.5" is why the
    v0.3.6 build reported 0.3.5). Catch any drift here in CI.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]

    def _toml_version(p: Path) -> str:
        return re.search(r'(?m)^version\s*=\s*"([^"]+)"', p.read_text()).group(1)

    def _named_literal(p: Path, name: str) -> str:
        return re.search(rf'(?m)^{name}\s*=\s*"([^"]+)"', p.read_text()).group(1)

    import json

    canonical = json.loads((root / "frontend/package.json").read_text())["version"]
    mirrors = {
        "pyproject.toml": _toml_version(root / "pyproject.toml"),
        "core/version.py": _named_literal(root / "backend/core/version.py", "_FALLBACK_VERSION"),
    }
    drifted = {k: v for k, v in mirrors.items() if v != canonical}
    assert not drifted, f"version mirrors drifted from package.json={canonical!r}: {drifted}"


def test_fallback_version_resolves_to_pyproject():
    """When package metadata is unavailable (frozen build / raw checkout), the
    version must still resolve to pyproject — never the stale literal that made
    the v0.3.6 build report "0.3.5"."""
    from pathlib import Path

    from core.version import _fallback_version

    root = Path(__file__).resolve().parents[1]
    pyproject = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"', (root / "pyproject.toml").read_text()
    ).group(1)
    assert _fallback_version() == pyproject

