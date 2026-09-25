# -*- coding: utf-8 -*-
"""Media ingestion records, probing, and local store."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from videotrans.configure.config import ROOT_DIR, TEMP_DIR
from videotrans.util._ffprobe import get_video_info

def get_upload_dir() -> Path:
    try:
        from videotrans.core.storage_config import get_storage_path
        p = get_storage_path("uploads_dir")
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        p = Path(TEMP_DIR) / "webui_uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p


UPLOAD_DIR = get_upload_dir()


@dataclass(frozen=True)
class MediaRecord:
    id: str
    path: Path
    filename: str
    size_bytes: int
    info: dict[str, Any]

    def snapshot(self) -> dict[str, Any]:
        width = int(self.info.get("width", 0) or 0)
        height = int(self.info.get("height", 0) or 0)
        return {
            "id": self.id,
            "filename": self.filename,
            "sizeBytes": self.size_bytes,
            "durationMs": int(self.info.get("time", 0) or 0),
            "resolution": f"{width}x{height}" if width and height else None,
            "fps": float(self.info.get("video_fps", 0) or 0),
            "videoCodec": self.info.get("video_codec_name") or None,
            "audioCodec": self.info.get("audio_codec_name") or None,
            "container": self.info.get("format_name") or None,
            "bitrate": int(self.info.get("bit_rate", 0) or 0),
            "audioSampleRate": int(self.info.get("audio_sample_rate", 0) or 0),
            "audioChannels": int(self.info.get("audio_channels", 0) or 0),
            "hasVideo": bool(self.info.get("video_streams")),
            "hasAudio": bool(self.info.get("streams_audio")),
        }


class MediaStore:
    def __init__(self, upload_dir: Path | None = None, probe: Callable[[str | Path], dict[str, Any]] = get_video_info) -> None:
        self._custom_upload_dir = Path(upload_dir) if upload_dir is not None else None
        if self._custom_upload_dir is not None:
            self._custom_upload_dir.mkdir(parents=True, exist_ok=True)
        self._probe = probe
        self._records: dict[str, MediaRecord] = {}
        self._lock = threading.Lock()

    @property
    def upload_dir(self) -> Path:
        if self._custom_upload_dir is not None:
            self._custom_upload_dir.mkdir(parents=True, exist_ok=True)
            return self._custom_upload_dir
        return get_upload_dir()

    def inspect(self, path: Path, filename: str, media_id: str | None = None) -> MediaRecord:
        info = dict(self._probe(path))
        has_media = bool(
            info.get("video_streams")
            or info.get("streams_audio")
            or (info.get("width") and info.get("height"))
            or info.get("audio_sample_rate")
            or info.get("time")
        )
        if not has_media:
            raise ValueError("The selected file contains no readable media streams")
        if (info.get("width") and info.get("height")) and not info.get("video_streams"):
            info["video_streams"] = 1
        rec_id = media_id or uuid.uuid4().hex
        record = MediaRecord(rec_id, path, filename, path.stat().st_size, info)
        with self._lock:
            self._records[record.id] = record
        return record

    def get(self, media_id: str) -> MediaRecord | None:
        if not media_id:
            return None
        with self._lock:
            rec = self._records.get(media_id)
            if rec is not None and rec.path.is_file():
                return rec

        # Self-healing lookup across server restarts
        try:
            # 1. Search in upload_dir for files matching media_id prefix
            candidates = list(self.upload_dir.glob(f"{media_id}-*")) + list(self.upload_dir.glob(f"{media_id}.*"))
            for cand in candidates:
                if cand.is_file() and cand.stat().st_size > 0:
                    cand_filename = cand.name.split("-", 1)[1] if "-" in cand.name else cand.name
                    return self.inspect(cand, cand_filename, media_id=media_id)

            # 2. Check SQLite projects table for media_path
            from videotrans.core.project_store import db_conn
            with db_conn() as conn:
                row = conn.execute(
                    "SELECT media_path, name FROM projects WHERE media_id = ? AND media_path IS NOT NULL LIMIT 1",
                    (media_id,),
                ).fetchone()
                if row and row["media_path"]:
                    p = Path(row["media_path"])
                    if p.is_file() and p.stat().st_size > 0:
                        return self.inspect(p, row["name"] or p.name, media_id=media_id)
        except Exception:
            pass

        return None


MEDIA = MediaStore(UPLOAD_DIR, get_video_info)
