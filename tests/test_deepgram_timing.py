import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import pytest

from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskEvent,
    TaskRequest,
    TaskResult,
    TaskStatus,
)
from webui import JobManager, JobRecord


def test_frontend_files_contain_timing_markers():
    stage1 = Path("frontend/js/screens/Stage1Prepare.js").read_text(encoding="utf-8")
    assert "renderAsrProgressCard" in stage1
    assert "data-asr-progress" in stage1
    assert "elapsedSeconds" in stage1

    stage2 = Path("frontend/js/screens/Stage2ReviewTranscript.js").read_text(encoding="utf-8")
    assert "asrDuration" in stage2
    assert "ASR: ${state.backend.asrDuration}s" in stage2

    footer = Path("frontend/js/components/StatusFooter.js").read_text(encoding="utf-8")
    assert "backend.asrDuration" in footer
    assert "backend.elapsedSeconds" in footer

    app_js = Path("frontend/js/app.js").read_text(encoding="utf-8")
    assert "renderAsrProgressCard" in app_js
    assert "data-asr-progress" in app_js


def test_task_result_has_asr_duration():
    res = TaskResult(
        job_id="test-123",
        status=TaskStatus.SUCCEEDED,
        output_dir=Path("."),
        asr_duration=3.42,
    )
    assert res.asr_duration == 3.42


def test_job_record_accepts_asr_timing_event():
    job = JobRecord(id="job-1", token=CancellationToken())
    assert job.asr_duration is None

    # Emit asr_timing event
    event = TaskEvent(
        job_id="job-1",
        kind=EventKind.LOG,
        stage="recogn",
        message="Deepgram ASR completed in 2.85s",
        details={"source_type": "asr_timing", "duration": 2.85},
    )
    job.accept(event)
    assert job.asr_duration == 2.85

    snap = job.snapshot()
    assert snap["asrDuration"] == 2.85


def test_job_record_accepts_succeeded_event_with_asr_duration():
    job = JobRecord(id="job-2", token=CancellationToken())
    event = TaskEvent(
        job_id="job-2",
        kind=EventKind.SUCCEEDED,
        stage="recogn",
        message="Complete",
        details={"outputs": [], "segments": [], "asr_duration": 4.15},
    )
    job.accept(event)
    assert job.asr_duration == 4.15
    assert job.snapshot()["asrDuration"] == 4.15


def test_job_manager_preserves_asr_duration_on_execute():
    job = JobRecord(id="job-3", token=CancellationToken(), job_type="asr")

    def mock_asr_runner(req, accept, token):
        return TaskResult(
            job_id="job-3",
            status=TaskStatus.SUCCEEDED,
            output_dir=Path("."),
            asr_duration=1.75,
        )

    mgr = JobManager(asr_runner=mock_asr_runner)
    mgr._execute(job, {})
    assert job.status == "succeeded"
    assert job.asr_duration == 1.75
    assert job.snapshot()["asrDuration"] == 1.75


def test_orchestrator_relay_asr_timing():
    from videotrans.task.orchestrator import run

    events = []

    def sink(event):
        events.append(event)

    class DummyTaskCfg:
        uuid = "dummy-uuid"
        target_dir = "/tmp/out"
        cache_folder = "/tmp/cache"
        clear_cache = False
        subtitles = ""
        basename = "test"
        name = "test.mp4"

    with patch("videotrans.task.orchestrator.TaskRequest") as mock_req, \
         patch("videotrans.task.orchestrator.TransCreate") as mock_trans, \
         patch("videotrans.task.orchestrator._embed_thumbnail"), \
         patch("videotrans.task.orchestrator._collect_outputs", return_value=()), \
         patch("videotrans.task.orchestrator.extract_transcript_segments", return_value=[]):

        mock_req_inst = MagicMock()
        mock_req_inst.normalize.return_value = {
            "uuid": "dummy-uuid",
            "target_dir": "/tmp/out",
            "cache_folder": "/tmp/cache",
            "clear_cache": False,
        }

        class MockTask:
            def __init__(self, cfg, event_sink, cancellation_token):
                self.cfg = DummyTaskCfg()
                self.should_recogn = True
                self.event_sink = event_sink
                self.asr_duration = 5.23

            def prepare(self):
                pass

            def recogn(self):
                # simulate Deepgram emitting asr_timing
                self.event_sink({
                    "type": "asr_timing",
                    "text": "Deepgram ASR completed in 3.12s",
                    "duration": 3.12,
                })

            def diariz(self):
                pass

        mock_trans.side_effect = MockTask

        result = run(mock_req_inst, event_sink=sink, stage_limit="asr")
        assert result.status == TaskStatus.SUCCEEDED
        assert result.asr_duration == 3.12

        # Check event sink received asr_duration in succeeded event
        succeeded_events = [e for e in events if e.kind == EventKind.SUCCEEDED]
        assert len(succeeded_events) == 1
        assert succeeded_events[0].details.get("asr_duration") == 3.12


def test_deepgram_emits_asr_timing():
    from videotrans.recognition._deepgram import DeepgramRecogn

    recogn = DeepgramRecogn(
        audio_file="dummy.wav",
        detect_language="en",
        cache_folder="/tmp",
    )
    emitted = []
    recogn.event_sink = lambda msg: emitted.append(msg)

    with patch("videotrans.recognition._deepgram.params", {"deepgram_apikey": "fake-key"}), \
         patch("videotrans.recognition._deepgram.os.path.getsize", return_value=1000), \
         patch("builtins.open", mock_open(read_data=b"fake-audio")), \
         patch("videotrans.recognition._deepgram.DeepgramClient") as mock_client_cls, \
         patch("videotrans.recognition._deepgram.DeepgramConverter") as mock_conv, \
         patch("videotrans.recognition._deepgram.srt", return_value="1\n00:00:00,000 --> 00:00:02,000\nHello world\n"), \
         patch("videotrans.recognition._deepgram.get_subtitle_from_srt", return_value=[{"line": 1, "text": "Hello world"}]):

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_client.listen.rest.v.return_value.transcribe_file.return_value = mock_resp

        res = recogn._exec()
        assert len(res) == 1
        assert res[0]["text"] == "Hello world"

        # Verify asr_timing signal was emitted
        timing_signals = [s for s in emitted if s.get("type") == "asr_timing"]
        assert len(timing_signals) == 1
        assert "duration" in timing_signals[0]
        assert isinstance(timing_signals[0]["duration"], float)
