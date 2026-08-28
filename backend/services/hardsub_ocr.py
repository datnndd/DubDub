"""Hardsub subtitle extraction: soft-sub detect/extract + OCR sidecar client.

Two subtitle sources for a dub job:

* **soft-sub** — real text tracks inside the container (mkv/mp4). Detected
  with ffprobe, extracted with ffmpeg; no OCR involved.
* **hardsub** — subtitles burned into the picture. The OCR sidecar
  (``engines.hardsub_ocr``) samples frames, runs RapidOCR (the ONNX
  conversion of PaddleOCR's PP-OCR models), and groups per-frame text into
  timed cues. Everything lands in the same SRT path ``/dub/import-srt``
  uses, so downstream handling is identical to a user-supplied .srt.
"""
from __future__ import annotations

import json
import logging
import os
import struct
import subprocess
import sys
from typing import Callable, Optional

logger = logging.getLogger("omnivoice.hardsub_ocr")

#: Threshold below which a text box is treated as OCR noise.
DEFAULT_TEXT_SCORE = 0.5


def detect_soft_subtitles(video_path: str) -> list[dict]:
    """List subtitle streams inside the video (ffprobe). Empty when none."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", "-select_streams", "s", video_path],
            capture_output=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("ffprobe subtitle scan failed: %s", e)
        return []
    if r.returncode != 0:
        return []
    try:
        streams = json.loads(r.stdout.decode("utf-8", errors="replace")).get("streams", [])
    except Exception:  # noqa: BLE001
        return []
    out = []
    for i, s in enumerate(streams):
        tags = s.get("tags") or {}
        out.append({
            "index": s.get("index", i),
            "codec": s.get("codec_name", ""),
            "language": tags.get("language", ""),
            "title": tags.get("title", ""),
        })
    return out


def extract_soft_subtitle(video_path: str, stream_index: int = 0) -> str:
    """Extract one subtitle stream to SRT text. Raises on failure."""
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-map", f"0:s:{stream_index}",
         "-f", "srt", "-"],
        capture_output=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(
            "ffmpeg subtitle extraction failed: "
            + r.stderr.decode("utf-8", errors="replace")[-400:]
        )
    return r.stdout.decode("utf-8-sig", errors="replace")


def build_srt(cues: list[dict]) -> str:
    """Render OCR cues as SRT text (the format the rest of the pipeline eats)."""

    def _ts(t: float) -> str:
        ms = int(round(t * 1000))
        h, rem = divmod(ms, 3600_000)
        m, rem = divmod(rem, 60_000)
        s, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    blocks = []
    for i, cue in enumerate(cues, start=1):
        text = (cue.get("text") or "").strip()
        if not text:
            continue
        blocks.append(
            f"{i}\n{_ts(float(cue['start']))} --> {_ts(float(cue['end']))}\n{text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def run_ocr_client(
    video_path: str,
    *,
    fps: float = 2.0,
    band_top: float = 0.55,
    text_score: float = DEFAULT_TEXT_SCORE,
    progress_cb: Optional[Callable[[dict], None]] = None,
) -> list[dict]:
    """Run the OCR sidecar over one video; return [{start, end, text}].

    Blocking (spawns the sidecar subprocess); call from a worker thread.
    ``progress_cb`` receives {"frames_done", "frames_total", "percent"}.
    """
    from engines.hardsub_ocr.bootstrap import (
        HARDSUB_OCR_SIDECAR_SCRIPT,
        resolve_hardsub_ocr_venv,
    )

    python = str(resolve_hardsub_ocr_venv())
    script = str(HARDSUB_OCR_SIDECAR_SCRIPT)
    proc = subprocess.Popen(
        [python, script],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        send = lambda obj: (  # noqa: E731
            proc.stdin.write(struct.pack("!I", len(json.dumps(obj, separators=(",", ":")).encode()))),
            proc.stdin.write(json.dumps(obj, separators=(",", ":")).encode()),
            proc.stdin.flush(),
        )

        def recv():
            header = proc.stdout.read(4)
            if len(header) < 4:
                return None
            (n,) = struct.unpack("!I", header)
            return json.loads(proc.stdout.read(n).decode("utf-8"))

        ready = recv()
        if not ready or ready.get("op") != "ready":
            raise RuntimeError("hardsub OCR sidecar failed its handshake")
        send({"op": "ocr_video", "video_path": video_path, "fps": fps,
              "band_top": band_top, "text_score": text_score})
        while True:
            msg = recv()
            if msg is None:
                raise RuntimeError("hardsub OCR sidecar exited mid-job")
            op = msg.get("op")
            if op == "progress":
                if progress_cb:
                    progress_cb(msg)
            elif op == "cues":
                return list(msg.get("cues") or [])
            elif op == "error":
                raise RuntimeError(
                    f"hardsub OCR failed ({msg.get('stage')}): {msg.get('message')}"
                )
    finally:
        try:
            proc.stdin.write(struct.pack("!I", len(b'{"op":"shutdown"}')) + b'{"op":"shutdown"}')
            proc.stdin.flush()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


__all__ = [
    "DEFAULT_TEXT_SCORE",
    "build_srt",
    "detect_soft_subtitles",
    "extract_soft_subtitle",
    "run_ocr_client",
]
