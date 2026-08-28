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
