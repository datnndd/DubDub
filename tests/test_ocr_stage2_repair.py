from PIL import Image
import pytest
import shutil
import subprocess

from videotrans.api.ocr_helpers import extract_ocr_segment_text
from videotrans.ocr._frame_source import frame_at


def _frame(*_args):
    return Image.new("RGB", (200, 100), color="white")


def test_stage2_ocr_reuses_provider_across_frames(monkeypatch):
    import videotrans.ocr as ocr

    created = []

    class Provider:
        def __init__(self):
            self.calls = []

        def recognize(self, image, language):
            self.calls.append((image.size, language))
            return {"text": "Hello", "confidence": 0.9}

    def get_provider(**_kwargs):
        provider = Provider()
        created.append(provider)
        return provider

    monkeypatch.setattr(ocr, "get_provider", get_provider)
    result = extract_ocr_segment_text("unused.mp4", 1, 2, (0.1, 0.7, 0.8, 0.2), language="en", frame_fetcher=_frame)
    assert result["text"] == "Hello"
    assert len(created) == 1
    assert len(created[0].calls) > 1
    assert all(language == "en" for _, language in created[0].calls)


def test_stage2_ocr_reports_unreadable_video():
    with pytest.raises(RuntimeError, match="No video frames could be decoded"):
        extract_ocr_segment_text("unused.mp4", 1, 2, (0.1, 0.7, 0.8, 0.2), frame_fetcher=lambda *_: None)


def test_stage2_ocr_reports_provider_failure(monkeypatch):
    import videotrans.ocr as ocr

    class BrokenProvider:
        def recognize(self, image, language):
            raise RuntimeError("PaddleOCR optional component is not installed")

    monkeypatch.setattr(ocr, "get_provider", lambda **_kwargs: BrokenProvider())
    with pytest.raises(RuntimeError, match="PaddleOCR optional component is not installed"):
        extract_ocr_segment_text("unused.mp4", 1, 2, (0.1, 0.7, 0.8, 0.2), frame_fetcher=_frame)


def test_stage2_ocr_empty_result_is_not_an_error(monkeypatch):
    import videotrans.ocr as ocr

    class EmptyProvider:
        def recognize(self, image, language):
            return {"text": "", "confidence": 0}

    monkeypatch.setattr(ocr, "get_provider", lambda **_kwargs: EmptyProvider())
    result = extract_ocr_segment_text("unused.mp4", 1, 2, (0.1, 0.7, 0.8, 0.2), frame_fetcher=_frame)
    assert result["ok"] is True
    assert result["text"] == ""


def test_stage2_ocr_samples_only_within_each_segment_interval():
    requested = []

    def frame_at_time(_path, seconds):
        requested.append(seconds)
        color = "red" if seconds < 2 else "blue"
        return Image.new("RGB", (200, 100), color=color)

    def recognize(frame):
        return {"text": "FIRST" if tuple(frame[0, 0]) == (255, 0, 0) else "SECOND", "confidence": 1}

    first = extract_ocr_segment_text("unused.mp4", 1, 2, (0, 0, 1, 1), frame_fetcher=frame_at_time, ocr_runner=recognize)
    first_times = requested[:]
    requested.clear()
    second = extract_ocr_segment_text("unused.mp4", 2, 3, (0, 0, 1, 1), frame_fetcher=frame_at_time, ocr_runner=recognize)

    assert first["text"] == "FIRST"
    assert second["text"] == "SECOND"
    assert first_times and all(1 <= seconds < 2 for seconds in first_times)
    assert requested and all(2 <= seconds < 3 for seconds in requested)


def test_stage2_ocr_handles_fractional_millisecond_boundaries():
    requested = []

    def frame_at_time(_path, seconds):
        requested.append(seconds)
        return _frame()

    extract_ocr_segment_text("unused.mp4", 1.0004, 1.0032, (0, 0, 1, 1),
                             frame_fetcher=frame_at_time, ocr_runner=lambda _frame: [])
    assert requested and all(1.0004 <= seconds < 1.0032 for seconds in requested)


def test_stage2_ocr_decoder_excludes_next_frame_at_boundary(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    Image.new("RGB", (160, 90), "red").save(first)
    Image.new("RGB", (160, 90), "blue").save(second)
    video = tmp_path / "adjacent.mp4"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-t", "2", "-i", str(first),
                    "-loop", "1", "-t", "2", "-i", str(second),
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
    before, _, _ = frame_at(ffmpeg, str(video), 1900, end_ms=2000)
    crossing, _, _ = frame_at(ffmpeg, str(video), 1999, end_ms=2000)
    after, _, _ = frame_at(ffmpeg, str(video), 2000)
    assert before is not None and after is not None
    assert tuple(before[0, 0]) != tuple(after[0, 0])
    assert crossing is None

    def color_text(frame):
        return {"text": "FIRST" if frame[0, 0, 2] > frame[0, 0, 0] else "SECOND", "confidence": 1}

    first_result = extract_ocr_segment_text(video, 0, 2, (0, 0, 1, 1), ocr_runner=color_text)
    second_result = extract_ocr_segment_text(video, 2, 4, (0, 0, 1, 1), ocr_runner=color_text)
    assert first_result["text"] == "FIRST"
    assert second_result["text"] == "SECOND"


def test_stage2_ocr_extracts_multiple_entries_when_subtitles_change():
    def frame_at_time(_path, seconds):
        return Image.new("RGB", (200, 100), color="white")

    def mock_ocr(frame_crop):
        return {"text": "dummy", "confidence": 1.0}

    # Custom runner returning different subtitles based on timestamp simulated through frame_fetcher
    times = []

    def frame_fetcher(_path, seconds):
        times.append(seconds)
        color = 1 if seconds < 72.0 else (2 if seconds < 74.0 else 3)
        img = Image.new("RGB", (200, 100), color=(color, 0, 0))
        return img

    def ocr_runner(frame):
        val = frame[0, 0, 0] if hasattr(frame, "shape") else 1
        if val == 1:
            return {"text": "OCR subtitle line 1", "confidence": 0.95}
        elif val == 2:
            return {"text": "OCR subtitle line 2", "confidence": 0.92}
        else:
            return {"text": "OCR subtitle line 3", "confidence": 0.90}

    result = extract_ocr_segment_text(
        "unused.mp4",
        70.0,
        75.0,
        (0.1, 0.7, 0.8, 0.2),
        frame_fetcher=frame_fetcher,
        ocr_runner=ocr_runner,
    )

    assert result["ok"] is True
    entries = result.get("entries", [])
    assert len(entries) == 3
    assert entries[0]["text"] == "OCR subtitle line 1"
    assert entries[0]["startSec"] == 70.0
    assert entries[0]["endSec"] == 72.0
    assert entries[0]["startTime"] == "00:01:10,000"
    assert entries[0]["endTime"] == "00:01:12,000"

    assert entries[1]["text"] == "OCR subtitle line 2"
    assert entries[1]["startSec"] == 72.0
    assert entries[1]["endSec"] == 74.0
    assert entries[1]["startTime"] == "00:01:12,000"
    assert entries[1]["endTime"] == "00:01:14,000"

    assert entries[2]["text"] == "OCR subtitle line 3"
    assert entries[2]["startSec"] == 74.0
    assert entries[2]["endSec"] == 75.0
    assert entries[2]["startTime"] == "00:01:14,000"
    assert entries[2]["endTime"] == "00:01:15,000"


def test_stage2_ocr_single_entry_when_subtitle_constant():
    def frame_fetcher(_path, seconds):
        return Image.new("RGB", (200, 100), color="white")

    def ocr_runner(_frame):
        return {"text": "Single constant subtitle", "confidence": 0.98}

    result = extract_ocr_segment_text(
        "unused.mp4",
        10.0,
        15.0,
        (0.1, 0.7, 0.8, 0.2),
        frame_fetcher=frame_fetcher,
        ocr_runner=ocr_runner,
    )

    assert result["ok"] is True
    entries = result.get("entries", [])
    assert len(entries) == 1
    assert entries[0]["text"] == "Single constant subtitle"
    assert entries[0]["startSec"] == 10.0
    assert entries[0]["endSec"] == 15.0
    assert entries[0]["startTime"] == "00:00:10,000"
    assert entries[0]["endTime"] == "00:00:15,000"
    assert entries[0]["confidence"] == 0.98


def test_stage2_ocr_empty_returns_empty_entries(monkeypatch):
    import videotrans.ocr as ocr

    class EmptyProvider:
        def recognize(self, image, language):
            return {"text": "", "confidence": 0.0}

    monkeypatch.setattr(ocr, "get_provider", lambda **_kwargs: EmptyProvider())
    result = extract_ocr_segment_text("unused.mp4", 1, 2, (0.1, 0.7, 0.8, 0.2), frame_fetcher=_frame)
    assert result["ok"] is True
    assert result["text"] == ""
    assert result["entries"] == []

