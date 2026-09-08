"""Behavioral regressions at the OCR crop and API boundaries (offline)."""
import json
import subprocess
import sys
import threading

import pytest

from engines.hardsub_ocr.main import _crop_from
from services import hardsub_ocr as hso


@pytest.mark.parametrize("bottom", [0.3, 1.0])
def test_crop_preserves_zero_top(bottom):
    rect = {"left": 0, "top": 0, "right": 1, "bottom": bottom}
    assert _crop_from({"crop": rect}) == rect


@pytest.fixture
def route_job(monkeypatch, tmp_path):
    from api.routers import dub_core
    from core.tasks import task_manager

    (tmp_path / "original.mkv").write_bytes(b"fixture")
    job = {"duration": 2.0, "segments": [{"id": 0, "start": 0, "end": 1, "text": "existing"}]}
    monkeypatch.setattr(dub_core, "_get_job", lambda _: job)
    monkeypatch.setattr(dub_core, "_safe_job_dir", lambda _: str(tmp_path))
    monkeypatch.setattr(dub_core, "_save_job", lambda _, value: job.update(value))
    queued = []

    async def add_task(task_id, task_type, generator):
        queued.append(generator)

    monkeypatch.setattr(task_manager, "add_task", add_task)
    return dub_core, job, queued, tmp_path


@pytest.mark.asyncio
async def test_soft_route_extracts_subtitle_ordinal_not_global_stream_index(route_job, monkeypatch):
    from schemas.requests import HardsubExtractRequest

    router, job, _, _ = route_job
    monkeypatch.setattr(hso, "detect_soft_subtitles", lambda _: [{"index": 2}, {"index": 4}])
    selected = []

    def extract(path, index):
        selected.append(index)
        return "1\n00:00:00,000 --> 00:00:01,000\nselected\n"

    monkeypatch.setattr(hso, "extract_soft_subtitle", extract)
    result = await router.dub_hardsub_extract("fixture", HardsubExtractRequest(mode="soft", soft_index=1))
    assert selected == [1]  # ffmpeg -map 0:s:1 is the second subtitle stream
    assert result["segments"][0]["text"] == "selected"


@pytest.mark.asyncio
async def test_ocr_outside_duration_preserves_existing_transcript(route_job, monkeypatch):
    from schemas.requests import HardsubExtractRequest

    router, job, queued, folder = route_job
    before = list(job["segments"])
    monkeypatch.setattr(hso, "run_ocr_client", lambda *a, **kw: [{"start": 3, "end": 4, "text": "outside"}])
    await router.dub_hardsub_extract("fixture", HardsubExtractRequest(mode="ocr"))
    events = [json.loads(event.removeprefix("data: ")) async for event in queued[0]()]
    assert events[-1]["type"] == "error"
    assert job["segments"] == before
    assert not (folder / "hardsub.srt").exists()


@pytest.mark.asyncio
async def test_srt_artifact_matches_clamped_transcript(route_job, monkeypatch):
    from schemas.requests import HardsubExtractRequest
    from services.srt_parser import parse_srt

    router, job, queued, folder = route_job
    monkeypatch.setattr(hso, "run_ocr_client", lambda *a, **kw: [{"start": 1, "end": 3, "text": "visible"}])
    await router.dub_hardsub_extract("fixture", HardsubExtractRequest(mode="ocr"))
    events = [event async for event in queued[0]()]
    assert "hardsub_done" in events[-1]
    saved = parse_srt((folder / "hardsub.srt").read_text(encoding="utf-8-sig"))
    assert saved.segments[0]["end"] == job["segments"][0]["end"] == 2.0


@pytest.mark.asyncio
async def test_cancelled_ocr_does_not_replace_transcript(route_job, monkeypatch):
    from core.tasks import task_manager
    from schemas.requests import HardsubExtractRequest

    router, job, queued, folder = route_job
    before = list(job["segments"])
    cancelled = False

    def extract(*args, **kwargs):
        nonlocal cancelled
        cancelled = True
        return [{"start": 0, "end": 1, "text": "unwanted"}]

    monkeypatch.setattr(task_manager, "is_cancelled", lambda _: cancelled)
    monkeypatch.setattr(hso, "run_ocr_client", extract)
    await router.dub_hardsub_extract("fixture", HardsubExtractRequest(mode="ocr"))
    events = [json.loads(event.removeprefix("data: ")) async for event in queued[0]()]
    assert events[-1]["type"] == "cancelled"
    assert job["segments"] == before
    assert not (folder / "hardsub.srt").exists()


def test_client_cancellation_terminates_sidecar(monkeypatch, tmp_path):
    from engines.hardsub_ocr import bootstrap

    script = tmp_path / "waiting_sidecar.py"
    child_pid_path = tmp_path / "child.pid"
    script.write_text(
        'import sys, struct, time, subprocess\n'
        'from pathlib import Path\n'
        'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])\n'
        'Path(__file__).with_name("child.pid").write_text(str(child.pid))\n'
        'body = b\'{"op":"ready"}\'\n'
        'sys.stdout.buffer.write(struct.pack("!I", len(body)) + body)\n'
        'sys.stdout.buffer.flush()\n'
        'time.sleep(30)\n', encoding="utf-8",
    )
    monkeypatch.setattr(bootstrap, "resolve_hardsub_ocr_venv", lambda: sys.executable)
    monkeypatch.setattr(bootstrap, "HARDSUB_OCR_SIDECAR_SCRIPT", script)
    processes = []
    popen = subprocess.Popen

    def track(*args, **kwargs):
        proc = popen(*args, **kwargs)
        processes.append(proc)
        return proc

    monkeypatch.setattr(hso.subprocess, "Popen", track)
    cancel = threading.Event()
    timer = threading.Timer(1, cancel.set)
    timer.start()
    try:
        with pytest.raises(RuntimeError, match="cancelled"):
            hso.run_ocr_client("unused.mp4", cancelled=cancel.is_set)
        import psutil
        assert child_pid_path.exists()
        assert not psutil.pid_exists(int(child_pid_path.read_text()))
    finally:
        timer.cancel()
        for proc in processes:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
    assert processes and processes[0].poll() is not None
