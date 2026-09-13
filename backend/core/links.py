"""Project repo URL resolver — single source of truth for deeplinks.

Owned by Plan 01-02 (checker B-6 resolution). Read by:
  - backend/core/error_docs_map.py — error → docs URL mapping
  - (future) backend/services/bug_report.py — prefilled GitHub Issues URL

Resolution source: `pyproject.toml [project.urls].Repository`.

The resolved URL is cached at import time so callers can use the module
constants directly without re-reading files.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("omnivoice.core.links")

# Walk up from this file to find the repo root (the dir containing
# `pyproject.toml`). This lets the module work whether the backend is
# imported under `--app-dir backend` or installed as a wheel.
_THIS = Path(__file__).resolve()


def _find_repo_root() -> Path:
    for ancestor in (_THIS.parent, *_THIS.parents):
        if (ancestor / "pyproject.toml").exists():
            return ancestor
    # Fallback — two levels up from backend/core/links.py
    return _THIS.parent.parent.parent


_REPO_ROOT = _find_repo_root()
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _from_pyproject() -> Optional[str]:
    """Read `[project.urls].Repository` from pyproject.toml via tomllib."""
    try:
        # tomllib is stdlib on 3.11+
        if sys.version_info >= (3, 11):
            import tomllib
        else:  # pragma: no cover — repo pins 3.11+
            import tomli as tomllib  # type: ignore[no-redef]
        with _PYPROJECT.open("rb") as f:
            data = tomllib.load(f)
        repo = data.get("project", {}).get("urls", {}).get("Repository")
        if isinstance(repo, str) and repo.startswith("https://github.com/"):
            # Strip trailing `.git` / slash if present.
            return repo.rstrip("/").removesuffix(".git")
    except Exception:
        logger.debug("links: pyproject.toml read failed", exc_info=True)
    return None


def _resolve() -> str:
    """pyproject Repository URL, with a hardcoded upstream last resort."""
    return _from_pyproject() or "https://github.com/debpalash/VoiceStudio"


PROJECT_REPO_URL: str = _resolve()
PROJECT_REPO_BLOB_MAIN: str = f"{PROJECT_REPO_URL}/blob/main"
