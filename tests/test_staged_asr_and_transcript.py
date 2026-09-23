import asyncio
import io
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer
import pytest

from videotrans import recognition
from videotrans.api.app import create_app
from videotrans.api.ocr_helpers import extract_ocr_segment_text
from videotrans.api.task_params import build_task_params
from videotrans.core.job_manager import JobManager
from videotrans.task import orchestrator
from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskEvent,
    TaskRequest,
    TaskResult,
    TaskStatus,
    extract_transcript_segments,
    run_staged_asr,
)
from videotrans.util.segment_ops import (
    calculate_cps,
    format_timestamp,
    parse_timestamp,
    split_segment,
)


# ============================================================================
# 1. Tests for videotrans.util.segment_ops
# ============================================================================

def test_format_timestamp():
    assert format_timestamp(0.0) == "00:00.000"
    assert format_timestamp(1.5) == "00:01.500"
    assert format_timestamp(65.123) == "01:05.123"
    assert format_timestamp(125.008) == "02:05.008"
    assert format_timestamp(3661.25) == "61:01.250"
    assert format_timestamp(-5.0) == "00:00.000"


def test_parse_timestamp():
    assert parse_timestamp("00:00.000") == 0.0
    assert parse_timestamp("01:05.123") == pytest.approx(65.123)
    assert parse_timestamp("01:02:03.456") == pytest.approx(3723.456)
    assert parse_timestamp("invalid") == 0.0


def test_calculate_cps():
    # Empty or zero duration
    cps, status = calculate_cps("", 2.0)
    assert cps == 0.0 and status == "Optimal"
    cps, status = calculate_cps("Test text", 0.0)
    assert cps == 0.0 and status == "Optimal"

    # Normal pace: 10 chars over 2 seconds = 5 cps
    cps, status = calculate_cps("1234567890", 2.0)
    assert cps == 5.0
    assert status == "Optimal"

    # Warning pace: 35 chars over 2 seconds = 17.5 cps (15-18 range)
    cps, status = calculate_cps("1234567890" * 3 + "12345", 2.0)
    assert cps == 17.5
    assert status == "Good"

    # Danger pace: 50 chars over 2 seconds = 25 cps (>18 range)
    cps, status = calculate_cps("1234567890" * 5, 2.0)
    assert cps == 25.0
    assert status == "Fast"


def test_split_segment_with_cursor():
    seg = {
        "id": "seg-10",
        "startSec": 10.0,
        "endSec": 20.0,
        "text": "Hello world wonderful morning",
        "speaker": "spk_0",
        "speakerLabel": "Speaker 1",
        "speakerColor": "sky",
    }
    # Split at 15.0s with cursor between "world" and "wonderful" (index 11)
    seg1, seg2 = split_segment(seg, 15.0, cursor_position=11, next_id="seg-11")

    assert seg1["id"] == "seg-10"
    assert seg1["startSec"] == 10.0
    assert seg1["endSec"] == 15.0
    assert seg1["startTime"] == "00:10.000"
    assert seg1["endTime"] == "00:15.000"
    assert seg1["text"] == "Hello world"
    assert seg1["speaker"] == "spk_0"
    assert seg1["speakerLabel"] == "Speaker 1"

    assert seg2["id"] == "seg-11"
    assert seg2["startSec"] == 15.0
    assert seg2["endSec"] == 20.0
    assert seg2["startTime"] == "00:15.000"
    assert seg2["endTime"] == "00:20.000"
    assert seg2["text"] == "wonderful morning"
    assert seg2["speaker"] == "spk_0"
    assert seg2["speakerLabel"] == "Speaker 1"


def test_split_segment_word_boundary_fallback():
    seg = {
        "id": "seg-1",
        "startSec": 0.0,
        "endSec": 10.0,
        "text": "The quick brown fox jumps over",
        "speaker": "spk_1",
        "speakerLabel": "Speaker 2",
    }
    # Split at 5.0 (50% duration) without cursor
    seg1, seg2 = split_segment(seg, 5.0, cursor_position=None)

    assert seg1["startSec"] == 0.0
    assert seg1["endSec"] == 5.0
    assert seg2["startSec"] == 5.0
    assert seg2["endSec"] == 10.0
    assert seg1["text"] + " " + seg2["text"] == "The quick brown fox jumps over"
    assert seg2["speakerLabel"] == "Speaker 2"


def test_split_segment_validates_bounds():
    seg = {"id": "seg-1", "startSec": 5.0, "endSec": 10.0, "text": "Testing bounds"}

    # Playhead before start
    with pytest.raises(ValueError, match="between startSec"):
        split_segment(seg, 4.0)

    # Playhead after end
    with pytest.raises(ValueError, match="between startSec"):
        split_segment(seg, 11.0)

    # Playhead exactly at bounds
    with pytest.raises(ValueError, match="between startSec"):
        split_segment(seg, 5.0)
    with pytest.raises(ValueError, match="between startSec"):
        split_segment(seg, 10.0)


def test_format_and_parse_timestamp_edge_cases():
    assert format_timestamp(float("nan")) == "00:00.000"
    assert format_timestamp(None) == "00:00.000"
    assert parse_timestamp(None) == 0.0
    assert parse_timestamp(12.34) == 12.34
    assert parse_timestamp(0) == 0.0
    assert parse_timestamp("") == 0.0
    assert parse_timestamp("02:15,750") == 135.75


def test_split_segment_whitespace_and_string_ids():
    seg = {
        "id": "seg-1",
        "startSec": 0.0,
        "endSec": 10.0,
        "sourceText": "   Hello world beautiful day   ",
    }
    s1, s2 = split_segment(seg, 5.0)
    assert s1["id"] == "seg-1"
    assert s2["id"] == "seg-2"
    assert s1["sourceText"] == "Hello world"
    assert s2["sourceText"] == "beautiful day"
    assert s1["text"] == "Hello world"
    assert s2["text"] == "beautiful day"

    # Empty text
    empty_seg = {"id": 1, "startSec": 0.0, "endSec": 4.0, "sourceText": ""}
    e1, e2 = split_segment(empty_seg, 2.0)
    assert e1["sourceText"] == ""
    assert e2["sourceText"] == ""
    assert e2["id"] == 2


# ============================================================================
# 2. Tests for extract_transcript_segments & run_staged_asr
# ============================================================================

def test_extract_transcript_segments_single_speaker(tmp_path):
    srt_file = tmp_path / "source.srt"
    srt_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,500\nHello and welcome to the show.\n\n"
        "2\n00:00:04,000 --> 00:00:07,000\nToday we talk about dubbing.\n\n",
        encoding="utf-8",
    )

    task = MagicMock()
    task.cfg.source_sub = str(srt_file)
    task.cfg.target_dir = str(tmp_path)
    task.cfg.enable_diariz = False
    task.source_srt_list = None

    segments = extract_transcript_segments(task)

    assert len(segments) == 2
    assert segments[0]["id"] in (1, "seg-1")
    assert segments[0]["startSec"] == 1.0
    assert segments[0]["endSec"] == 3.5
    assert segments[0]["startTime"] == "00:01.000"
    assert segments[0]["endTime"] == "00:03.500"
    assert segments[0]["text"] == "Hello and welcome to the show."
    assert segments[0]["speakerLabel"] == "Speaker 1"
    assert segments[0]["speaker"] == "Speaker 1"

    assert segments[1]["id"] in (2, "seg-2")
    assert segments[1]["startSec"] == 4.0
    assert segments[1]["endSec"] == 7.0
    assert segments[1]["startTime"] == "00:04.000"
    assert segments[1]["endTime"] == "00:07.000"
    assert segments[1]["speakerLabel"] == "Speaker 1"


def test_extract_transcript_segments_multi_speaker(tmp_path):
    srt_file = tmp_path / "source.srt"
    srt_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nFirst speaker talking.\n\n"
        "2\n00:00:03,500 --> 00:00:06,000\nSecond speaker answers.\n\n",
        encoding="utf-8",
    )
    speaker_file = tmp_path / "speaker.json"
    speaker_file.write_text(
        json.dumps({
            "1": "spk_0",
            "2": "spk_1",
        }),
        encoding="utf-8",
    )

    task = MagicMock()
    task.cfg.source_sub = str(srt_file)
    task.cfg.target_dir = str(tmp_path)
    task.cfg.enable_diariz = True
    task.source_srt_list = None

    segments = extract_transcript_segments(task)

    assert len(segments) == 2
    assert segments[0]["speakerLabel"] == "Speaker 1"
    assert segments[1]["speakerLabel"] == "Speaker 2"
    assert segments[0]["speakerId"] == "spk_1"
    assert segments[1]["speakerId"] == "spk_2"
    # Distinct colors
    assert segments[0]["speakerColor"] != segments[1]["speakerColor"]


class FakeAsrTask:
    def __init__(self, cfg, event_sink=None, cancellation_token=None):
        self.cfg = cfg
        self.event_sink = event_sink
        self.cancellation_token = cancellation_token
        self.calls = []
        self.should_recogn = True
        self.should_trans = False
        self.should_dubbing = False
        self.should_recogn2 = False
        self.should_hebing = False

        # Set up srt file
        srt_path = Path(cfg.target_dir) / "source.srt"
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        srt_path.write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nRecognized transcript line.\n\n",
            encoding="utf-8",
        )
        self.cfg.source_sub = str(srt_path)
        self.cfg.target_sub = str(Path(cfg.target_dir) / "target.srt")
        self.cfg.source_wav_output = str(Path(cfg.target_dir) / "source.m4a")
        self.cfg.target_wav_output = str(Path(cfg.target_dir) / "target.m4a")
        self.cfg.targetdir_mp4 = str(Path(cfg.target_dir) / "result.mp4")

    def prepare(self):
        self.calls.append("prepare")

    def recogn(self):
        self.calls.append("recogn")

    def diariz(self):
        self.calls.append("diariz")

    def trans(self):
        self.calls.append("trans")

    def dubbing(self):
        self.calls.append("dubbing")

    def task_done(self):
        self.calls.append("task_done")


def test_run_staged_asr_stops_before_translation(tmp_path, monkeypatch):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video")
    output = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()

    instance_holder = []

    def task_factory(cfg, event_sink=None, cancellation_token=None):
        inst = FakeAsrTask(cfg, event_sink, cancellation_token)
        instance_holder.append(inst)
        return inst

    monkeypatch.setattr(orchestrator, "TEMP_DIR", str(temp_dir))
    monkeypatch.setattr(orchestrator, "TransCreate", task_factory)

    req = TaskRequest({
        "name": str(source),
        "target_dir": str(output),
        "cache_folder": str(temp_dir / "job"),
        "source_language_code": "en",
        "target_language_code": "vi",
        "enable_diariz": True,
    })

    result = run_staged_asr(req)

    assert result.status == TaskStatus.SUCCEEDED
    assert len(instance_holder) == 1
    # prepare, recogn, diariz executed; trans and dubbing NOT executed
    assert instance_holder[0].calls == ["prepare", "recogn", "diariz"]
    assert len(result.segments) == 1
    assert result.segments[0]["text"] == "Recognized transcript line."
    assert result.segments[0]["startSec"] == 1.0
    assert result.segments[0]["endSec"] == 4.0


# ============================================================================
# 3. Tests for WebUI Endpoints (/api/jobs with jobType="asr", /api/ocr/extract, /api/segments/split)
# ============================================================================

def test_job_submission_supports_asr_job_type(tmp_path, monkeypatch):
    def fake_probe(_path):
        return {
            "time": 5000,
            "width": 1280,
            "height": 720,
            "video_fps": 30,
            "video_codec_name": "h264",
            "audio_codec_name": "aac",
            "format_name": "mp4",
            "bit_rate": 1000000,
            "audio_sample_rate": 44100,
            "audio_channels": 2,
            "video_streams": 1,
            "streams_audio": 1,
        }

    sample_segments = (
        {
            "id": "seg-1",
            "startSec": 0.5,
            "endSec": 2.5,
            "startTime": "00:00.500",
            "endTime": "00:02.500",
            "text": "Staged recognition segment",
            "speaker": "Speaker 1",
            "speakerLabel": "Speaker 1",
            "speakerColor": "emerald",
            "cps": 13.0,
            "cpsStatus": "normal",
        },
    )

    def fake_asr_runner(_req, sink, _token):
        sink(TaskEvent("task", EventKind.STAGE_STARTED, "prepare", message="Preparing ASR"))
        sink(TaskEvent("task", EventKind.STAGE_STARTED, "recogn", message="Transcribing speech"))
        return TaskResult("task", TaskStatus.SUCCEEDED, tmp_path, (), segments=sample_segments)

    manager = JobManager(asr_runner=fake_asr_runner)
    app = create_app(job_manager=manager, upload_dir=tmp_path / "uploads", media_probe=fake_probe, gpu_initializer=lambda: None)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # 1. Upload media
            form = FormData()
            form.add_field("file", io.BytesIO(b"video bytes"), filename="speech.mp4", content_type="video/mp4")
            res = await client.post("/api/media", data=form)
            assert res.status == 201
            media = await res.json()

            # 2. Submit staged ASR job (no translation or tts params required!)
            payload = {
                "mediaId": media["id"],
                "jobType": "asr",
                "options": {
                    "sourceLanguage": "en",
                    "recognType": recognition.FASTER_WHISPER,
                    "modelName": "large-v3",
                    "speakerDiarization": False,
                },
            }
            res = await client.post("/api/jobs", json=payload)
            assert res.status == 202
            job = await res.json()
            assert job["jobType"] == "asr"

            # 3. Wait for completion
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                res = await client.get(f"/api/jobs/{job['id']}")
                snapshot = await res.json()
                if snapshot["status"] == "succeeded":
                    break
                await asyncio.sleep(0.01)

            assert snapshot["status"] == "succeeded"
            assert snapshot["jobType"] == "asr"
            assert len(snapshot["segments"]) == 1
            assert snapshot["segments"][0]["text"] == "Staged recognition segment"

            # 4. Test GET /api/jobs/{job_id}/segments
            res = await client.get(f"/api/jobs/{job['id']}/segments")
            assert res.status == 200
            data = await res.json()
            assert len(data["segments"]) == 1
            assert data["segments"][0]["text"] == "Staged recognition segment"

            # 5. Test GET /api/jobs/{job_id}/transcript
            res = await client.get(f"/api/jobs/{job['id']}/transcript")
            assert res.status == 200
            data2 = await res.json()
            assert len(data2["segments"]) == 1
        finally:
            await client.close()

    asyncio.run(scenario())


def test_api_segments_split(tmp_path):
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # Valid split
            payload = {
                "segment": {
                    "id": "seg-1",
                    "startSec": 2.0,
                    "endSec": 8.0,
                    "text": "First sentence. Second sentence.",
                    "speaker": "Speaker 1",
                    "speakerLabel": "Speaker 1",
                },
                "splitTime": 5.0,
                "cursorPosition": 15,
            }
            res = await client.post("/api/segments/split", json=payload)
            assert res.status == 200
            data = await res.json()
            assert len(data["segments"]) == 2
            s1, s2 = data["segments"]
            assert s1["startSec"] == 2.0
            assert s1["endSec"] == 5.0
            assert s1["text"] == "First sentence."
            assert s2["startSec"] == 5.0
            assert s2["endSec"] == 8.0
            assert s2["text"] == "Second sentence."

            # Invalid split time out of range
            invalid_payload = {
                "segment": payload["segment"],
                "splitTime": 1.0,
            }
            res = await client.post("/api/segments/split", json=invalid_payload)
            assert res.status == 400

            # Missing fields
            res = await client.post("/api/segments/split", json={})
            assert res.status == 400
        finally:
            await client.close()

    asyncio.run(scenario())


def test_api_ocr_extract_endpoint(tmp_path):
    extracted_calls = []

    def fake_ocr_extractor(media_path, start_sec, end_sec, roi):
        extracted_calls.append({
            "media_path": media_path,
            "start_sec": start_sec,
            "end_sec": end_sec,
            "roi": roi,
        })
        return {
            "text": "Subtitles recognized by PaddleOCR",
            "confidence": 0.95,
            "sampleCount": 3,
        }

    def fake_probe(_path):
        return {
            "time": 10000,
            "width": 1920,
            "height": 1080,
            "video_fps": 30,
            "video_codec_name": "h264",
            "audio_codec_name": "aac",
            "format_name": "mp4",
            "bit_rate": 2000000,
            "audio_sample_rate": 48000,
            "audio_channels": 2,
            "video_streams": 1,
            "streams_audio": 1,
        }

    app = create_app(
        upload_dir=tmp_path / "uploads",
        media_probe=fake_probe,
        ocr_extractor=fake_ocr_extractor,
    )

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # Ingest media
            form = FormData()
            form.add_field("file", io.BytesIO(b"media file content"), filename="test_video.mp4", content_type="video/mp4")
            res = await client.post("/api/media", data=form)
            assert res.status == 201
            media = await res.json()

            # Successful OCR extract request
            payload = {
                "mediaId": media["id"],
                "startSec": 3.0,
                "endSec": 6.5,
                "roi": {
                    "x": 0.1,
                    "y": 0.8,
                    "width": 0.8,
                    "height": 0.15,
                },
            }
            res = await client.post("/api/ocr/extract", json=payload)
            assert res.status == 200
            data = await res.json()
            assert data["text"] == "Subtitles recognized by PaddleOCR"
            assert data["confidence"] == 0.95

            assert len(extracted_calls) == 1
            call = extracted_calls[0]
            assert call["start_sec"] == 3.0
            assert call["end_sec"] == 6.5
            assert call["roi"]["y"] == 0.8

            # Media not found
            bad_media_res = await client.post("/api/ocr/extract", json={**payload, "mediaId": "unknown-id"})
            assert bad_media_res.status == 404

            # Invalid timestamp range (startSec >= endSec)
            bad_time_res = await client.post("/api/ocr/extract", json={**payload, "startSec": 7.0, "endSec": 5.0})
            assert bad_time_res.status == 400

            # Invalid ROI (width <= 0)
            bad_roi_res = await client.post(
                "/api/ocr/extract",
                json={**payload, "roi": {"x": 0, "y": 0, "width": 0, "height": 0.5}},
            )
            assert bad_roi_res.status == 400
        finally:
            await client.close()

    asyncio.run(scenario())


def test_extract_ocr_segment_text_functional(tmp_path, monkeypatch):
    """Test the default extract_ocr_segment_text helper using mocked frames and OCR engine."""
    from PIL import Image

    test_video = tmp_path / "clip.mp4"
    test_video.write_bytes(b"dummy video")

    # Create dummy 200x100 RGB image
    dummy_img = Image.new("RGB", (200, 100), color=(255, 255, 255))

    frame_calls = []
    def fake_frame_at(video_path, timestamp_sec):
        frame_calls.append(timestamp_sec)
        return dummy_img.copy()

    ocr_calls = []
    def fake_run_ocr(cropped_img):
        w = cropped_img.shape[1] if hasattr(cropped_img, "shape") else cropped_img.size[0]
        h = cropped_img.shape[0] if hasattr(cropped_img, "shape") else cropped_img.size[1]
        ocr_calls.append((w, h))
        return [
            {"text": "Extracted line of subtitle", "confidence": 0.92, "box": (10, 10, 80, 30)}
        ]

    result = extract_ocr_segment_text(
        str(test_video),
        start_sec=1.0,
        end_sec=3.0,
        roi={"x": 0.1, "y": 0.7, "width": 0.8, "height": 0.25},
        frame_fetcher=fake_frame_at,
        ocr_runner=fake_run_ocr,
    )

    assert result["text"] == "Extracted line of subtitle"
    assert result["confidence"] >= 0.9
    assert len(frame_calls) >= 1
    # Check cropped image size matches ROI (width=0.8*200=160, height=0.25*100=25)
    assert ocr_calls[0] == (160, 25)


def test_extract_ocr_segment_text_with_ocr_result_object(tmp_path):
    """Ensure extract_ocr_segment_text works with native OcrResult objects (no TypeError)."""
    from videotrans.ocr._types import OcrLine, OcrResult

    test_video = tmp_path / "clip.mp4"
    test_video.write_bytes(b"dummy video")

    dummy_img = MagicMock()
    dummy_img.ndim = 3
    dummy_img.shape = (100, 200, 3)

    def fake_frame_at(video_path, timestamp_sec):
        return dummy_img

    # Return native OcrResult dataclass instance
    def fake_run_ocr(cropped_img):
        return OcrResult(
            text="Recognized via OcrResult object",
            confidence=0.96,
            lines=[OcrLine(text="Recognized via OcrResult object", confidence=0.96)],
            timestamp_ms=1000,
        )

    result = extract_ocr_segment_text(
        str(test_video),
        start_sec=1.0,
        end_sec=2.0,
        roi=(0.1, 0.7, 0.8, 0.25),
        language="zh",
        frame_fetcher=fake_frame_at,
        ocr_runner=fake_run_ocr,
    )

    assert result["ok"] is True
    assert result["text"] == "Recognized via OcrResult object"
    assert result["confidence"] == 0.96
    assert result["samples"] >= 1


def test_ocr_extract_handler_forwards_language(tmp_path):
    """Verify that ocr_extract_handler correctly passes language to ocr_extractor."""
    captured_kwargs = {}

    def fake_ocr_extractor(media_path, start_sec, end_sec, roi, language=None):
        captured_kwargs["language"] = language
        return {"text": "Language verified", "confidence": 0.99, "samples": 1}

    def fake_probe(_path):
        return {"time": 5000, "width": 1920, "height": 1080, "video_fps": 30}

    app = create_app(
        upload_dir=tmp_path / "uploads",
        media_probe=fake_probe,
        ocr_extractor=fake_ocr_extractor,
    )

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = FormData()
            form.add_field("file", io.BytesIO(b"content"), filename="video.mp4", content_type="video/mp4")
            res = await client.post("/api/media", data=form)
            assert res.status == 201
            media = await res.json()

            payload = {
                "mediaId": media["id"],
                "startSec": 1.0,
                "endSec": 3.0,
                "roi": [0.1, 0.7, 0.8, 0.2],
                "language": "zh",
            }
            res = await client.post("/api/ocr/extract", json=payload)
            assert res.status == 200
            data = await res.json()
            assert data["text"] == "Language verified"
            assert captured_kwargs.get("language") == "zh"
        finally:
            await client.close()

    asyncio.run(scenario())


# ============================================================================
# 4. Tests for Frontend Invariants (Stage 1 Start Dub, Stage 2 Workspace)
# ============================================================================

def test_asr_job_params_skip_video_render_preparation(tmp_path, monkeypatch):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()

    params = build_task_params(source, {
        "sourceLanguage": "en",
        "targetLanguage": "vi",
        "recognType": recognition.Deepgram,
        "modelName": "nova-3",
        "timingMode": "video",
        "voiceRole": "should-not-run-in-prepare",
        "backgroundMusicPath": "bgm.mp3",
        "thumbnailPath": "cover.jpg",
    }, job_type="asr", temp_dir=str(temp_dir), output_dir=output_dir)

    assert params["voice_role"] == "No"
    assert params["video_autorate"] is False
    assert params["subtitle_type"] == 0
    assert params["only_out_dubbed_audio"] is True
    assert params["embed_bgm"] is False
    assert params["background_music"] is None
    assert params["thumbnail"] is None


def test_split_segment_period_punctuation_and_cjk():
    """Verify splitting on period punctuation and unbroken CJK text."""
    # Western punctuation without spaces (e.g. period between sentences)
    seg_punct = {
        "id": "seg-1",
        "startSec": 0.0,
        "endSec": 10.0,
        "text": "First sentence.Second sentence.",
    }
    s1, s2 = split_segment(seg_punct, 5.0)
    assert s1["text"] == "First sentence."
    assert s2["text"] == "Second sentence."
    assert s1["startSec"] == 0.0
    assert s1["endSec"] == 5.0
    assert s2["startSec"] == 5.0
    assert s2["endSec"] == 10.0

    # Unbroken Chinese text without spaces or punctuation
    cjk_seg = {
        "id": "seg-cjk",
        "startSec": 0.0,
        "endSec": 6.0,
        "text": "这是一个长句子测试视频字幕",
    }
    c1, c2 = split_segment(cjk_seg, 3.0)
    assert len(c1["text"]) > 0
    assert len(c2["text"]) > 0
    assert c1["text"] + c2["text"] == "这是一个长句子测试视频字幕"
    assert c1["startSec"] == 0.0
    assert c1["endSec"] == 3.0
    assert c2["startSec"] == 3.0
    assert c2["endSec"] == 6.0


def test_format_and_parse_infinite_and_overflow_timestamps():
    """Ensure infinite/overflow timestamps fail-safe to 00:00.000 rather than throwing OverflowError."""
    assert format_timestamp(float("inf")) == "00:00.000"
    assert format_timestamp(float("-inf")) == "00:00.000"
    assert parse_timestamp(float("inf")) == 0.0
    assert parse_timestamp(float("-inf")) == 0.0


def test_api_segments_split_with_custom_next_id(tmp_path):
    """Ensure POST /api/segments/split honors nextId in payload."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            payload = {
                "segment": {
                    "id": "seg-original",
                    "startSec": 1.0,
                    "endSec": 5.0,
                    "text": "Alpha Bravo Charlie Delta",
                },
                "splitTime": 3.0,
                "nextId": "seg-custom-99",
            }
            res = await client.post("/api/segments/split", json=payload)
            assert res.status == 200
            data = await res.json()
            assert len(data["segments"]) == 2
            s1, s2 = data["segments"]
            assert s1["id"] == "seg-original"
            assert s2["id"] == "seg-custom-99"
            assert s1["startSec"] == 1.0
            assert s1["endSec"] == 3.0
            assert s2["startSec"] == 3.0
            assert s2["endSec"] == 5.0
        finally:
            await client.close()

    asyncio.run(scenario())

