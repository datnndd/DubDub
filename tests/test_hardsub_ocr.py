"""Hardsub OCR — cue grouping, SRT building, soft-sub detection, route wiring.

The grouping function lives in the sidecar module but is stdlib-only at
module level, so the parent's tests import it directly. Everything network
or model-shaped is faked; the ffmpeg-fixture test generates a real tiny
container (ffmpeg is available in CI).
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import pytest
import numpy as np

from engines.hardsub_ocr.main import group_frames_to_cues
from services import hardsub_ocr as hso


# ── cue grouping ────────────────────────────────────────────────────────────


def test_groups_consecutive_identical_frames_into_one_cue():
    frames = [{"i": i, "text": "Xin chào thế giới"} for i in range(6)]
    cues = group_frames_to_cues(frames, fps=2.0)
    assert cues == [{"start": 0.0, "end": 3.0, "text": "Xin chào thế giới"}]


def test_blank_frame_closes_the_cue():
    frames = (
        [{"i": i, "text": "Cue A"} for i in range(2)]
        + [{"i": 2, "text": ""}, {"i": 3, "text": ""}]
        + [{"i": i, "text": "Cue B"} for i in range(4, 6)]
    )
    cues = group_frames_to_cues(frames, fps=2.0)
    assert [(c["text"], c["start"], c["end"]) for c in cues] == [
        ("Cue A", 0.0, 1.0),
        ("Cue B", 2.0, 3.0),
    ]


def test_text_change_splits_cues_without_blank_frame():
    frames = [{"i": 0, "text": "First line"}, {"i": 1, "text": "Second different line"}]
    cues = group_frames_to_cues(frames, fps=2.0)
    assert len(cues) == 2
    assert cues[0]["end"] == 0.5  # previous cue ends where the next frame starts
    assert cues[1]["start"] == 0.5


def test_minor_ocr_noise_stays_in_the_same_cue():
    """The same subtitle with one OCR flicker (a stray space) must not split."""
    frames = [
        {"i": 0, "text": "Xin chào thế giới"},
        {"i": 1, "text": "Xin chào  thế giới"},
        {"i": 2, "text": "Xin chào thế giới"},
    ]
    cues = group_frames_to_cues(frames, fps=2.0)
    assert len(cues) == 1
    assert cues[0]["end"] == 1.5


def test_consecutive_seconds_deduplication_extends_end_time():
    """Consecutive seconds with duplicate text do not create new cues; non-duplicate text creates new start time."""
    frames = [
        {"i": 0, "text": ""},
        {"i": 1, "text": "Xin chào bạn"},
        {"i": 2, "text": "Xin chào bạn"},
        {"i": 3, "text": "Xin chào bạn"},
        {"i": 4, "text": "Hôm nay thời tiết đẹp"},
        {"i": 5, "text": "Hôm nay thời tiết đẹp"},
        {"i": 6, "text": ""},
    ]
    cues = group_frames_to_cues(frames, fps=1.0)
    assert len(cues) == 2
    assert cues[0] == {"start": 1.0, "end": 4.0, "text": "Xin chào bạn"}
    assert cues[1] == {"start": 4.0, "end": 6.0, "text": "Hôm nay thời tiết đẹp"}


def test_levenshtein_and_containment_similarity_merges_ocr_jitter():
    """OCR jitter (added dot, partial word recognition) is merged into the same cue."""
    frames = [
        {"i": 0, "text": "Chương trình tự động lồng tiếng"},
        {"i": 1, "text": "Chương trình tự động lồng tiếng."},
        {"i": 2, "text": "Chương trình tự động lồng"},
    ]
    cues = group_frames_to_cues(frames, fps=1.0)
    assert len(cues) == 1
    assert cues[0]["start"] == 0.0
    assert cues[0]["end"] == 3.0


def test_adaptive_gate_skips_static_frames_before_model_inference(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import engines.hardsub_ocr.main as sidecar

    for i in range(8):
        (tmp_path / f"f_{i:05d}.png").write_bytes(b"frame")
    thumbs = [np.zeros((8, 24), dtype=np.float32) for _ in range(8)]
    thumbs[5] = np.ones((8, 24), dtype=np.float32)
    calls = []
    frame_index = [0]

    def next_thumb(_path):
        thumb = thumbs[frame_index[0]]
        frame_index[0] += 1
        return thumb

    monkeypatch.setattr(sidecar, "_frame_thumbnail", next_thumb)

    class FakeEngine:
        def __call__(self, path):
            calls.append(path)
            return SimpleNamespace(txts=["same"], scores=[0.99], boxes=[[[0, 0], [1, 0], [1, 1], [0, 1]]])

    monkeypatch.setattr(sidecar, "_create_ocr_engine", lambda _model: FakeEngine())
    sidecar._run_ocr(str(tmp_path), 0.5, 8, 2.0, lambda _event: None)
    assert len(calls) < 8


# ── SRT building ────────────────────────────────────────────────────────────


def test_build_srt_round_trips_through_the_real_parser():
    from services.srt_parser import parse_srt

    cues = [
        {"start": 0.0, "end": 1.5, "text": "Xin chào thế giới"},
        {"start": 2.0, "end": 3.25, "text": "Dòng thứ hai"},
    ]
    srt = hso.build_srt(cues)
    parsed = parse_srt(srt)
    assert not parsed.segments or all("text" in s for s in parsed.segments)
    assert len(parsed.segments) == 2
    assert parsed.segments[0]["text"] == "Xin chào thế giới"
    assert abs(parsed.segments[1]["end"] - 3.25) < 0.01


def test_build_srt_skips_empty_cues():
    srt = hso.build_srt([
        {"start": 0.0, "end": 1.0, "text": ""},
        {"start": 1.0, "end": 2.0, "text": "hello"},
    ])
    assert "hello" in srt
    assert srt.count("-->") == 1


# ── v2: crop đa vùng + boundary refinement ─────────────────────────────────


def test_crop_filter_generalizes_band():
    from engines.hardsub_ocr.main import _crop_filter

    crop = {"left": 0.1, "top": 0.5, "right": 0.9, "bottom": 1.0}
    assert _crop_filter(crop) == (
        "crop=trunc(iw*0.8000):trunc(ih*0.5000):trunc(iw*0.1000):trunc(ih*0.5000)"
    )


def test_crop_from_request_prefers_user_rect_and_clamps():
    from engines.hardsub_ocr.main import _crop_from

    msg = {"band_top": 0.55, "crop": {"left": 0.05, "top": -0.2, "right": 1.4, "bottom": 0.8}}
    crop = _crop_from(msg)
    assert crop == {"left": 0.05, "top": 0.0, "right": 1.0, "bottom": 0.8}
    # không gửi crop → dải dưới v1 nguyên vẹn
    assert _crop_from({"band_top": 0.6}) == {"left": 0.0, "top": 0.6, "right": 1.0, "bottom": 1.0}


def test_refine_boundaries_snap_to_real_subtitle_interval():
    """Coarse biên lệch (1.0–3.0) so với phụ đề thật (1.0–3.2): refinement
    phải kéo end ra 3.2 bằng aHash, không cần OCR thêm."""
    from engines.hardsub_ocr.main import refine_cue_boundaries

    H_GAP, H_SUB = 0x0000, 0xFFFF
    hashes = []
    for i in range(101):  # 0.0 → 10.0 bước 0.1
        t = i / 10.0
        h = H_SUB if 1.0 <= t <= 3.19 else H_GAP
        hashes.append((round(t, 3), h))
    cues = [{"start": 1.0, "end": 3.0, "text": "Xin chào"}]
    refined = refine_cue_boundaries(cues, hashes, refine_fps=10.0)
    assert refined[0]["start"] == pytest.approx(1.0, abs=0.11)
    assert refined[0]["end"] == pytest.approx(3.2, abs=0.11)


def test_refine_falls_back_to_coarse_when_no_hashes():
    from engines.hardsub_ocr.main import refine_cue_boundaries

    cues = [{"start": 1.0, "end": 2.0, "text": "x"}]
    assert refine_cue_boundaries(cues, [], 10.0) == cues


def test_refined_cues_never_overlap():
    from engines.hardsub_ocr.main import refine_cue_boundaries

    # hai phụ đề liền kề — refinement không được làm chúng chồng nhau
    H1, H2, H_GAP = 0x1111, 0x2222, 0x0000
    hashes = []
    for i in range(60):  # 0 → 6.0
        t = i / 10.0
        h = H1 if 1.0 <= t <= 2.0 else (H2 if 2.1 <= t <= 4.0 else H_GAP)
        hashes.append((round(t, 3), h))
    cues = [
        {"start": 1.0, "end": 2.0, "text": "A"},
        {"start": 2.0, "end": 4.0, "text": "B"},
    ]
    refined = refine_cue_boundaries(cues, hashes, refine_fps=10.0)
    for a, b in zip(refined, refined[1:]):
        assert a["end"] <= b["start"] + 1e-9


# ── v2: crop đa vùng + boundary refinement ─────────────────────────────────


def test_crop_filter_generalizes_band():
    from engines.hardsub_ocr.main import _crop_filter

    crop = {"left": 0.1, "top": 0.5, "right": 0.9, "bottom": 1.0}
    assert _crop_filter(crop) == (
        "crop=trunc(iw*0.8000):trunc(ih*0.5000):trunc(iw*0.1000):trunc(ih*0.5000)"
    )


def test_crop_from_request_prefers_user_rect_and_clamps():
    from engines.hardsub_ocr.main import _crop_from

    msg = {"band_top": 0.55, "crop": {"left": 0.05, "top": -0.2, "right": 1.4, "bottom": 0.8}}
    crop = _crop_from(msg)
    assert crop == {"left": 0.05, "top": 0.0, "right": 1.0, "bottom": 0.8}
    # không gửi crop → dải dưới v1 nguyên vẹn
    assert _crop_from({"band_top": 0.6}) == {"left": 0.0, "top": 0.6, "right": 1.0, "bottom": 1.0}


def test_refine_boundaries_snap_to_real_subtitle_interval():
    """Coarse biên lệch (1.0–3.0) so với phụ đề thật (1.0–3.2): refinement
    phải kéo end ra 3.2 bằng aHash, không cần OCR thêm."""
    from engines.hardsub_ocr.main import refine_cue_boundaries

    H_GAP, H_SUB = 0x0000, 0xFFFF
    hashes = []
    for i in range(101):  # 0.0 → 10.0 bước 0.1
        t = i / 10.0
        h = H_SUB if 1.0 <= t <= 3.19 else H_GAP
        hashes.append((round(t, 3), h))
    cues = [{"start": 1.0, "end": 3.0, "text": "Xin chào"}]
    refined = refine_cue_boundaries(cues, hashes, refine_fps=10.0)
    assert refined[0]["start"] == pytest.approx(1.0, abs=0.11)
    assert refined[0]["end"] == pytest.approx(3.2, abs=0.11)


def test_refine_falls_back_to_coarse_when_no_hashes():
    from engines.hardsub_ocr.main import refine_cue_boundaries

    cues = [{"start": 1.0, "end": 2.0, "text": "x"}]
    assert refine_cue_boundaries(cues, [], 10.0) == cues


def test_refined_cues_never_overlap():
    from engines.hardsub_ocr.main import refine_cue_boundaries

    # hai phụ đề liền kề — refinement không được làm chúng chồng nhau
    H1, H2, H_GAP = 0x1111, 0x2222, 0x0000
    hashes = []
    for i in range(60):  # 0 → 6.0
        t = i / 10.0
        h = H1 if 1.0 <= t <= 2.0 else (H2 if 2.1 <= t <= 4.0 else H_GAP)
        hashes.append((round(t, 3), h))
    cues = [
        {"start": 1.0, "end": 2.0, "text": "A"},
        {"start": 2.0, "end": 4.0, "text": "B"},
    ]
    refined = refine_cue_boundaries(cues, hashes, refine_fps=10.0)
    for a, b in zip(refined, refined[1:]):
        assert a["end"] <= b["start"] + 1e-9


# ── soft-sub detection (real tiny container) ────────────────────────────────


@pytest.mark.skipif(
    subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode != 0,
    reason="ffmpeg not on PATH",
)
def test_detect_and_extract_soft_subtitle_from_real_container(tmp_path):
    srt_src = tmp_path / "sub.srt"
    srt_src.write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nPhụ đề mềm\n",
        encoding="utf-8",
    )
    out = tmp_path / "clip.mkv"
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=d=1:s=320x240",
         "-f", "srt", "-i", str(srt_src),
         "-map", "0:v", "-map", "1", "-c:v", "libx264", "-c:s", "srt",
         str(out)],
        capture_output=True,
    )
    if r.returncode != 0:  # exotic build without the srt muxer
        pytest.skip("ffmpeg build cannot mux srt")

    subs = hso.detect_soft_subtitles(str(out))
    assert len(subs) >= 1
    text = hso.extract_soft_subtitle(str(out), 0)
    assert "Phụ đề mềm" in text


@pytest.mark.asyncio
async def test_dub_hardsub_extract_generator_and_prep_event(monkeypatch, tmp_path):
    """Verify dub_hardsub_extract and its _hardsub_gen task generator run cleanly
    with _prep_event without any NameError, streaming progress and creating hardsub.srt."""
    from core.db import init_db
    init_db()
    from api.routers.dub_core import dub_hardsub_extract, _save_job
    from schemas.requests import HardsubExtractRequest
    from core.tasks import task_manager

    jid = "test_ocr_job"
    job_dir = tmp_path / jid
    job_dir.mkdir(parents=True, exist_ok=True)
    video_file = job_dir / "original.mp4"
    video_file.write_bytes(b"dummy video data")

    job_data = {
        "video_path": str(video_file),
        "filename": "original.mp4",
        "duration": 5.0,
        "segments": None,
        "dubbed_tracks": {},
    }
    _save_job(jid, job_data)
    monkeypatch.setattr("api.routers.dub_core._safe_job_dir", lambda _: str(job_dir))

    # Mock run_ocr_client to call progress callback and return cues
    def fake_run_ocr_client(vpath, **kwargs):
        cb = kwargs.get("progress_cb")
        if cb:
            cb({"frames_done": 5, "frames_total": 10, "percent": 50,
                "ocr_calls": 3, "decoded_frames": 5, "skipped_frames": 2,
                "cache_hits": 0, "current_text": "Live text"})
        return [{"start": 1.0, "end": 3.0, "text": "Phụ đề trích xuất OCR"}]

    monkeypatch.setattr("services.hardsub_ocr.run_ocr_client", fake_run_ocr_client)

    req = HardsubExtractRequest(mode="ocr", fps=2.0)
    res = await dub_hardsub_extract(jid, req)
    assert "task_id" in res
    task_id = res["task_id"]

    # Verify task was registered with task_manager and execute the generator
    assert task_id in task_manager.active_tasks
    queued_tid, func, args, kwargs = await task_manager.queue.get()
    assert queued_tid == task_id
    events = []
    async for evt in func(*args, **kwargs):
        events.append(evt)

    # Check emitted events
    combined = "".join(events)
    assert "hardsub_start" in combined
    assert "hardsub_progress" in combined
    assert "hardsub_done" in combined
    import json
    progress_evt = [json.loads(line[6:]) for line in combined.splitlines()
                    if line.startswith("data: ") and '"ocr_calls"' in line][-1]
    assert progress_evt["ocr_calls"] == 3
    assert progress_evt["decoded_frames"] == 5
    assert progress_evt["skipped_frames"] == 2
    assert progress_evt["current_text"] == "Live text"
    done_evt = [json.loads(line[6:]) for line in combined.splitlines() if line.startswith("data: ") and "hardsub_done" in line][0]
    assert done_evt["segments"][0]["text"] == "Phụ đề trích xuất OCR"

    # Check hardsub.srt was written to disk
    srt_file = job_dir / "hardsub.srt"
    assert srt_file.is_file()
    assert "Phụ đề trích xuất OCR" in srt_file.read_text(encoding="utf-8-sig")
