# -*- coding: utf-8 -*-
"""Project model and CRUD operations for persistent workflow state."""
from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from videotrans.configure.config import ROOT_DIR
from videotrans.core.db import db_conn

logger = logging.getLogger("videotrans.project_store")

DEFAULT_PROJECTS_DIR = Path(ROOT_DIR) / "output" / "projects"
PROJECTS_OUTPUT_DIR = DEFAULT_PROJECTS_DIR


def get_projects_root() -> Path:
    """Return configured output directory for projects."""
    try:
        from videotrans.core.storage_config import get_storage_path
        return get_storage_path("output_dir") / "projects"
    except Exception:
        return DEFAULT_PROJECTS_DIR


def get_project_dir(project_id: str) -> Path:
    """Return the base artifact directory for a project with fallback continuity."""
    configured_dir = get_projects_root() / project_id
    if configured_dir.exists():
        return configured_dir
    legacy_dir = DEFAULT_PROJECTS_DIR / project_id
    if legacy_dir.exists():
        return legacy_dir
    return configured_dir


def init_project_dirs(project_id: str) -> dict[str, Path]:
    """Initialize structured output directories for intermediate artifacts."""
    base = get_project_dir(project_id)
    dirs = {
        "root": base,
        "media": base / "media",
        "transcripts": base / "transcripts",
        "dubbing": base / "dubbing",
        "exports": base / "exports",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def _row_to_dict(row: Any) -> dict[str, Any]:
    d = dict(row)
    if "state_json" in d:
        try:
            d["state"] = json.loads(d.pop("state_json") or "{}")
        except Exception:
            d["state"] = {}
    return d


def create_project(
    project_id: Optional[str] = None,
    name: str = "Untitled Project",
    *,
    media_id: Optional[str] = None,
    media_path: Optional[str] = None,
    duration: float = 0.0,
    stage: int = 1,
    status: str = "pending",
    audio_hash: str = "",
    state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Create and persist a new project record and its artifact directories."""
    pid = project_id or uuid.uuid4().hex
    now = time.time()
    state_json = json.dumps(state or {})

    with db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projects
            (id, name, media_id, media_path, duration, stage, status, audio_hash, state_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pid, name, media_id, media_path, duration, stage, status, audio_hash, state_json, now, now),
        )

    init_project_dirs(pid)
    logger.info("Created project %s ('%s')", pid, name)
    return get_project(pid)  # type: ignore[return-value]


def get_project(project_id: str) -> Optional[dict[str, Any]]:
    """Fetch project details including parsed state dictionary."""
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_projects(limit: int = 100) -> list[dict[str, Any]]:
    """List all projects sorted by last updated timestamp descending."""
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def find_project_by_audio_hash(audio_hash: str) -> Optional[dict[str, Any]]:
    """Locate an existing project with the given audio content hash."""
    if not audio_hash:
        return None
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE audio_hash = ? AND audio_hash != '' ORDER BY updated_at DESC LIMIT 1",
            (audio_hash,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def update_project(project_id: str, **kwargs: Any) -> Optional[dict[str, Any]]:
    """Update arbitrary fields of a project record."""
    allowed = {
        "name",
        "media_id",
        "media_path",
        "duration",
        "stage",
        "status",
        "audio_hash",
        "state_json",
    }
    updates = {}
    for k, v in kwargs.items():
        if k == "state":
            updates["state_json"] = json.dumps(v or {})
        elif k in allowed:
            updates[k] = v

    if not updates:
        return get_project(project_id)

    updates["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [project_id]

    with db_conn() as conn:
        conn.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)

    return get_project(project_id)


def update_project_state(
    project_id: str,
    state_dict: dict[str, Any],
    stage: Optional[int] = None,
    status: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Update state snapshot and optionally advance the workflow stage."""
    if isinstance(state_dict, dict):
        try:
            dirs = init_project_dirs(project_id)
            if "segments" in state_dict and isinstance(state_dict["segments"], list):
                (dirs["transcripts"] / "segments.json").write_text(
                    json.dumps(state_dict["segments"], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                from videotrans.util.help_srt import ms_to_time_string
                srt_lines = []
                for idx, seg in enumerate(state_dict["segments"]):
                    line_num = seg.get("id") or seg.get("line") or (idx + 1)
                    start_ms = int(round(float(seg.get("startSec", 0)) * 1000)) if "startSec" in seg else 0
                    end_ms = int(round(float(seg.get("endSec", 0)) * 1000)) if "endSec" in seg else 0
                    st_raw = seg.get("startTime") or ms_to_time_string(ms=start_ms)
                    et_raw = seg.get("endTime") or ms_to_time_string(ms=end_ms)
                    text = seg.get("sourceText") or seg.get("text") or ""
                    srt_lines.append(f"{line_num}\n{st_raw} --> {et_raw}\n{text}\n")
                if srt_lines:
                    (dirs["transcripts"] / "source.srt").write_text("\n".join(srt_lines), encoding="utf-8")
            if "transcript_options" in state_dict and state_dict["transcript_options"]:
                (dirs["transcripts"] / "transcript_options.json").write_text(
                    json.dumps(state_dict["transcript_options"], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        except Exception as e:
            logger.warning("Failed to persist transcript artifacts for project %s: %s", project_id, e)

    kwargs: dict[str, Any] = {"state": state_dict}
    if stage is not None:
        kwargs["stage"] = stage
    if status is not None:
        kwargs["status"] = status
    return update_project(project_id, **kwargs)


def delete_project(project_id: str, delete_files: bool = True) -> bool:
    """Delete project from database and optionally remove artifact directory."""
    with db_conn() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        deleted = cur.rowcount > 0

    if deleted and delete_files:
        pdir = get_project_dir(project_id)
        if pdir.exists() and pdir.is_dir():
            try:
                shutil.rmtree(pdir)
            except Exception as exc:
                logger.warning("Failed to remove project dir %s: %s", pdir, exc)

    return deleted
