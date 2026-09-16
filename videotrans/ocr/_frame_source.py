"""FFmpeg-based exact-frame decode for OCR ROI work.

The scanner stays decoupled from media decoding: this module supplies
``(timestamp_ms, frame_bgr)`` to the scanner. It also powers the ROI preview
dialog's exact-frame decoding (``frame_at``), so pixels come from the decoder
rather than from a displayed QVideoWidget. Optional deps only: it uses the
ffmpeg binary already required by the app.
"""
import subprocess
import sys

import numpy as np

# Generic subtitle-agnostic timestamp helper.
def _ts_arg(ts_ms):
    ms = int(ts_ms)
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    u = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{u:03d}"


def _cmd(ffmpeg):
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def frame_at(ffmpeg_exe: str, video: str, ts_ms: int):
    """Decode one BGR frame at ts_ms using ffmpeg.

    Returns (frame, width, height) as a numpy (H, W, 3) uint8 BGR array, or
    (None, w, h) when no frame could be decoded.
    """
    ts = _ts_arg(ts_ms)
    cmd = [
        ffmpeg_exe, "-hide_banner", "-nostdin", "-loglevel", "error",
        "-ss", ts, "-i", video,
        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=_cmd(ffmpeg_exe),
    )
    if proc.returncode != 0 or len(proc.stdout) == 0:
        return None, 0, 0

    # Probe width/height for this source (assume constant).
    width, height = _probe_size(ffmpeg_exe, video)
    if width <= 0 or height <= 0:
        return None, 0, 0
    expected = width * height * 3
    buf = proc.stdout
    if len(buf) < expected:
        return None, width, height
    frame = np.frombuffer(buf[:expected], dtype=np.uint8).reshape(height, width, 3)
    return np.array(frame, copy=True), width, height


def _probe_size(ffmpeg_exe: str, video: str):
    cmd = [
        ffmpeg_exe, "-hide_banner", "-nostdin", "-loglevel", "error",
        "-i", video, "-map", "0:v:0", "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "100x100", "-",
    ]
    # Simpler: read via ffprobe-less output. Use ffmpeg -i stderr parse.
    import re
    probe = subprocess.run(
        [ffmpeg_exe, "-hide_banner", "-i", video],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=_cmd(ffmpeg_exe) if sys.platform == "win32" else 0,
    )
    text = probe.stderr.decode("utf-8", errors="replace")
    m = re.search(r"(\d{2,5})x(\d{2,5})", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def sampled_frame_iter(ffmpeg_exe: str, video: str, *, coarse_interval_ms: int = 500, duration_ms: int = 0):
    """Yield (ts_ms, frame) at coarse intervals by random-access ffmpeg seeks."""
    if duration_ms <= 0:
        duration_ms = probe_duration(ffmpeg_exe, video)
    ts = 0
    while ts < duration_ms:
        frame, w, h = frame_at(ffmpeg_exe, video, ts)
        if frame is None:
            ts += coarse_interval_ms
            continue
        yield int(ts), frame
        ts += coarse_interval_ms


def probe_duration(ffmpeg_exe: str, video: str) -> int:
    import re
    probe = subprocess.run(
        [ffmpeg_exe, "-hide_banner", "-i", video],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=_cmd(ffmpeg_exe) if sys.platform == "win32" else 0,
    )
    text = probe.stderr.decode("utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not m:
        return 0
    h, mm, ss = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return int((h * 3600 + mm * 60 + ss) * 1000)
