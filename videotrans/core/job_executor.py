"""Execute one background job and persist its lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from videotrans.configure import config as runtime_config
from videotrans.core.job_store import mark_cancelled, mark_done, mark_failed, mark_running
from videotrans.core.proc_registry import set_current_job_id
from videotrans.core.project_store import update_project
from videotrans.task.orchestrator import TaskRequest, TaskStatus


@dataclass(frozen=True)
class JobRunners:
    full: Callable
    asr: Callable
    translation: Callable

    def for_type(self, job_type: str) -> Callable:
        if job_type == "asr":
            return self.asr
        if job_type == "translation":
            return self.translation
        return self.full


def _update_project(project_id: str | None, **fields: Any) -> None:
    if not project_id:
        return
    try:
        update_project(project_id, **fields)
    except Exception:
        pass


def execute_job(job: Any, params: dict[str, Any], runners: JobRunners) -> None:
    """Run and persist a job; registry cleanup remains the manager's responsibility."""
    set_current_job_id(job.id)
    try:
        mark_running(job.id)
        _update_project(job.project_id, status="processing")
        result = runners.for_type(job.job_type)(TaskRequest(params), job.accept, job.token)
        with job._lock:
            if result is None or not hasattr(result, "status"):
                job.status = TaskStatus.FAILED.value
                job.error = "Job runner returned an invalid result"
                job.message = job.error
                mark_failed(job.id, error=job.error)
                _update_project(job.project_id, status="failed")
                return

            job.status = result.status.value
            job.outputs = getattr(result, "outputs", ())
            if getattr(result, "segments", ()):
                job.segments = tuple(result.segments)
            if getattr(result, "asr_duration", None) is not None:
                job.asr_duration = result.asr_duration

            if result.status == TaskStatus.SUCCEEDED:
                job.message = "Processing complete"
                job.progress = 100.0
                mark_done(job.id, message=job.message)
                target_stage = 2 if job.job_type == "asr" else (3 if job.job_type == "translation" else 4)
                _update_project(job.project_id, stage=target_stage, status="completed")
            elif result.status == TaskStatus.CANCELLED:
                job.message = "Processing cancelled"
                mark_cancelled(job.id, message=job.message)
                _update_project(job.project_id, status="paused")
            else:
                job.error = result.failure.message if getattr(result, "failure", None) else "Processing failed"
                job.message = job.error
                mark_failed(job.id, error=job.error)
                _update_project(job.project_id, status="failed")
    except Exception as exc:
        runtime_config.logger.exception("Unhandled exception in job execution %s: %s", job.id, exc, exc_info=True)
        with job._lock:
            job.status = TaskStatus.FAILED.value
            job.error = str(exc) or "Internal job execution error"
            job.message = f"Processing failed: {job.error}"
        try:
            mark_failed(job.id, error=job.error)
        except Exception:
            pass
        _update_project(job.project_id, status="failed")
    finally:
        set_current_job_id(None)
