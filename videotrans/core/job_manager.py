# -*- coding: utf-8 -*-
"""Background job lifecycle, execution management, and status subscribers."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from videotrans.configure import config as runtime_config
from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskEvent,
    TaskRequest,
    TaskStatus,
    run,
    run_staged_asr,
    run_staged_translation,
)
from videotrans.core.job_store import (
    create_job as db_create_job,
    get_job as db_get_job,
    list_jobs as db_list_jobs,
    update_job as db_update_job,
    mark_running as db_mark_running,
    mark_done as db_mark_done,
    mark_failed as db_mark_failed,
    mark_cancelled as db_mark_cancelled,
    append_event,
)
from videotrans.core.project_store import update_project
from videotrans.core.proc_registry import (
    kill_job_procs,
    set_current_job_id,
)


class ActiveJobError(RuntimeError):
    """Raised when the same ingested media already has an active job."""


@dataclass
class JobRecord:
    id: str
    token: CancellationToken
    status: str = "queued"
    stage: str | None = None
    progress: float | None = None
    message: str = "Queued"
    events: list[dict[str, Any]] = field(default_factory=list)
    outputs: tuple[Path, ...] = ()
    segments: tuple[dict[str, Any], ...] = ()
    asr_duration: float | None = None
    error: str | None = None
    media_id: str | None = None
    job_type: str = "full"
    project_id: str | None = None
    _subscribers: list[tuple[Any, Any]] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def subscribe(self, queue: Any, loop: Any) -> None:
        with self._lock:
            self._subscribers.append((queue, loop))

    def unsubscribe(self, queue: Any) -> None:
        with self._lock:
            self._subscribers = [sub for sub in self._subscribers if sub[0] is not queue]

    def accept(self, event: TaskEvent) -> None:
        item = {
            "kind": event.kind.value,
            "stage": event.stage,
            "message": event.message,
            "progress": event.progress,
            "details": dict(event.details),
        }
        with self._lock:
            self.events.append(item)
            self.events[:] = self.events[-200:]
            self.stage = event.stage
            if event.progress is not None:
                self.progress = event.progress
            if event.message:
                self.message = event.message
            if event.kind in {EventKind.RUNNING, EventKind.STAGE_STARTED}:
                self.status = "running"
            elif event.kind == EventKind.FAILED:
                self.status = "failed"
                self.error = event.message or "Processing failed"
            elif event.kind == EventKind.CANCELLED:
                self.status = "cancelled"
                self.message = event.message or "Processing cancelled"
            elif event.kind == EventKind.SUCCEEDED:
                self.status = "succeeded"
                self.progress = 100.0
            if event.details:
                if event.details.get("source_type") == "asr_timing" and "duration" in event.details:
                    try:
                        self.asr_duration = float(event.details["duration"])
                    except (ValueError, TypeError):
                        pass
                elif "asr_duration" in event.details and event.details.get("asr_duration") is not None:
                    try:
                        self.asr_duration = float(event.details["asr_duration"])
                    except (ValueError, TypeError):
                        pass
                if "segments" in event.details:
                    raw_segs = event.details["segments"]
                    if isinstance(raw_segs, (list, tuple)):
                        self.segments = tuple(raw_segs)

            payload = {
                "kind": event.kind.value,
                "stage": self.stage,
                "message": self.message,
                "progress": self.progress,
                "status": self.status,
                "error": self.error,
                "details": dict(event.details),
            }
            try:
                seq = append_event(self.id, payload)
                db_update_job(
                    self.id,
                    status=self.status,
                    stage=self.stage,
                    progress=self.progress,
                    message=self.message,
                    error=self.error,
                )
            except Exception:
                seq = len(self.events)

            subs = list(self._subscribers)

        for q, loop in subs:
            try:
                loop.call_soon_threadsafe(q.put_nowait, (seq, payload))
            except Exception:
                pass

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "jobType": self.job_type,
                "projectId": self.project_id,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
                "events": list(self.events),
                "error": self.error,
                "outputs": [
                    {"name": path.name, "url": f"/api/jobs/{self.id}/outputs/{index}"}
                    for index, path in enumerate(self.outputs)
                ],
                "segments": list(self.segments),
                "asrDuration": self.asr_duration,
            }


class JobManager:
    def __init__(
        self,
        runner: Callable = run,
        asr_runner: Callable | None = None,
        translation_runner: Callable | None = None,
    ) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._active_by_media: dict[str, str] = {}
        self._lock = threading.Lock()
        self._runner = runner
        self._asr_runner = asr_runner or run_staged_asr
        self._translation_runner = translation_runner or run_staged_translation

    def submit(
        self,
        params: dict[str, Any],
        *,
        media_id: str,
        job_type: str = "full",
        project_id: str | None = None,
    ) -> JobRecord:
        with self._lock:
            active_id = self._active_by_media.get(media_id)
            if active_id:
                raise ActiveJobError(f"Media already running in job {active_id}")
            job = JobRecord(
                uuid.uuid4().hex,
                CancellationToken(),
                media_id=media_id,
                job_type=job_type,
                project_id=project_id,
            )
            self._jobs[job.id] = job
            self._active_by_media[media_id] = job.id
            try:
                db_create_job(
                    job.id,
                    type=job_type,
                    project_id=project_id,
                    meta={"media_id": media_id},
                )
            except Exception as e:
                runtime_config.logger.warning("Failed to create job in db: %s", e)
        threading.Thread(target=self._execute, args=(job, params), daemon=True).start()
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is not None:
            return record
        try:
            db_job = db_get_job(job_id)
            if db_job:
                rec = JobRecord(
                    id=db_job["id"],
                    token=CancellationToken(),
                    status=db_job.get("status", "failed"),
                    stage=db_job.get("stage"),
                    progress=db_job.get("progress"),
                    message=db_job.get("message", ""),
                    error=db_job.get("error"),
                    project_id=db_job.get("project_id"),
                    job_type=db_job.get("type", "full"),
                )
                return rec
        except Exception:
            pass
        return None

    def cancel(self, job_id: str) -> JobRecord | None:
        kill_job_procs(job_id)
        try:
            db_mark_cancelled(job_id)
        except Exception:
            pass
        job = self.get(job_id)
        if job:
            job.token.cancel()
            with job._lock:
                if job.status not in {"succeeded", "failed", "cancelled"}:
                    job.status = "cancelled"
                    job.message = "Processing cancelled"
                    payload = {
                        "kind": "cancelled",
                        "status": "cancelled",
                        "message": "Processing cancelled",
                        "progress": job.progress,
                    }
                    try:
                        seq = append_event(job.id, payload)
                    except Exception:
                        seq = 0
                    subs = list(job._subscribers)
                else:
                    subs = []
            for q, loop in subs:
                try:
                    loop.call_soon_threadsafe(q.put_nowait, (seq, payload))
                except Exception:
                    pass
            if job.project_id:
                try:
                    update_project(job.project_id, status="paused")
                except Exception:
                    pass
        return job

    def _execute(self, job: JobRecord, params: dict[str, Any]) -> None:
        set_current_job_id(job.id)
        try:
            db_mark_running(job.id)
            if job.project_id:
                try:
                    update_project(job.project_id, status="processing")
                except Exception:
                    pass
            if job.job_type == "asr":
                runner = self._asr_runner
            elif job.job_type == "translation":
                runner = self._translation_runner
            else:
                runner = self._runner
            result = runner(TaskRequest(params), job.accept, job.token)
            with job._lock:
                if result is not None and hasattr(result, "status"):
                    job.status = result.status.value
                    job.outputs = getattr(result, "outputs", ())
                    if getattr(result, "segments", ()):
                        job.segments = tuple(result.segments)
                    if getattr(result, "asr_duration", None) is not None:
                        job.asr_duration = result.asr_duration
                    if result.status == TaskStatus.SUCCEEDED:
                        job.message = "Processing complete"
                        job.progress = 100.0
                        db_mark_done(job.id, message=job.message)
                        if job.project_id:
                            target_stage = 2 if job.job_type == "asr" else (3 if job.job_type == "translation" else 4)
                            update_project(job.project_id, stage=target_stage, status="completed")
                    elif result.status == TaskStatus.CANCELLED:
                        job.message = "Processing cancelled"
                        db_mark_cancelled(job.id, message=job.message)
                        if job.project_id:
                            update_project(job.project_id, status="paused")
                    else:
                        job.error = result.failure.message if getattr(result, "failure", None) else "Processing failed"
                        job.message = job.error
                        db_mark_failed(job.id, error=job.error)
                        if job.project_id:
                            update_project(job.project_id, status="failed")
                else:
                    job.status = TaskStatus.FAILED.value
                    job.error = "Job runner returned an invalid result"
                    job.message = job.error
                    db_mark_failed(job.id, error=job.error)
                    if job.project_id:
                        update_project(job.project_id, status="failed")
        except Exception as exc:
            runtime_config.logger.exception("Unhandled exception in job execution %s: %s", job.id, exc, exc_info=True)
            with job._lock:
                job.status = TaskStatus.FAILED.value
                job.error = str(exc) or "Internal job execution error"
                job.message = f"Processing failed: {job.error}"
            db_mark_failed(job.id, error=job.error)
            if job.project_id:
                update_project(job.project_id, status="failed")
        finally:
            set_current_job_id(None)
            with self._lock:
                if self._active_by_media.get(job.media_id) == job.id:
                    self._active_by_media.pop(job.media_id, None)


def run_prepare_review(
    request: TaskRequest,
    event_sink: Callable[[TaskEvent], None] | None = None,
    cancellation_token: CancellationToken | None = None,
):
    """Run only the stages needed to produce a transcript for Review Transcript."""
    import sys
    runner = getattr(sys.modules.get("webui"), "run", run) if "webui" in sys.modules else run
    return runner(
        request,
        event_sink,
        cancellation_token,
        stop_after_stage="diariz",
    )



JOBS = JobManager(runner=run_prepare_review, translation_runner=run_staged_translation)
