"""UI-independent orchestration for one noninteractive video task."""

from __future__ import annotations

import shutil
import threading
import traceback
from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping

from videotrans.configure.config import TEMP_DIR, logger
from videotrans.configure.excepts import get_msg_from_except
from videotrans.task.taskcfg import TaskCfgVTT
from videotrans.task.trans_create import TransCreate
from videotrans.util._ffmpeg_misc import format_video


class EventKind(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    LOG = "log"
    PROGRESS = "progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class TaskEvent:
    job_id: str
    kind: EventKind
    stage: str | None = None
    message: str = ""
    progress: float | None = None
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskFailure:
    code: str
    stage: str
    message: str
    cause: str
    retryable: bool = False


@dataclass(frozen=True)
class TaskResult:
    job_id: str
    status: TaskStatus
    output_dir: Path
    outputs: tuple[Path, ...] = ()
    failure: TaskFailure | None = None


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()


@dataclass(frozen=True)
class TaskRequest:
    params: Mapping[str, object]

    def normalize(self) -> dict:
        values = dict(self.params)
        unknown = set(values) - {item.name for item in fields(TaskCfgVTT)}
        if unknown:
            raise ValueError(f"Unsupported task parameters: {', '.join(sorted(unknown))}")

        raw_name = values.get("name")
        if not raw_name:
            raise ValueError("Input file is required")
        source = Path(raw_name).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"Input file does not exist: {source}")

        file_info = format_video(source.as_posix())
        for key in ("name", "dirname", "basename", "noextname", "ext", "uuid"):
            values[key] = getattr(file_info, key)

        target_dir = values.get("target_dir")
        if not target_dir:
            raise ValueError("Output directory is required")
        output = Path(target_dir).expanduser().resolve()
        if output == Path(output.anchor):
            raise ValueError("Output directory cannot be a filesystem root")
        values["target_dir"] = output.as_posix()

        cache = Path(values.get("cache_folder") or Path(TEMP_DIR) / file_info.uuid).expanduser().resolve()
        cache_root = Path(TEMP_DIR).resolve()
        if cache != cache_root and cache_root not in cache.parents:
            raise ValueError("Cache directory must be inside the application temp directory")
        values["cache_folder"] = cache.as_posix()
        return values


EventSink = Callable[[TaskEvent], None]


def run(
    request: TaskRequest,
    event_sink: EventSink | None = None,
    cancellation_token: CancellationToken | None = None,
    *,
    stop_after_stage: str | None = None,
) -> TaskResult:
    """Validate and execute one task, optionally stopping after a completed stage."""
    emit = event_sink or (lambda _event: None)
    token = cancellation_token or CancellationToken()
    stage = "validation"
    job_id = ""
    output_dir = Path(".")
    terminal_emitted = False

    def send(kind: EventKind, message: str = "", *, progress=None, details=None) -> None:
        nonlocal terminal_emitted
        if kind in {EventKind.SUCCEEDED, EventKind.FAILED, EventKind.CANCELLED}:
            if terminal_emitted:
                return
            terminal_emitted = True
        emit(TaskEvent(job_id, kind, stage, message, progress, details or {}))

    try:
        values = request.normalize()
        job_id = str(values["uuid"])
        output_dir = Path(str(values["target_dir"]))
        cache_dir = Path(str(values["cache_folder"]))
        send(EventKind.QUEUED)
        if token.is_cancelled():
            send(EventKind.CANCELLED, "Task cancelled before execution")
            return TaskResult(job_id, TaskStatus.CANCELLED, output_dir)

        if values.pop("clear_cache", False) and cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        values["clear_cache"] = False

        def relay(raw: dict) -> None:
            raw_type = raw.get("type", "logs")
            if raw_type == "set_precent":
                text, _, percent = str(raw.get("text", "")).partition("???")
                send(EventKind.PROGRESS, text, progress=float(percent or 0))
            elif raw_type in {"logs", "subtitle", "replace_subtitle"}:
                send(EventKind.LOG, str(raw.get("text", "")), details={"source_type": raw_type})

        task = TransCreate(
            cfg=TaskCfgVTT(**values),
            event_sink=relay,
            cancellation_token=token,
        )
        send(EventKind.RUNNING)

        stages = [("prepare", True), ("recogn", task.should_recogn),
                  ("diariz", task.should_recogn), ("trans", task.should_trans),
                  ("dubbing", task.should_dubbing), ("align", task.should_dubbing),
                  ("recogn2pass", task.should_recogn2),
                  ("assembling", task.should_hebing), ("task_done", True)]
        valid_stages = {stage_name for stage_name, _enabled in stages}
        if stop_after_stage is not None and stop_after_stage not in valid_stages:
            raise ValueError(f"Unknown stop stage: {stop_after_stage}")
        for stage_name, enabled in stages:
            if not enabled:
                continue
            stage = stage_name
            if token.is_cancelled():
                send(EventKind.CANCELLED, "Task cancelled")
                return TaskResult(job_id, TaskStatus.CANCELLED, output_dir)
            send(EventKind.STAGE_STARTED)
            getattr(task, stage_name)()
            if token.is_cancelled():
                send(EventKind.CANCELLED, "Task cancelled")
                return TaskResult(job_id, TaskStatus.CANCELLED, output_dir)
            send(EventKind.STAGE_COMPLETED)
            if stage_name == stop_after_stage:
                break

        outputs = _collect_outputs(task.cfg)
        send(EventKind.SUCCEEDED, details={"outputs": tuple(map(str, outputs))})
        return TaskResult(job_id, TaskStatus.SUCCEEDED, output_dir, outputs)
    except Exception as exc:
        cause = "".join(traceback.format_exception(exc))
        logger.exception("Task %s failed during %s", job_id, stage, exc_info=True)
        failure = TaskFailure(
            code=f"{stage}_failed",
            stage=stage,
            message=get_msg_from_except(exc) or str(exc),
            cause=cause,
        )
        send(EventKind.FAILED, failure.message, details={"code": failure.code})
        return TaskResult(job_id, TaskStatus.FAILED, output_dir, failure=failure)


def _collect_outputs(cfg: TaskCfgVTT) -> tuple[Path, ...]:
    target_dir = Path(cfg.target_dir)
    candidates = [cfg.targetdir_mp4, cfg.source_sub, cfg.target_sub,
                  cfg.source_wav_output, cfg.target_wav_output,
                  target_dir / f"{cfg.target_language_code}-dubbing.wav",
                  target_dir / f"{cfg.target_language_code}-slowed.mp4",
                  target_dir / f"{cfg.target_language_code}-{cfg.noextname}.wav"]
    if cfg.only_out_mp4:
        candidates.append(target_dir.parent / Path(cfg.targetdir_mp4).name)
    output_dir = Path(cfg.target_dir).resolve()
    found = []
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).resolve()
        is_task_output = output_dir in path.parents or (
            cfg.only_out_mp4 and path.parent == output_dir.parent
        )
        if path.is_file() and is_task_output:
            found.append(path)
    return tuple(dict.fromkeys(found))
