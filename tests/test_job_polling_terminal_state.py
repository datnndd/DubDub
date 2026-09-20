import time
import pytest
from videotrans.task.orchestrator import TaskEvent, EventKind, TaskStatus
import webui


def test_job_manager_unhandled_runner_exception_transitions_to_failed():
    """If runner raises an unhandled exception, job.status must become 'failed'."""
    def broken_runner(*args, **kwargs):
        raise RuntimeError("Unexpected failure in ASR runner")

    manager = webui.JobManager(runner=broken_runner, asr_runner=broken_runner)
    job = manager.submit({"name": "test_video"}, media_id="media_1", job_type="asr")

    deadline = time.time() + 2
    while job.snapshot()["status"] not in {"succeeded", "failed", "cancelled"} and time.time() < deadline:
        time.sleep(0.01)

    snapshot = job.snapshot()
    # BUG: currently stays "queued" or "running" because _execute has no except block!
    assert snapshot["status"] == "failed"
    assert "Unexpected failure in ASR runner" in (snapshot["error"] or "")


def test_job_record_accept_terminal_events_updates_status():
    """JobRecord.accept must update status on terminal events (FAILED, CANCELLED, SUCCEEDED)."""
    job = webui.JobRecord("job_1", webui.CancellationToken())
    assert job.status == "queued"

    job.accept(TaskEvent("job_1", EventKind.RUNNING, "prepare"))
    assert job.status == "running"

    job.accept(TaskEvent("job_1", EventKind.FAILED, "prepare", message="ASR failed completely"))
    assert job.status == "failed"
    assert job.error == "ASR failed completely"


def test_job_manager_cancel_transitions_status_to_cancelled():
    """JobManager.cancel must transition the job to 'cancelled' so polling stops."""
    manager = webui.JobManager()
    job = webui.JobRecord("job_cancel", webui.CancellationToken())
    manager._jobs[job.id] = job

    manager.cancel("job_cancel")
    assert job.token.is_cancelled()
    assert job.status == "cancelled"
