"""Hardsub OCR sidecar — runs under the hardsub-ocr venv (rapidocr), NEVER the parent.

Wire protocol — length-prefixed JSON over stdin/stdout, byte-identical to the
other sidecars (``engines/_echo/main.py``):

    [ 4-byte big-endian uint32 length ][ N bytes UTF-8 JSON ]

Ops:
    1. sidecar -> parent: {"op": "ready", "engine": "hardsub-ocr"}
    2. parent -> sidecar: {"op": "ping"} -> {"op": "pong", "vram_mb": 0.0}
    3. parent -> sidecar: {"op": "ocr_video", "video_path": "...",
                           "fps": 2.0, "band_top": 0.55, "text_score": 0.5}
       -> {"op": "progress", "stage": "ocr", "frames_done": i,
           "frames_total": N, "percent": p}   (repeating)
       -> {"op": "cues", "cues": [{"start": s, "end": e, "text": "..."}]}
    4. parent -> sidecar: {"op": "shutdown"} -> exit 0

Stdlib-only at module level: grouping (`group_frames_to_cues`) is importable
by the parent's unit tests; the heavy imports (cv2/rapidocr/ffmpeg) happen
inside functions. Frames are sampled by the HOST's ffmpeg into a temp dir
(crop to the subtitle band so OCR sees big text and stays fast), then run
through RapidOCR — the ONNX conversion of PaddleOCR's PP-OCR models.
"""
from __future__ import annotations

import base64
import difflib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import traceback

# Mirrors backend/services/subprocess_backend.py::MAX_FRAME_BYTES.
MAX_FRAME_BYTES = 64 * 1024 * 1024


# ── wire protocol ─────────────────────────────────────────────────────────


def _send(stream, obj: dict) -> None:
    body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    stream.write(struct.pack("!I", len(body)))
    stream.write(body)
    stream.flush()


def _recv(stream):
    header = stream.read(4)
    if len(header) < 4:
        return None  # EOF
    (n,) = struct.unpack("!I", header)
    if n > MAX_FRAME_BYTES:
        raise IOError(f"frame too large: {n}")
    body = bytearray()
    while len(body) < n:
        chunk = stream.read(n - len(body))
        if not chunk:
            raise IOError("short read")
        body.extend(chunk)
    return json.loads(bytes(body).decode("utf-8"))


# ── cue grouping (pure — unit-tested from the parent) ─────────────────────


def _norm_text(text: str) -> str:
    return "".join((text or "").split()).lower()


def group_frames_to_cues(frames: list, fps: float, similarity: float = 0.8) -> list:
    """Collapse per-frame OCR text into timed cues.

    ``frames`` is a list of ``{"i": <frame index>, "text": <str>}`` sorted by
    index. Consecutive frames whose normalized text is similar (difflib ratio
    >= ``similarity``) belong to one cue; the cue spans from the first to the
    LAST matching frame (a subtitle shown for frames i..j ends at (j+1)/fps —
    the next frame's timestamp — so a cue disappears exactly when the frame
    that would contradict it appears). Empty-text frames close the current
    cue (a blank frame means no subtitle on screen).
    """
    step = 1.0 / max(fps, 0.001)
    cues: list = []
    cur: dict | None = None
    last_text = ""
    for fr in frames:
        idx = int(fr.get("i") or 0)
        text = (fr.get("text") or "").strip()
        t0 = idx * step
        if not text:
            if cur:
                cues.append(cur)
                cur = None
                last_text = ""
            continue
        same = cur is not None and (
            _norm_text(text) == _norm_text(last_text)
            or difflib.SequenceMatcher(None, _norm_text(text), _norm_text(last_text)).ratio() >= similarity
        )
        if same and cur:
            cur["end"] = round((idx + 1) * step, 3)
            cur["_last_i"] = idx
            continue
        if cur:
            cues.append(cur)
        cur = {"start": round(t0, 3), "end": round((idx + 1) * step, 3),
               "text": text, "_last_i": idx}
        last_text = text
    if cur:
        cues.append(cur)
    for c in cues:
        c.pop("_last_i", None)
    return cues


# ── frame extraction + OCR (heavy imports inside) ─────────────────────────


def _extract_frames(video_path: str, fps: float, band_top: float, out_dir: str) -> int:
    """Sample frames with the host ffmpeg, cropped to the subtitle band.

    Crop band: ``[band_top*h, h]`` — subtitles live in the bottom strip, and
    cropping it away makes every OCR box bigger/faster/more accurate.
    Returns the sampled frame count."""
    vf = f"fps={fps},crop=iw:ih*{max(0.05, 1.0 - band_top):.4f}:0:ih*{band_top:.4f}"
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vf", vf, os.path.join(out_dir, "f_%05d.png")],
        capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError(
            "ffmpeg frame sampling failed: "
            + r.stderr.decode("utf-8", errors="replace")[-400:]
        )
    return len([f for f in os.listdir(out_dir) if f.endswith(".png")])


def _run_ocr(out_dir: str, text_score: float, total: int, fps: float, send) -> list:
    from rapidocr import RapidOCR  # noqa: F401 — heavy import, sidecar venv only

    engine = RapidOCR()
    files = sorted(
        (f for f in os.listdir(out_dir) if f.endswith(".png")),
        key=lambda n: int(n[2:-4]),
    )
    frames: list = []
    for i, name in enumerate(files):
        path = os.path.join(out_dir, name)
        res = engine(path)
        texts = []
        if res and getattr(res, "txts", None):
            for txt, score in zip(res.txts, res.scores or []):
                if float(score or 0.0) >= text_score:
                    texts.append(txt)
        frames.append({"i": i, "text": " ".join(texts)})
        if total > 0 and (i % 5 == 0 or i == len(files) - 1):
            send({
                "op": "progress", "stage": "ocr", "frames_done": i + 1,
                "frames_total": total,
                "percent": int((i + 1) * 100 / max(1, total)),
            })
    return group_frames_to_cues(frames, fps)


def _handle_ocr_video(msg: dict, stdout) -> None:
    video_path = msg.get("video_path")
    if not video_path or not os.path.isfile(video_path):
        raise ValueError(f"ocr_video: video not found: {video_path!r}")
    fps = float(msg.get("fps") or 2.0)
    band_top = float(msg.get("band_top") or 0.55)
    text_score = float(msg.get("text_score") or 0.5)

    out_dir = tempfile.mkdtemp(prefix="hardsub_ocr_")
    try:
        _send(stdout, {"op": "progress", "stage": "sampling", "percent": 0})
        total = _extract_frames(video_path, fps, band_top, out_dir)
        _log(stdout, f"sampling done — {total} frames")
        cues = _run_ocr(out_dir, text_score, total, fps, lambda o: _send(stdout, o))
        _send(stdout, {"op": "cues", "cues": cues})
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def _log(stdout, line: str) -> None:
    _send(stdout, {"op": "log", "line": line})


# ── main loop ─────────────────────────────────────────────────────────────


def main() -> int:
    stdin = sys.stdin.buffer
    # Frames down a PRIVATE dup'd fd; fd 1 → stderr (#1428).
    _frame_fd = os.dup(1)
    os.dup2(2, 1)
    stdout = os.fdopen(_frame_fd, "wb")

    _send(stdout, {"op": "ready", "engine": "hardsub-ocr"})

    while True:
        try:
            msg = _recv(stdin)
        except Exception as exc:
            _send(stdout, {
                "op": "error", "stage": "recv",
                "message": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            })
            return 1
        if msg is None:
            return 0
        op = msg.get("op") if isinstance(msg, dict) else None
        try:
            if op == "ping":
                _send(stdout, {"op": "pong", "vram_mb": 0.0})
            elif op == "ocr_video":
                _handle_ocr_video(msg, stdout)
            elif op == "shutdown":
                return 0
            else:
                _send(stdout, {
                    "op": "error", "stage": "dispatch",
                    "message": f"unknown op: {op!r}",
                })
        except Exception as exc:
            _send(stdout, {
                "op": "error", "stage": op or "unknown",
                "message": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            })


if __name__ == "__main__":
    sys.exit(main())
