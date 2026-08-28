"""VieNeu-TTS venv probe + lazy bootstrap.

Resolves which Python interpreter runs the VieNeu sidecar. Mirrors
``engines.dots_tts.bootstrap`` / ``engines.confucius4.bootstrap`` — same
subprocess-isolation shape — but simpler: ``vieneu`` is a PyPI package, so
there is no user clone directory to point at.

Probe order (priority):

    1. ``${OMNIVOICE_VIENEU_VENV}`` — a user-provided venv directory.
    2. ``backend/engines/vienue/.venv/`` — this package's own venv.
    3. Bootstrap: ``uv venv`` then ``uv pip install vieneu`` (>=3.0 — the
       v3-Turbo generation) into the package venv. Fully automatic: no clone
       dir, no manual step. Weights still download from HuggingFace on first
       synthesize, reported through sidecar progress frames.

Caching: memoised after first success. Tests reset via :func:`invalidate`.

Security: same posture as the other engine bootstraps — bootstrap never
touches HF_TOKEN; the sidecar's stderr is redacted by the parent's
``HFTokenRedactor``; the install comes from PyPI (user-run `uv`).
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from engines._venv_probe import ProbeResult, log_safe, venv_can_import

logger = logging.getLogger("omnivoice.vienue.bootstrap")

#: Absolute path to the sidecar entrypoint.
VIENEU_SIDECAR_SCRIPT: Path = Path(__file__).parent / "main.py"

#: This package's owned venv (Probe 2).
_ENGINES_VENV_DIR: Path = Path(__file__).parent / ".venv"

#: Optional env var pointing at a user-provided venv directory (Probe 1).
_VENV_DIR_ENV: str = "OMNIVOICE_VIENEU_VENV"

#: Version floor: the v3-Turbo generation (48 kHz, ONNX CPU path) shipped in
#: the 3.x line of the PyPI package.
_VIENEU_PIP_SPEC = "vieneu>=3.0"

#: Per-process resolution cache. Cleared by :func:`invalidate` for tests.
_resolved_python: Optional[Path] = None

_UV_VENV_TIMEOUT_S = 120
_UV_PIP_INSTALL_TIMEOUT_S = 1800


def _uv_env() -> "dict[str, str] | None":
    """uv cache co-location for installs on a non-system volume (see
    services.sidecar_install.uv_subprocess_env)."""
    try:
        from services.sidecar_install import uv_subprocess_env
        return uv_subprocess_env(_ENGINES_VENV_DIR.parent.parent)
    except Exception:  # noqa: BLE001 — cache co-location is an optimization
        return None


# ── public API ────────────────────────────────────────────────────────────


def invalidate() -> None:
    """Clear the resolved-python cache. Tests call this between scenarios."""
    global _resolved_python
    _resolved_python = None


def is_vieneu_installed() -> bool:
    """Cheap file-existence check for a usable vieneu venv. Does NOT spawn
    the venv Python — that's saved for :func:`resolve_vieneu_venv`."""
    for cand in _probe_paths():
        if cand.is_file():
            return True
    return False


def resolve_vieneu_venv() -> Path:
    """Resolve the sidecar's Python interpreter (probe order in the module
    docstring). Memoised. Raises :exc:`RuntimeError` if none can be located
    and the bootstrap path is unavailable (no uv)."""
    global _resolved_python
    if _resolved_python is not None:
        return _resolved_python

    user_venv = os.environ.get(_VENV_DIR_ENV)

    # A candidate whose probe ran out of time (#1414): preferred over
    # bootstrapping or declaring the engine missing, but only after every
    # candidate has had its chance to prove itself outright.
    unproven: Optional[Path] = None

    # Probe 1 — user-provided venv directory.
    if user_venv:
        cand = _venv_python_path(Path(user_venv))
        if cand.is_file():
            verdict = _venv_can_import_vieneu(cand)
            if verdict == "yes":
                logger.info("vieneu venv resolved from %s: %s", _VENV_DIR_ENV, cand)
                _resolved_python = cand
                return cand
            if verdict == "unproven":
                unproven = cand

    # Probe 2 — this package's own venv.
    cand = _venv_python_path(_ENGINES_VENV_DIR)
    if cand.is_file():
        verdict = _venv_can_import_vieneu(cand)
        if verdict == "yes":
            logger.info("vieneu venv resolved from engines path: %s", cand)
            _resolved_python = cand
            return cand
        if verdict == "unproven" and unproven is None:
            unproven = cand

    if unproven is not None:
        # Nothing proved itself, but something plausible is installed. Use
        # it: a venv that really is broken fails the sidecar handshake with
        # a real error, which beats reinstalling over the top of a working
        # install (#1414).
        logger.warning(
            "vieneu venv %s could not be verified in time; using it anyway "
            "rather than treating a slow import as a missing install (#1414).",
            log_safe(unproven),
        )
        _resolved_python = unproven
        return unproven

    # Probe 3 — bootstrap from PyPI (no clone dir needed for vieneu).
    cand = _bootstrap_engines_venv()
    _resolved_python = cand
    return cand


# ── internals ─────────────────────────────────────────────────────────────


def _venv_python_path(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _probe_paths() -> list[Path]:
    out: list[Path] = []
    user_venv = os.environ.get(_VENV_DIR_ENV)
    if user_venv:
        out.append(_venv_python_path(Path(user_venv)))
    out.append(_venv_python_path(_ENGINES_VENV_DIR))
    return out


def _venv_can_import_vieneu(python_path: Path) -> ProbeResult:
    """Spawn the candidate python and verify the engine imports.

    Tri-state — "yes" / "no" / "unproven". See ``engines._venv_probe``:
    a probe that runs out of time proves nothing, and treating that as
    "no" is what discarded working user installs (#1414).
    """
    return venv_can_import(
        python_path, "import vieneu", engine="vienue", logger=logger,
    )


def _locate_uv() -> Optional[str]:
    bundled = os.environ.get("OMNIVOICE_BUNDLED_UV")
    if bundled and Path(bundled).is_file():
        return bundled
    return shutil.which("uv")


def _bootstrap_engines_venv() -> Path:
    """Create engines/vienue/.venv and install ``vieneu`` from PyPI."""
    uv = _locate_uv()
    if not uv:
        raise RuntimeError(
            "VieNeu-TTS needs its own venv but uv was not found on PATH (and "
            "OMNIVOICE_BUNDLED_UV was not set). Install uv from "
            "https://docs.astral.sh/uv/ and re-launch VoiceStudio, or set "
            "OMNIVOICE_BUNDLED_UV to the absolute path of a uv binary, or "
            "create backend/engines/vienue/.venv manually and "
            "`uv pip install vieneu` into it."
        )

    logger.info(
        "Bootstrapping vieneu venv at %s (this can take a few minutes on "
        "first launch)", _ENGINES_VENV_DIR,
    )

    try:
        subprocess.run(
            [uv, "venv", str(_ENGINES_VENV_DIR)],
            check=True, timeout=_UV_VENV_TIMEOUT_S, capture_output=True,
            env=_uv_env(),
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"uv venv failed for vieneu bootstrap at {_ENGINES_VENV_DIR}: "
            f"{exc.stderr.decode('utf-8', errors='replace') if exc.stderr else exc}"
        ) from exc

    python_path = _venv_python_path(_ENGINES_VENV_DIR)
    install_cmd = [uv, "pip", "install", "--python", str(python_path), _VIENEU_PIP_SPEC]
    try:
        subprocess.run(
            install_cmd, check=True,
            timeout=_UV_PIP_INSTALL_TIMEOUT_S, capture_output=True,
            env=_uv_env(),
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "uv pip install failed during vieneu bootstrap: "
            f"{exc.stderr.decode('utf-8', errors='replace') if exc.stderr else exc}. "
            "See docs/engines/vieneu-tts.md."
        ) from exc

    # Only a *proven* failure is fatal: a bootstrap that installed correctly
    # and is merely slow to import must not be thrown away after spending
    # minutes on the install (#1414).
    if _venv_can_import_vieneu(python_path) == "no":
        raise RuntimeError(
            "vieneu bootstrap completed but `import vieneu` still fails from "
            f"{python_path}. See docs/engines/vieneu-tts.md."
        )

    logger.info("vieneu venv bootstrap successful: %s", python_path)
    return python_path


__all__ = [
    "VIENEU_SIDECAR_SCRIPT",
    "invalidate",
    "is_vieneu_installed",
    "resolve_vieneu_venv",
]
