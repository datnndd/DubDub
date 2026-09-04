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

import numpy as np  # sidecar venv dependency (rapidocr pulls it) — hashing pass

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


def _crop_from(msg: dict) -> dict:
    """Normalized crop rect {left, top, right, bottom} from the request.

    ``crop`` (user-drawn rect, 0..1) wins; ``band_top`` keeps v1 behaviour
    (full-width bottom strip)."""
    crop = msg.get("crop")
    band_top = max(0.05, min(float(msg.get("band_top") or 0.55), 0.95))
    if isinstance(crop, dict):
        try:
            left = max(0.0, min(float(crop.get("left") or 0.0), 0.98))
            top = max(0.0, min(float(crop.get("top") or band_top), 0.98))
            right = max(left + 0.02, min(float(crop.get("right") or 1.0), 1.0))
            bottom = max(top + 0.02, min(float(crop.get("bottom") or 1.0), 1.0))
            return {"left": left, "top": top, "right": right, "bottom": bottom}
        except (TypeError, ValueError):
            pass
    return {"left": 0.0, "top": band_top, "right": 1.0, "bottom": 1.0}


def _crop_filter(crop: dict) -> str:
    """ffmpeg crop expression from a normalized rect (w:h:x:y order)."""
    w = crop["right"] - crop["left"]
    h = crop["bottom"] - crop["top"]
    return (
        f"crop=trunc(iw*{w:.4f}):trunc(ih*{h:.4f}):"
        f"trunc(iw*{crop['left']:.4f}):trunc(ih*{crop['top']:.4f})"
    )


def _extract_frames(video_path: str, fps: float, crop: dict, out_dir: str) -> int:
    """Sample frames with the host ffmpeg, cropped to the chosen region.

    Cropping makes every OCR box bigger/faster/more accurate.
    Returns the sampled frame count."""
    vf = f"fps={fps},{_crop_filter(crop)}"
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


# ── pass 2: boundary refinement (aHash, KHÔNG OCR) ────────────────────────
#
# Biên cue từ pass coarse lệch ±(1/fps). Pass này stream dải crop ở
# refine_fps qua ffmpeg rawvideo-gray, aHash 8×8 mỗi khung (numpy — rẻ),
# rồi mở rộng/mang mỗi cue ra tới khung "giống" gần nhất trong cửa sổ
# ±``window_s``. Fail-soft: mọi ngoại lệ → coarse cues nguyên vẹn.
_REFINE_SCALE_W = 160
_REFINE_SCALE_H = 90
_REFINE_WINDOW_S = 0.6
_HAMMING_THRESHOLD = 10  # /64 — aHash cùng phụ đề thường lệch ≤ vài bit


def _ahash(gray) -> int:
    """8×8 average hash của khung gray (numpy array h×w)."""
    h, w = gray.shape
    ys = np.arange(0, 8) * h // 8
    xs = np.arange(0, 8) * w // 8
    ys2 = list(ys[1:]) + [h]
    xs2 = list(xs[1:]) + [w]
    blocks = np.zeros((8, 8), dtype=np.float64)
    for by in range(8):
        for bx in range(8):
            blocks[by, bx] = gray[ys[by]:ys2[by], xs[bx]:xs2[bx]].mean()
    bits = (blocks >= blocks.mean()).flatten()
    return int.from_bytes(np.packbits(bits).tobytes(), "big")


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _extract_band_hashes(video_path: str, crop: dict, refine_fps: float, send) -> list:
    """[(t, hash)] của dải crop ở refine_fps — streaming rawvideo, không file."""
    vf = (
        f"fps={refine_fps},{_crop_filter(crop)},"
        f"scale={_REFINE_SCALE_W}:{_REFINE_SCALE_H},format=gray"
    )
    w, h = _REFINE_SCALE_W, _REFINE_SCALE_H
    frame_bytes = w * h
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", video_path, "-vf", vf,
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        stdout=subprocess.PIPE,
    )
    hashes: list = []
    step = 1.0 / refine_fps
    idx = 0
    assert proc.stdout is not None
    while True:
        chunk = proc.stdout.read(frame_bytes)
        if not chunk or len(chunk) < frame_bytes:
            break
        hashes.append((idx * step, _ahash(np.frombuffer(chunk, dtype=np.uint8).reshape(h, w))))
        idx += 1
        if idx % max(10, int(refine_fps * 10)) == 0:
            send({"op": "progress", "stage": "refine", "frames_done": idx,
                  "percent": -1, "heartbeat": True})
    proc.stdout.close()
    proc.wait(timeout=60)
    return hashes


def refine_cue_boundaries(cues: list, hashes: list, refine_fps: float,
                          window_s: float = _REFINE_WINDOW_S) -> list:
    """Tinh chỉnh biên cue bằng so khung aHash trong cửa sổ ±window_s.

    Anchor = khung gần (start+end)/2 nhất (phụ đề chắc chắn đang hiện).
    Lùi/tiến tới khung ĐẦU TIÊN khác anchor (hamming > ngưỡng) trong cửa sổ.
    Không chồng cue: end của mỗi cue bị kẹp ≤ start của cue kế tiếp.
    """
    if not cues or not hashes:
        return cues
    step = 1.0 / refine_fps
    times = [t for t, _ in hashes]
    out = []
    for cue in cues:
        s, e = float(cue["start"]), float(cue["end"])
        mid = (s + e) / 2.0
        anchor_i = min(range(len(times)), key=lambda k: abs(times[k] - mid))
        anchor = hashes[anchor_i][1]

        def sim(idx: int) -> bool:
            return _hamming(hashes[idx][1], anchor) <= _HAMMING_THRESHOLD

        lo = max(0, anchor_i - int((window_s + (mid - s)) * refine_fps) - 1)
        ns_i = anchor_i
        k = anchor_i - 1
        while k >= lo and sim(k):
            ns_i = k
            k -= 1

        hi = min(len(times) - 1, anchor_i + int((window_s + (e - mid)) * refine_fps) + 1)
        ne_i = anchor_i
        k = anchor_i + 1
        while k <= hi and sim(k):
            ne_i = k
            k += 1

        ns = max(0.0, round(max(s - window_s, times[ns_i]), 3))
        ne = round(min(e + window_s, times[ne_i] + step), 3)
        out.append({**cue, "start": ns, "end": max(0.1, ne)})
    out.sort(key=lambda c: c["start"])
    for a, b in zip(out, out[1:]):
        if b["start"] < a["end"]:
            mid = round((a["end"] + b["start"]) / 2.0, 3)
            a["end"] = min(a["end"], mid)
            b["start"] = max(b["start"], mid)
    return out


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
    crop = _crop_from(msg)
    text_score = float(msg.get("text_score") or 0.5)
    refine_fps = max(4.0, min(float(msg.get("refine_fps") or 10.0), 30.0))

    out_dir = tempfile.mkdtemp(prefix="hardsub_ocr_")
    try:
        _send(stdout, {"op": "progress", "stage": "sampling", "percent": 0})
        total = _extract_frames(video_path, fps, crop, out_dir)
        _log(stdout, f"sampling done — {total} frames")
        cues = _run_ocr(out_dir, text_score, total, fps, lambda o: _send(stdout, o))
        _log(stdout, f"ocr done — {len(cues)} coarse cues; refining boundaries…")
        try:
            hashes = _extract_band_hashes(video_path, crop, refine_fps,
                                          lambda o: _send(stdout, o))
            cues = refine_cue_boundaries(cues, hashes, refine_fps)
        except Exception as exc:  # noqa: BLE001 — refinement là tối ưu, fail-soft
            _log(stdout, f"boundary refinement skipped ({type(exc).__name__}: {exc})")
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
