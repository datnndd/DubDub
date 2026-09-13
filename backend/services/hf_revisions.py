"""Immutable revision for the sole downloadable model."""

from __future__ import annotations

import os
import re
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{40}\Z")
CURATED_REVISIONS = {
    "k2-fsa/OmniVoice": "c5fdb5ccb189668d56333f77ba2629f4cd7535f4",
}


def revision_for(repo_id: str) -> str:
    try:
        return CURATED_REVISIONS[repo_id]
    except KeyError as exc:
        raise ValueError(f"No reviewed revision is pinned for {repo_id!r}") from exc


def _repo_dir(repo_id: str, cache_dir: str) -> Path:
    return Path(cache_dir) / ("models--" + repo_id.replace("/", "--"))


def remember_revision(repo_id: str, revision: str, cache_dir: str) -> None:
    revision_for(repo_id)
    if not _SHA.fullmatch(revision):
        raise ValueError("Hugging Face revision must be a 40-character commit SHA")
    repo_dir = _repo_dir(repo_id, cache_dir)
    repo_dir.mkdir(parents=True, exist_ok=True)
    marker = repo_dir / "voicestudio-revision"
    temporary = marker.with_suffix(f".tmp-{os.getpid()}")
    temporary.write_text(revision + "\n", encoding="ascii")
    os.replace(temporary, marker)


def installed_revision(repo_id: str, cache_dir: str) -> str:
    curated_revision = revision_for(repo_id)
    repo_dir = _repo_dir(repo_id, cache_dir)
    for marker in (repo_dir / "voicestudio-revision", repo_dir / "refs" / "main"):
        try:
            revision = marker.read_text(encoding="ascii").strip()
        except OSError:
            continue
        if _SHA.fullmatch(revision):
            return revision
    return curated_revision
