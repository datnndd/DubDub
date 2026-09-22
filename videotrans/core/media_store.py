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

UPLOAD_DIR = Path(TEMP_DIR) / "webui_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
    def __init__(self, upload_dir: Path, probe: Callable[[str | Path], dict[str, Any]]) -> None:
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._probe = probe
        self._records: dict[str, MediaRecord] = {}
        self._lock = threading.Lock()

    def inspect(self, path: Path, filename: str) -> MediaRecord:
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
        record = MediaRecord(uuid.uuid4().hex, path, filename, path.stat().st_size, info)
        with self._lock:
            self._records[record.id] = record
        return record

    def get(self, media_id: str) -> MediaRecord | None:
        with self._lock:
            return self._records.get(media_id)


MEDIA = MediaStore(UPLOAD_DIR, get_video_info)
