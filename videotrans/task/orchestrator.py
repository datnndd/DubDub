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
    segments: tuple[dict[str, Any], ...] = ()
    asr_duration: float | None = None


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
    stage_limit: str | None = None,
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

        asr_duration_val: float | None = None

        def relay(raw: dict) -> None:
            nonlocal asr_duration_val
            raw_type = raw.get("type", "logs")
            if raw_type == "set_precent":
                text, _, percent = str(raw.get("text", "")).partition("???")
                send(EventKind.PROGRESS, text, progress=float(percent or 0))
            elif raw_type == "asr_timing":
                dur = raw.get("duration")
                if dur is not None:
                    try:
                        asr_duration_val = float(dur)
                    except (ValueError, TypeError):
                        pass
                send(EventKind.LOG, str(raw.get("text", "")), details={"source_type": raw_type, "duration": asr_duration_val})
            elif raw_type in {"logs", "subtitle", "replace_subtitle"}:
                send(EventKind.LOG, str(raw.get("text", "")), details={"source_type": raw_type})

        task = TransCreate(
            cfg=TaskCfgVTT(**values),
            event_sink=relay,
            cancellation_token=token,
        )
        if task.cfg.subtitles:
            # Stage 4 is authoritative for edited text/timing. Reuse the prepared
            # media/cache and enter the existing dubbing/assembly stages directly.
            task.cfg.clear_cache = False
            Path(task.cfg.source_sub).parent.mkdir(parents=True, exist_ok=True)
            Path(task.cfg.source_sub).write_text(task.cfg.subtitles, encoding="utf-8")
            Path(task.cfg.target_sub).write_text(task.cfg.subtitles, encoding="utf-8")
            from videotrans.util.help_srt import get_subtitle_from_srt
            task.source_srt_list = get_subtitle_from_srt(task.cfg.source_sub, is_file=True) or []
            task.target_srt_list = get_subtitle_from_srt(task.cfg.target_sub, is_file=True) or []
            task.should_recogn = False
            task.should_trans = False
        send(EventKind.RUNNING)

        if stage_limit == "asr":
            stages = [("prepare", True), ("recogn", task.should_recogn),
                      ("diariz", task.should_recogn)]
        else:
            stages = [("prepare", True), ("recogn", task.should_recogn),
                      ("diariz", task.should_recogn), ("trans", task.should_trans),
                      ("dubbing", task.should_dubbing), ("align", task.should_dubbing),
                      ("recogn2pass", task.should_recogn2),
                      ("assembling", task.should_hebing), ("task_done", True)]

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

        _embed_thumbnail(task.cfg)
        outputs = _collect_outputs(task.cfg)
        segments = extract_transcript_segments(task)
        if asr_duration_val is None:
            asr_duration_val = getattr(task, "asr_duration", None)
        send(EventKind.SUCCEEDED, details={"outputs": tuple(map(str, outputs)), "segments": list(segments), "asr_duration": asr_duration_val})
        return TaskResult(job_id, TaskStatus.SUCCEEDED, output_dir, outputs, segments=tuple(segments), asr_duration=asr_duration_val)
    except Exception as exc:
        cause = "".join(traceback.format_exception(exc))
        logger.exception("Task %s failed during %s", job_id, stage, exc_info=True)
        failure = TaskFailure(
            code=f"{stage}_failed",
            stage=stage,
            message=get_msg_from_except(exc) or str(exc),
            cause=cause,
        )
        try:
            send(EventKind.FAILED, failure.message, details={"code": failure.code})
        except Exception:
            logger.exception("Failed to send terminal failure event for task %s", job_id, exc_info=True)
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


def _embed_thumbnail(cfg: TaskCfgVTT) -> None:
    """Attach the selected cover image without re-encoding the rendered streams."""
    thumbnail = Path(cfg.thumbnail).resolve() if cfg.thumbnail else None
    video = Path(cfg.targetdir_mp4).resolve() if cfg.targetdir_mp4 else None
    if not thumbnail or not thumbnail.is_file() or not video or not video.is_file():
        return
    from videotrans.util.help_ffmpeg import runffmpeg
    staged = Path(cfg.cache_folder) / f"thumbnail-{video.name}"
    runffmpeg([
        '-y', '-i', video.as_posix(), '-i', thumbnail.as_posix(),
        '-map', '0', '-map', '1', '-c', 'copy', '-c:v:1', 'mjpeg',
        '-disposition:v:1', 'attached_pic', staged.as_posix(),
    ])
    if staged.is_file():
        staged.replace(video)


def run_staged_asr(
    request: TaskRequest,
    event_sink: EventSink | None = None,
    cancellation_token: CancellationToken | None = None,
) -> TaskResult:
    """Execute audio extraction, speech recognition (ASR), and speaker diarization."""
    return run(request, event_sink, cancellation_token, stage_limit="asr")


def extract_transcript_segments(task: object) -> list[dict[str, Any]]:
    """Extract and normalize recognized dialogue segments from a completed ASR task."""
    import json
    from typing import Any
    from videotrans.util.segment_ops import calculate_cps, format_timestamp, parse_timestamp

    raw_items = getattr(task, "source_srt_list", None) or []
    if not raw_items:
        source_sub = getattr(getattr(task, "cfg", None), "source_sub", None)
        if source_sub and Path(source_sub).is_file():
            try:
                from videotrans.util.help_srt import get_subtitle_from_srt
                raw_items = get_subtitle_from_srt(str(source_sub), is_file=True) or []
            except Exception:
                raw_items = []

    if not raw_items:
        return []

    cache_folder = getattr(getattr(task, "cfg", None), "cache_folder", None)
    target_dir = getattr(getattr(task, "cfg", None), "target_dir", None)
    speaker_list: list[str] = []
    for spk_path in (
        Path(cache_folder) / "speaker.json" if cache_folder else None,
        Path(target_dir) / "speaker.json" if target_dir else None,
    ):
        if spk_path and spk_path.is_file():
            try:
                loaded = json.loads(spk_path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    speaker_list = [str(x) for x in loaded]
                    break
                elif isinstance(loaded, dict):
                    speaker_list = [
                        str(v)
                        for _, v in sorted(
                            loaded.items(),
                            key=lambda p: int(p[0]) if str(p[0]).isdigit() else p[0],
                        )
                    ]
                    break
            except Exception:
                pass

    enable_diariz = getattr(getattr(task, "cfg", None), "enable_diariz", False)

    raw_spk_per_item = []
    for idx, item in enumerate(raw_items):
        item_dict = item if isinstance(item, dict) else dict(item.items()) if hasattr(item, "items") else getattr(item, "__dict__", {})
        spk = item_dict.get("spk") or getattr(item, "spk", None)
        if not spk and idx < len(speaker_list) and speaker_list[idx]:
            spk = speaker_list[idx]
        raw_spk_per_item.append(str(spk) if spk else "")

    distinct_speakers = [s for s in dict.fromkeys(raw_spk_per_item) if s]

    palette = [
        {"id": "spk_1", "name": "Speaker 1", "code": "S1", "color": "amber"},
        {"id": "spk_2", "name": "Speaker 2", "code": "S2", "color": "secondary"},
        {"id": "spk_3", "name": "Speaker 3", "code": "S3", "color": "emerald"},
        {"id": "spk_4", "name": "Speaker 4", "code": "S4", "color": "rose"},
        {"id": "spk_5", "name": "Speaker 5", "code": "S5", "color": "purple"},
    ]

    spk_map: dict[str, dict[str, str]] = {}
    if enable_diariz and len(distinct_speakers) > 1:
        for i, spk_key in enumerate(distinct_speakers):
            if i < len(palette):
                spk_map[spk_key] = palette[i]
            else:
                spk_map[spk_key] = {
                    "id": f"spk_{i+1}",
                    "name": f"Speaker {i+1}",
                    "code": f"S{i+1}",
                    "color": "stone",
                }
    else:
        single = palette[0]
        for spk_key in distinct_speakers:
            spk_map[spk_key] = single

    segments = []
    for idx, item in enumerate(raw_items):
        item_dict = item if isinstance(item, dict) else dict(item.items()) if hasattr(item, "items") else getattr(item, "__dict__", {})
        text = str(item_dict.get("text", getattr(item, "text", ""))).strip()

        start_val = item_dict.get("start_time", getattr(item, "start_time", 0))
        end_val = item_dict.get("end_time", getattr(item, "end_time", 0))

        if isinstance(start_val, (int, float)) and isinstance(end_val, (int, float)) and (start_val > 0 or end_val > 0):
            start_sec = float(start_val) / 1000.0
            end_sec = float(end_val) / 1000.0
        else:
            startraw = item_dict.get("startraw", getattr(item, "startraw", ""))
            endraw = item_dict.get("endraw", getattr(item, "endraw", ""))
            start_sec = parse_timestamp(str(startraw))
            end_sec = parse_timestamp(str(endraw))

        start_time_str = format_timestamp(start_sec)
        end_time_str = format_timestamp(end_sec)
        dur = max(0.1, end_sec - start_sec)
        cps, cps_status = calculate_cps(text, dur)

        raw_spk = raw_spk_per_item[idx] if idx < len(raw_spk_per_item) else ""
        spk_info = spk_map.get(raw_spk) or palette[0]

        segments.append({
            "id": idx + 1,
            "speaker": spk_info["name"],
            "speakerId": spk_info["id"],
            "speakerName": spk_info["name"],
            "speakerLabel": spk_info["name"],
            "speakerColor": spk_info["color"],
            "speakerCode": spk_info["code"],
            "startTime": start_time_str,
            "endTime": end_time_str,
            "startSec": round(start_sec, 3),
            "endSec": round(end_sec, 3),
            "text": text,
            "sourceText": text,
            "targetText": "",
            "cps": cps,
            "cpsStatus": cps_status,
            "hasOcrDiff": False,
        })

    return segments
