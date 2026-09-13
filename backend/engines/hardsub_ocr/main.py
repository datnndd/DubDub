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
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import traceback

import numpy as np  # sidecar venv dependency (rapidocr pulls it) — hashing pass

MAX_FRAME_BYTES = 64 * 1024 * 1024
_THUMB_W = 24
_THUMB_H = 8
_CHANGE_THRESHOLD = 0.02
_CONFIRM_EVERY = 4
_LOW_CONFIDENCE = 0.65


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


def _clean_for_compare(text: str) -> str:
    import re
    t = re.sub(r"[^\w\s]", " ", (text or "").lower(), flags=re.UNICODE)
    return " ".join(t.split())


def is_duplicate_or_similar(t1: str, t2: str, similarity: float = 0.75) -> bool:
    """Kiểm tra xem 2 dòng transcript ở các giây liên tiếp có trùng lặp không."""
    c1 = _clean_for_compare(t1)
    c2 = _clean_for_compare(t2)
    if not c1 or not c2:
        return False
    # Khớp chính xác
    if c1 == c2:
        return True
    # Tỷ lệ tương đồng xâu (difflib)
    ratio = difflib.SequenceMatcher(None, c1, c2).ratio()
    if ratio >= similarity:
        return True
    # Chứa nhau (karaoke text hoặc OCR từng phần)
    len1, len2 = len(c1), len(c2)
    if len1 >= 4 and len2 >= 4:
        if c1 in c2 or c2 in c1:
            if min(len1, len2) / max(len1, len2) >= 0.65:
                return True
    # Trùng lặp từ vựng (Token Jaccard)
    w1, w2 = set(c1.split()), set(c2.split())
    if w1 and w2:
        jaccard = len(w1 & w2) / len(w1 | w2)
        if jaccard >= 0.70:
            return True
    return False


def group_frames_to_cues(frames: list, fps: float, similarity: float = 0.75) -> list:
    """Gom các khung OCR liên tiếp thành các cue phụ đề có mốc thời gian.

    - Nếu 2 transcript ở các giây/khung liên tiếp trùng nhau (is_duplicate_or_similar):
      không tạo segment mới, chỉ kéo dài thời gian kết thúc của cue hiện tại.
    - Nếu không trùng: chốt cue trước và tạo mốc thời gian mới (start time mới).
    - Khung trống sẽ chốt cue (có bộ đệm 1 khung chống chập chờn khi fps >= 1.8).
    """
    step = 1.0 / max(fps, 0.001)
    cues: list = []
    cur: dict | None = None
    gap_count = 0
    max_gap_frames = 1 if fps >= 1.8 else 0

    for fr in frames:
        idx = int(fr.get("i") or 0)
        text = (fr.get("text") or "").strip()
        t0 = idx * step

        if not text:
            if cur:
                gap_count += 1
                if gap_count > max_gap_frames:
                    cues.append(cur)
                    cur = None
                    gap_count = 0
            continue

        is_dup = False
        if cur is not None:
            is_dup = (
                is_duplicate_or_similar(text, cur.get("_last_text") or "", similarity)
                or is_duplicate_or_similar(text, cur.get("text") or "", similarity)
            )

        if is_dup and cur:
            cur["end"] = round((idx + 1) * step, 3)
            cur["_last_i"] = idx
            cur["_last_text"] = text
            if len(text) > len(cur["text"]) and is_duplicate_or_similar(text, cur["text"], 0.7):
                cur["text"] = text
            gap_count = 0
            continue

        if cur:
            cues.append(cur)
        cur = {
            "start": round(t0, 3),
            "end": round((idx + 1) * step, 3),
            "text": text,
            "_last_i": idx,
            "_last_text": text,
        }
        gap_count = 0

    if cur:
        cues.append(cur)

    out: list = []
    for c in cues:
        c.pop("_last_i", None)
        c.pop("_last_text", None)
        if c.get("text") and len(c["text"].strip()) >= 1:
            out.append(c)

    return out


# ── frame extraction + OCR (heavy imports inside) ─────────────────────────


def _auto_detect_band(video_path: str) -> "dict | None":
    """Đề xuất vùng phụ đề bằng mật độ cạnh dọc trên nửa dưới khung.

    Phase 3.1 của kế hoạch hardsub v2: thay dải cố định 55% bằng vùng được
    đo từ video — sample ~90 khung trải đều (tối đa 10 phút đầu), tính
    edge-energy theo hàng (gradient dọc = viền ngang của chữ), chọn cửa sổ
    trượt 8 hàng có năng lượng đậm đặc nhất. Trả rect chuẩn hoá {left: 0,
    top, right: 1, bottom} hoặc None khi đo thất bại (caller dùng dải
    mặc định). Thuần numpy trên stream rawvideo — không OCR, không file tạm.
    """
    import numpy as np  # noqa: F811 — shadowing an toàn nếu caller đã có

    SAMPLES_CAP = 90          # số khung phân tích tối đa
    BAND_SCAN = 0.5           # chỉ quét nửa dưới khung (0.5 → 1.0)
    SCAN_ROWS = 45            # độ phân giải hàng của vùng quét
    WINDOW_ROWS = 14  # chieu cao cua so de xuat (~31% chieu cao — du cho 2 dong)
    MIN_ENERGY_RATIO = 0.18   # đỉnh cửa sổ / tổng — dưới ngưỡng này coi như
                              # không tìm thấy vùng phụ đề rõ → dùng mặc định

    vf = (
        f"fps={SAMPLES_CAP / 60:.3f},crop=iw:ih*{BAND_SCAN}:0:ih*{BAND_SCAN},"
        f"scale={_REFINE_SCALE_W}:{SCAN_ROWS},format=gray"
    )
    try:
        proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-i", video_path, "-vf", vf,
             "-frames:v", str(SAMPLES_CAP), "-f", "rawvideo",
             "-pix_fmt", "gray", "-"],
            stdout=subprocess.PIPE,
        )
    except OSError:
        return None
    w, h = _REFINE_SCALE_W, SCAN_ROWS
    frame_bytes = w * h
    rows = np.zeros(h, dtype=np.float64)
    n = 0
    try:
        assert proc.stdout is not None
        while n < SAMPLES_CAP:
            chunk = proc.stdout.read(frame_bytes)
            if not chunk or len(chunk) < frame_bytes:
                break
            img = np.frombuffer(chunk, dtype=np.uint8).reshape(h, w).astype(np.float32)
            # gradient dọc: viền ngang của chữ có độ tương phản mạnh theo hàng
            rows[: h - 1] += np.abs(np.diff(img, axis=0)).mean(axis=1)
            n += 1
    except Exception:  # noqa: BLE001 — sampling fail → dùng mặc định
        proc.kill()
        return None
    finally:
        try:
            proc.stdout.close()
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()

    if n < max(3, SAMPLES_CAP // 10):
        return None

    energy = rows / max(rows.sum(), 1e-6)
    # cửa sổ trượt 8 hàng trong vùng quét — chọn cửa sổ có tổng năng lượng cao nhất
    best_lo, best_sum = 0, -1.0
    for lo in range(0, h - WINDOW_ROWS + 1):
        s = float(energy[lo : lo + WINDOW_ROWS].sum())
        if s > best_sum:
            best_sum, best_lo = s, lo
    if best_sum < MIN_ENERGY_RATIO:
        return None
    # mo rong thich nghi: nuot hang ke cuon con nang luong dang ke (≤3 hang moi phia)
    lo = max(0, best_lo - 1)
    hi = min(h, best_lo + WINDOW_ROWS + 1)
    row_max = max(float(energy.max()), 1e-6)
    lo, hi = best_lo, best_lo + WINDOW_ROWS
    for _ in range(3):
        if lo > 0 and energy[lo - 1] >= 0.03 * row_max:
            lo -= 1
        if hi < h and energy[hi] >= 0.03 * row_max:
            hi += 1
    top = BAND_SCAN + (lo / h) * (1.0 - BAND_SCAN)
    bottom = BAND_SCAN + (hi / h) * (1.0 - BAND_SCAN)
    return {"left": 0.0, "top": round(max(0.05, top), 3),
            "right": 1.0, "bottom": round(min(1.0, bottom), 3)}


def _crop_from(msg: dict) -> dict:
    """Normalized crop rect {left, top, right, bottom} from the request.

    ``crop`` (user-drawn rect, 0..1) wins; ``band_top`` keeps v1 behaviour
    (full-width bottom strip)."""
    crop = msg.get("crop")
    band_top = max(0.05, min(float(msg.get("band_top") or 0.55), 0.95))
    if isinstance(crop, dict):
        try:
            left = max(0.0, min(float(crop.get("left") or 0.0), 0.98))
            top = max(0.0, min(float(crop.get("top", band_top)), 0.98))
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


def _frame_thumbnail(path: str):
    """Read a tiny normalized grayscale thumbnail for pre-inference gating."""
    try:
        import cv2
        image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if image is None or image.size == 0:
            return None
        thumb = cv2.resize(image, (_THUMB_W, _THUMB_H), interpolation=cv2.INTER_AREA)
        lo, hi = float(thumb.min()), float(thumb.max())
        if hi - lo < 1e-6:
            return np.zeros((_THUMB_H, _THUMB_W), dtype=np.float32)
        return (thumb.astype(np.float32) - lo) / (hi - lo)
    except Exception:
        # If an image decoder is unavailable, preserve the old correctness path.
        return None


def _thumbnail_delta(previous, current) -> float:
    if previous is None or current is None:
        return 1.0
    return float(np.mean(np.abs(previous - current)))


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _extract_band_hashes(video_path: str, crop: dict, refine_fps: float, send, windows=None) -> list:
    """Return ``(timestamp, hash)`` for refinement windows only.

    ``windows`` is a list of ``(start_s, end_s)`` intervals. Keeping it local
    avoids the previous full-video high-FPS pass.
    """
    vf = (
        f"fps={refine_fps},{_crop_filter(crop)},"
        f"scale={_REFINE_SCALE_W}:{_REFINE_SCALE_H},format=gray"
    )
    w, h = _REFINE_SCALE_W, _REFINE_SCALE_H
    frame_bytes = w * h
    hashes: list = []
    step = 1.0 / refine_fps
    intervals = windows or [(0.0, float("inf"))]
    processed = 0
    for start_s, end_s in intervals:
        args = ["ffmpeg", "-v", "error"]
        if start_s > 0:
            args += ["-ss", f"{start_s:.3f}"]
        args += ["-i", video_path]
        if end_s != float("inf"):
            args += ["-t", f"{max(0.01, end_s - start_s):.3f}"]
        args += ["-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"]
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        idx = 0
        assert proc.stdout is not None
        while True:
            chunk = proc.stdout.read(frame_bytes)
            if not chunk or len(chunk) < frame_bytes:
                break
            hashes.append((round(start_s + idx * step, 3), _ahash(np.frombuffer(chunk, dtype=np.uint8).reshape(h, w))))
            idx += 1
            processed += 1
            if processed % max(10, int(refine_fps * 2)) == 0:
                send({"op": "progress", "stage": "refine", "frames_done": processed,
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


def _create_ocr_engine(model_id: str):
    if model_id == "rapidocr":
        from rapidocr import RapidOCR

        return RapidOCR()
    if model_id != "paddleocr":
        raise ValueError(f"Unsupported OCR model: {model_id}")
    from importlib.metadata import version
    if int(version('paddleocr').split('.')[0]) < 3:
        if __package__:
            from .ocr._paddle import PaddleOcrProvider
        else:
            from ocr._paddle import PaddleOcrProvider
        provider = PaddleOcrProvider(device='cpu')
        provider._current_lang = provider.map_language(None)
        provider._require_engine('cpu')
        return provider.recognize
    from paddleocr import PaddleOCR
    from types import SimpleNamespace

    # Native CPU path is explicit opt-in. Disable the PIR/oneDNN path that
    # failed on the repository's Windows fixture (docs/dubbing/hardsub-ocr.md).
    engine = PaddleOCR(
        ocr_version="PP-OCRv5", device="cpu", enable_mkldnn=False,
        use_doc_orientation_classify=False, use_doc_unwarping=False,
        use_textline_orientation=False,
    )

    def predict(path):
        texts, scores, boxes = [], [], []
        for result in engine.predict(path):
            texts.extend(result.get("rec_texts", []))
            scores.extend(result.get("rec_scores", []))
            boxes.extend(result.get("rec_polys", []))
        return SimpleNamespace(txts=texts, scores=scores, boxes=boxes)

    return predict


def _run_ocr(out_dir: str, text_score: float, total: int, fps: float, send,
             model_id: str = "rapidocr") -> list:
    send({"op": "progress", "stage": "loading", "percent": None, "model_id": model_id})
    engine = _create_ocr_engine(model_id)
    started = time.monotonic()
    files = sorted(
        (f for f in os.listdir(out_dir) if f.endswith(".png")),
        key=lambda n: int(n[2:-4]),
    )
    frames: list = []
    previous_thumb = None
    previous_text = ""
    previous_confidence = 0.0
    ocr_calls = 0
    skipped_frames = 0
    cache_hits = 0
    signature_cache = {}
    for i, name in enumerate(files):
        path = os.path.join(out_dir, name)
        thumb = _frame_thumbnail(path)
        signature = None
        if thumb is not None:
            signature = _ahash((thumb * 255).astype(np.uint8))
        delta = _thumbnail_delta(previous_thumb, thumb)
        needs_ocr = (
            i == 0
            or delta > _CHANGE_THRESHOLD
            or i % _CONFIRM_EVERY == 0
            or previous_confidence < _LOW_CONFIDENCE
        )
        res = None
        if needs_ocr and signature is not None and signature in signature_cache and signature_cache[signature][1] >= _LOW_CONFIDENCE:
            previous_text, previous_confidence = signature_cache[signature]
            cache_hits += 1
            needs_ocr = False
        if needs_ocr:
            res = engine(path)
            ocr_calls += 1
        else:
            skipped_frames += 1
        box_items = []
        accepted_scores = []
        if res is not None:
            txts = getattr(res, "txts", None)
            scores = getattr(res, "scores", None)
            boxes = getattr(res, "boxes", None)
            contract_lines = getattr(res, 'lines', None)
            if contract_lines is not None:
                for line_number, line in enumerate(contract_lines):
                    score = float(getattr(line, 'confidence', 0) or 0)
                    text = str(getattr(line, 'text', '') or '').strip()
                    if score >= text_score and text:
                        accepted_scores.append(score)
                        box = getattr(line, 'box', None)
                        y_pos = float(box[1]) if box is not None else float(line_number)
                        box_items.append((y_pos, text))
            elif txts is not None and scores is not None:
                for idx_b, (txt, score) in enumerate(zip(txts, scores)):
                    if float(score or 0.0) >= text_score and txt and str(txt).strip():
                        accepted_scores.append(float(score or 0.0))
                        y_pos = 0.0
                        if boxes is not None and idx_b < len(boxes):
                            try:
                                y_pos = float(np.mean([pt[1] for pt in boxes[idx_b]]))
                            except Exception:
                                y_pos = float(idx_b)
                        box_items.append((y_pos, str(txt).strip()))
            elif isinstance(res, (list, tuple)):
                items = res[0] if (isinstance(res, tuple) and len(res) >= 1 and isinstance(res[0], list)) else res
                for item in items:
                    if isinstance(item, (list, tuple)) and len(item) >= 3:
                        box, txt, score = item[0], item[1], item[2]
                        if float(score or 0.0) >= text_score and txt and str(txt).strip():
                            accepted_scores.append(float(score or 0.0))
                            y_pos = 0.0
                            try:
                                y_pos = float(np.mean([pt[1] for pt in box]))
                            except Exception:
                                y_pos = 0.0
                            box_items.append((y_pos, str(txt).strip()))
        # Sắp xếp các dòng chữ từ trên xuống dưới theo toạ độ Y
        box_items.sort(key=lambda x: x[0])
        frame_text = " ".join(item[1] for item in box_items) if res is not None else previous_text
        if res is not None:
            previous_text = frame_text
            previous_confidence = max(accepted_scores, default=0.0)
            if signature is not None:
                signature_cache[signature] = (previous_text, previous_confidence)
        previous_thumb = thumb
        frames.append({"i": i, "text": frame_text})
        if total > 0:
            elapsed = max(0.0, time.monotonic() - started)
            send({
                "op": "progress", "stage": "ocr", "frames_done": i + 1,
                "frames_total": total,
                "percent": int((i + 1) * 100 / max(1, total)),
                "elapsed_seconds": round(elapsed, 2),
                "eta_seconds": round(elapsed / (i + 1) * max(0, total - i - 1), 2),
                "video_time": round(i / fps, 3),
                "current_text": frame_text,
                "model_id": model_id,
                "ocr_calls": ocr_calls,
                "decoded_frames": i + 1,
                "skipped_frames": skipped_frames,
                "cache_hits": cache_hits,
            })
    return group_frames_to_cues(frames, fps)


def _handle_ocr_video(msg: dict, stdout) -> None:
    video_path = msg.get("video_path")
    if not video_path or not os.path.isfile(video_path):
        raise ValueError(f"ocr_video: video not found: {video_path!r}")
    fps = float(msg.get("fps") or 2.0)
    text_score = float(msg.get("text_score") or 0.5)
    refine_fps = max(4.0, min(float(msg.get("refine_fps") or 10.0), 30.0))
    do_refine = bool(msg.get("refine", False))
    checkpoint_path = msg.get("checkpoint_path")
    time_ranges = msg.get("time_ranges")
    # Vùng quét: user vẽ (crop) > auto-suggest theo mật độ cạnh > dải dưới
    # mặc định 55%. Auto-suggest chỉ chạy khi user KHÔNG gửi band_top tùy
    # chỉnh (đặt band_top phi mặc định = chủ ý dùng dải cố định).
    if isinstance(msg.get("crop"), dict):
        crop = _crop_from(msg)
        _log(stdout, "crop: user-drawn region")
    elif "band_top" not in msg:
        suggested = _auto_detect_band(video_path)
        if suggested is not None:
            crop = suggested
            _log(stdout, f"crop: auto-detected subtitle band {suggested}")
        else:
            crop = _crop_from(msg)
            _log(stdout, "crop: auto-detect found no clear band — default bottom strip")
    else:
        crop = _crop_from(msg)

    # The parent owns its scratch directory and can clean it after cancellation.
    out_dir = msg.get("out_dir") or tempfile.mkdtemp(prefix="hardsub_ocr_")
    try:
        _send(stdout, {"op": "progress", "stage": "sampling", "percent": 0})
        if os.environ.get('OMNIVOICE_OCR_LEGACY') == '1':
            total = _extract_frames(video_path, fps, crop, out_dir)
            cues = _run_ocr(out_dir, text_score, total, fps, lambda o: _send(stdout, o),
                            model_id=msg.get('model_id', 'rapidocr'))
        else:
            if __package__:
                from .ocr._runtime import scan_video
            else:
                from ocr._runtime import scan_video
            model_id = msg.get('model_id', 'rapidocr')
            _send(stdout, {'op': 'progress', 'stage': 'loading', 'model_id': model_id})
            engine = _create_ocr_engine(model_id)
            if __package__:
                from .ocr._identity import model_identity
            else:
                from ocr._identity import model_identity
            identity = model_identity(model_id) if checkpoint_path else model_id
            started = time.monotonic()
            def report(event):
                seconds = event['timestamp_ms'] / 1000
                duration = event['duration_ms'] / 1000
                elapsed = time.monotonic() - started
                frames_total = math.ceil(duration * fps)
                frames_done = min(frames_total, round(seconds * fps) + 1)
                _send(stdout, dict(op='progress', stage='ocr', model_id=model_id,
                    frames_done=frames_done,
                    frames_total=frames_total, percent=100 * frames_done / frames_total if frames_total else 0,
                    video_time=seconds, elapsed_seconds=elapsed,
                    eta_seconds=elapsed * max(0, duration - seconds) / seconds if seconds > 0 else None,
                    current_text=event['latest_text'], ocr_calls=event['ocr_calls'],
                    decoded_frames=event['decoded_frames'], skipped_frames=event['skipped_frames'],
                    cache_hits=event['cache_hits']))
            cues = scan_video(video_path, crop, engine, fps=fps, threshold=text_score,
                              checkpoint_path=checkpoint_path, model_identity=identity,
                              on_progress=report, refine=do_refine, refine_fps=refine_fps,
                              time_ranges=time_ranges)
        _log(stdout, f"ocr done — {len(cues)} cues extracted")
        if do_refine and os.environ.get('OMNIVOICE_OCR_LEGACY') == '1':
            try:
                _log(stdout, "refining cue boundaries…")
                _send(stdout, {"op": "progress", "stage": "refine", "percent": None})
                windows = []
                for cue in cues:
                    start = max(0.0, float(cue.get("start", 0.0)) - _REFINE_WINDOW_S)
                    end = float(cue.get("end", start)) + _REFINE_WINDOW_S
                    windows.append((start, end))
                windows.sort()
                merged = []
                for start, end in windows:
                    if merged and start <= merged[-1][1]:
                        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                    else:
                        merged.append((start, end))
                hashes = _extract_band_hashes(video_path, crop, refine_fps,
                                              lambda o: _send(stdout, o), windows=merged)
                cues = refine_cue_boundaries(cues, hashes, refine_fps)
            except Exception as exc:  # noqa: BLE001 — refinement là tối ưu, fail-soft
                _log(stdout, f"boundary refinement skipped ({type(exc).__name__}: {exc})")
        _send(stdout, {"op": "cues", "cues": cues})
    finally:
        if not msg.get("out_dir"):
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
