"""Tests for backend/core/links.py — project repo URL resolver.

The module owns the single source of truth for the GitHub repo URL used by
error → docs deeplinks (and, in Phase 5, by the prefilled bug-report URL).
The 4 tests below pin the resolution order:

  1. Tauri config endpoint wins when present.
  2. Falls back to pyproject's Repository URL when Tauri is unreadable.
  3. The derived `BLOB_MAIN` constant is always `<URL>/blob/main`.
  4. The URL always starts with `https://github.com/`.
"""
from __future__ import annotations

import importlib
import sys


def _fresh_links_module():
    """Drop any cached `core.links` so the next import re-runs `_resolve()`."""
    for mod in list(sys.modules):
        if mod == "core.links":
            del sys.modules[mod]
    import core.links as links  # noqa: WPS433 — needed for re-import
    return importlib.reload(links)


def test_project_repo_url_is_set():
    links = _fresh_links_module()
    assert isinstance(links.PROJECT_REPO_URL, str)
    assert links.PROJECT_REPO_URL.startswith("https://github.com/")


def test_project_repo_blob_main_derives_from_url():
    links = _fresh_links_module()
    assert links.PROJECT_REPO_BLOB_MAIN == links.PROJECT_REPO_URL + "/blob/main"


def test_resolves_from_pyproject_repository():
    """pyproject `[project.urls].Repository` is the only source now that the
    Tauri shell (and its updater-endpoint config) is removed."""
    links = _fresh_links_module()
    url = links._resolve()
    assert url.startswith("https://github.com/")


def test_falls_back_to_hardcoded_when_pyproject_unreadable(monkeypatch, tmp_path):
    """With pyproject missing, `_resolve()` falls back to the hardcoded repository URL."""
    links = _fresh_links_module()
    monkeypatch.setattr(links, "_PYPROJECT", tmp_path / "missing.toml")
    url = links._resolve()
    assert url == "https://github.com/debpalash/VoiceStudio"
