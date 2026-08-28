"""Hardsub OCR sidecar venv probe + lazy bootstrap.

Mirrors ``engines.vienue.bootstrap``: a PyPI-package engine (``rapidocr`` +
``onnxruntime`` — ONNX conversions of the PP-OCR models) that must not fight
the parent app's pins. Probe order:

    1. ``${OMNIVOICE_HARDSUB_OCR_VENV}`` — a user-provided venv directory.
    2. ``backend/engines/hardsub_ocr/.venv/`` — this package's own venv.
    3. Bootstrap: ``uv venv`` + ``uv pip install rapidocr onnxruntime``.

The ffmpeg binary is NOT bootstrapped here — it is the host's (VoiceStudio
already publishes media tools on PATH; the sidecar inherits the env).
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

logger = logging.getLogger("omnivoice.hardsub_ocr.bootstrap")

#: Absolute path to the sidecar entrypoint.
HARDSUB_OCR_SIDECAR_SCRIPT: Path = Path(__file__).parent / "main.py"

#: This package's owned venv (Probe 2).
_ENGINES_VENV_DIR: Path = Path(__file__).parent / ".venv"

#: Optional env var pointing at a user-provided venv directory (Probe 1).
_VENV_DIR_ENV: str = "OMNIVOICE_HARDSUB_OCR_VENV"

#: Minimal OCR stack: ONNX conversions of the PP-OCR models (RapidOCR) —
#: no paddlepaddle runtime (its 3.x PIR/oneDNN CPU path is currently broken;
#: see docs/dubbing/hardsub-ocr.md for the measured comparison).
_PIP_REQUIREMENTS = ["rapidocr", "onnxruntime"]

#: Per-process resolution cache. Cleared by :func:`invalidate` for tests.
_resolved_python: Optional[Path] = None

_UV_VENV_TIMEOUT_S = 120
_UV_PIP_INSTALL_TIMEOUT_S = 900


def invalidate() -> None:
    """Clear the resolved-python cache. Tests call this between scenarios."""
    global _resolved_python
    _resolved_python = None


def is_hardsub_ocr_installed() -> bool:
    """Cheap file-existence check for a usable OCR venv."""
    for cand in _probe_paths():
        if cand.is_file():
            return True
    return False


def resolve_hardsub_ocr_venv() -> Path:
    """Resolve the sidecar's Python interpreter (probe order above). Memoised.
    Raises :exc:`RuntimeError` when nothing is available and uv is missing."""
    global _resolved_python
    if _resolved_python is not None:
        return _resolved_python

    user_venv = os.environ.get(_VENV_DIR_ENV)
    unproven: Optional[Path] = None

    for cand in _probe_paths():
        if not cand.is_file():
            continue
        verdict = _venv_can_import_rapidocr(cand)
        if verdict == "yes":
            logger.info("hardsub OCR venv resolved: %s", cand)
            _resolved_python = cand
            return cand
        if verdict == "unproven" and unproven is None:
            unproven = cand

    if unproven is not None:
        logger.warning(
            "hardsub OCR venv %s could not be verified in time; using it anyway (#1414).",
            log_safe(unproven),
        )
        _resolved_python = unproven
        return unproven

    _bootstrap_engines_venv()
    return _venv_python_path(_ENGINES_VENV_DIR)


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


def _venv_can_import_rapidocr(python_path: Path) -> ProbeResult:
    return venv_can_import(
        python_path, "import rapidocr", engine="hardsub_ocr", logger=logger,
    )


def _locate_uv() -> Optional[str]:
    bundled = os.environ.get("OMNIVOICE_BUNDLED_UV")
    if bundled and Path(bundled).is_file():
        return bundled
    return shutil.which("uv")


def _bootstrap_engines_venv() -> None:
    """Create engines/hardsub_ocr/.venv and install the OCR stack."""
    uv = _locate_uv()
    if not uv:
        raise RuntimeError(
            "Hardsub OCR needs its own venv but uv was not found on PATH (and "
            "OMNIVOICE_BUNDLED_UV was not set). Install uv from "
            "https://docs.astral.sh/uv/ and re-launch VoiceStudio, or set "
            "OMNIVOICE_BUNDLED_UV to the absolute path of a uv binary."
        )
    logger.info(
        "Bootstrapping hardsub OCR venv at %s (this can take a few minutes)",
        _ENGINES_VENV_DIR,
    )
    try:
        subprocess.run(
            [uv, "venv", str(_ENGINES_VENV_DIR)],
            check=True, timeout=120, capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"uv venv failed for hardsub OCR bootstrap: "
            f"{exc.stderr.decode('utf-8', errors='replace') if exc.stderr else exc}"
        ) from exc
    python_path = _venv_python_path(_ENGINES_VENV_DIR)
    try:
        subprocess.run(
            [uv, "pip", "install", "--python", str(python_path), *_PIP_REQUIREMENTS],
            check=True, timeout=900, capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "uv pip install failed during hardsub OCR bootstrap: "
            f"{exc.stderr.decode('utf-8', errors='replace') if exc.stderr else exc}. "
            "See docs/dubbing/hardsub-ocr.md."
        ) from exc
    if _venv_can_import_rapidocr(python_path) == "no":
        raise RuntimeError(
            "hardsub OCR bootstrap completed but `import rapidocr` still fails "
            f"from {python_path}. See docs/dubbing/hardsub-ocr.md."
        )
    logger.info("hardsub OCR venv bootstrap successful: %s", python_path)


__all__ = [
    "HARDSUB_OCR_SIDECAR_SCRIPT",
    "invalidate",
    "is_hardsub_ocr_installed",
    "resolve_hardsub_ocr_venv",
]
