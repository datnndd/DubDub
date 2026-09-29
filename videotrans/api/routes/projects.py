import os
import shutil
import struct
import subprocess
import sys
import wave
import zipfile
from pathlib import Path
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from videotrans.core.project_store import (
    create_project,
    get_project,
    get_project_dir,
    list_projects,
    update_project,
    update_project_state,
    delete_project,
    find_project_by_audio_hash,
)
from videotrans.core.content_hash import compute_content_hash
from videotrans.core.media_store import MEDIA

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = "Untitled Project"
    mediaId: Optional[str] = Field(None, alias="media_id")
    mediaPath: Optional[str] = Field(None, alias="media_path")
    duration: Optional[float] = 0.0
    stage: Optional[int] = 1
    status: Optional[str] = "pending"
    state: Optional[dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    mediaId: Optional[str] = Field(None, alias="media_id")
    mediaPath: Optional[str] = Field(None, alias="media_path")
    duration: Optional[float] = None
    stage: Optional[int] = None
    status: Optional[str] = None
    state: Optional[dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


@router.get("/api/projects")
async def list_projects_handler(limit: int = Query(100)) -> JSONResponse:
    projects = list_projects(limit=limit)
    return JSONResponse({"projects": projects})


@router.post("/api/projects", status_code=201)
async def create_project_handler(
    payload: ProjectCreateRequest,
    request: Request,
) -> JSONResponse:
    media_id = str(payload.mediaId or "") or None
    name = str(payload.name or "Untitled Project").strip() or "Untitled Project"
    media_store = getattr(request.app.state, "media_store", None) or MEDIA
    media = media_store.get(media_id) if media_id else None
    media_path = str(media.path) if media else (str(payload.mediaPath or "") or None)

    duration = 0.0
    if media and media.info.get("time"):
        try:
            duration = float(media.info["time"]) / 1000.0
        except (ValueError, TypeError):
            pass
    elif payload.duration is not None:
        try:
            duration = float(payload.duration)
        except (ValueError, TypeError):
            pass

    audio_hash = ""
    if media and media.path.is_file():
        try:
            audio_hash = compute_content_hash(media.path)
        except Exception:
            pass

    stage = 1
    if payload.stage is not None:
        try:
            stage = int(payload.stage)
        except (ValueError, TypeError):
            pass

    status = str(payload.status or "pending")
    state = payload.state if isinstance(payload.state, dict) else {}

    if audio_hash and not state.get("segments"):
        cached_proj = find_project_by_audio_hash(audio_hash)
        if cached_proj and cached_proj.get("state", {}).get("segments"):
            state["segments"] = cached_proj["state"]["segments"]
            if cached_proj.get("stage", 1) > stage:
                stage = cached_proj["stage"]

    project = create_project(
        project_id=str(payload.id or "") or None,
        name=name,
        media_id=media_id,
        media_path=media_path,
        duration=duration,
        stage=stage,
        status=status,
        audio_hash=audio_hash,
        state=state,
    )

    return JSONResponse(project, status_code=201)


@router.get("/api/projects/{project_id}")
async def get_project_handler(project_id: str) -> JSONResponse:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return JSONResponse(project)


@router.put("/api/projects/{project_id}")
@router.put("/api/projects/{project_id}/state")
@router.post("/api/projects/{project_id}/state")
async def update_project_handler(
    project_id: str,
    payload: ProjectUpdateRequest,
    request: Request,
) -> JSONResponse:
    kwargs: dict[str, Any] = {}
    if payload.state is not None and isinstance(payload.state, dict):
        kwargs["state"] = payload.state
    if payload.stage is not None:
        try:
            kwargs["stage"] = int(payload.stage)
        except (ValueError, TypeError):
            pass
    if payload.status is not None:
        kwargs["status"] = str(payload.status)
    if payload.name is not None:
        kwargs["name"] = str(payload.name)
    if payload.duration is not None:
        try:
            kwargs["duration"] = float(payload.duration)
        except (ValueError, TypeError):
            pass

    media_store = getattr(request.app.state, "media_store", None) or MEDIA
    media_id = str(payload.mediaId or "") or None
    if not media_id and isinstance(payload.state, dict):
        media_id = str(payload.state.get("backend", {}).get("mediaId") or "") or None

    if media_id:
        kwargs["media_id"] = media_id
        media = media_store.get(media_id)
        if media:
            kwargs["media_path"] = str(media.path)
            if payload.duration is None and media.info.get("time"):
                try:
                    kwargs["duration"] = float(media.info["time"]) / 1000.0
                except (ValueError, TypeError):
                    pass
    elif payload.mediaPath:
        kwargs["media_path"] = str(payload.mediaPath)

    if payload.state is not None and isinstance(payload.state, dict):
        project = update_project_state(
            project_id,
            state_dict=payload.state,
            stage=kwargs.get("stage"),
            status=kwargs.get("status"),
        )
        extra_keys = ("name", "duration", "media_id", "media_path")
        if project and any(k in kwargs for k in extra_keys):
            extra = {k: kwargs[k] for k in extra_keys if k in kwargs}
            project = update_project(project_id, **extra)
    else:
        project = update_project(project_id, **kwargs)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return JSONResponse(project)


class BulkDeleteProjectsRequest(BaseModel):
    ids: list[str]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


@router.post("/api/projects/bulk-delete")
@router.delete("/api/projects/bulk-delete")
async def bulk_delete_projects_handler(payload: BulkDeleteProjectsRequest) -> JSONResponse:
    raw_ids = payload.ids or []
    deleted_ids = []
    for pid in raw_ids:
        if delete_project(str(pid), delete_files=True):
            deleted_ids.append(str(pid))
    return JSONResponse({"ok": True, "deleted": deleted_ids, "count": len(deleted_ids)})


@router.delete("/api/projects/{project_id}")
async def delete_project_handler(project_id: str) -> JSONResponse:
    deleted = delete_project(project_id, delete_files=True)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return JSONResponse({"ok": True, "id": project_id})


@router.post("/api/projects/{project_id}/resume")
async def resume_project_handler(project_id: str) -> JSONResponse:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return JSONResponse({"ok": True, "project": project})


def _format_srt_time(sec: float) -> str:
    total_ms = max(0, int(round(float(sec) * 1000)))
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    s = total_sec % 60
    total_min = total_sec // 60
    m = total_min % 60
    h = total_min // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_srt(segments: list[dict], field: str = "targetText") -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        if not isinstance(seg, dict):
            continue
        text = str(seg.get(field) or (seg.get("sourceText") if field == "targetText" else seg.get("targetText")) or "").strip()
        start = _format_srt_time(float(seg.get("startSec", 0)))
        end = _format_srt_time(float(seg.get("endSec", float(seg.get("startSec", 0)) + 1.0)))
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines).strip() + "\n"


def _create_fallback_wav(path: Path, duration_sec: float = 1.0) -> None:
    sample_rate = 44100
    num_frames = int(max(0.5, float(duration_sec)) * sample_rate)
    with wave.open(str(path), 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        data = struct.pack(f"<{num_frames}h", *([0] * num_frames))
        wav_file.writeframes(data)


def _prepare_capcut_assets(project_id: str, request: Request | None = None) -> dict[str, Path]:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    proj_dir = get_project_dir(project_id)
    exports_dir = proj_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    state = project.get("state") or {}
    segments = state.get("segments") or []

    # 1. subtitles_edited.srt
    edited_srt_path = exports_dir / "subtitles_edited.srt"
    edited_content = _build_srt(segments, field="targetText")
    edited_srt_path.write_text(edited_content, encoding="utf-8")

    # 2. subtitles_target.srt
    target_srt_path = exports_dir / "subtitles_target.srt"
    target_content = _build_srt(segments, field="rawTranslation" if any("rawTranslation" in s for s in segments) else "targetText")
    target_srt_path.write_text(target_content, encoding="utf-8")

    # 3. video.mp4
    video_path = exports_dir / "video.mp4"
    src_media_path = None
    media_id = project.get("media_id")
    app_state = getattr(getattr(request, "app", None), "state", None)
    store = getattr(app_state, "media_store", None) or MEDIA
    if media_id:
        rec = store.get(media_id)
        if rec and rec.path.is_file():
            src_media_path = rec.path
    if not src_media_path and project.get("media_path"):
        cand = Path(project["media_path"])
        if cand.is_file():
            src_media_path = cand

    if src_media_path and src_media_path.is_file():
        if src_media_path.resolve() != video_path.resolve():
            try:
                shutil.copy2(src_media_path, video_path)
            except Exception:
                video_path = src_media_path
    elif not video_path.is_file():
        video_path.touch(exist_ok=True)

    # 4. voiceover_merged.wav
    voiceover_path = exports_dir / "voiceover_merged.wav"
    found_audio = None
    dubbing_dir = proj_dir / "dubbing"
    for cand_name in ["voiceover_merged.wav", "target.wav", "lastend.wav", "dubbed.wav"]:
        cand = exports_dir / cand_name
        if cand.is_file() and cand.stat().st_size > 0:
            found_audio = cand
            break
        cand_dub = dubbing_dir / cand_name
        if cand_dub.is_file() and cand_dub.stat().st_size > 0:
            found_audio = cand_dub
            break

    if found_audio and found_audio.is_file() and found_audio.resolve() != voiceover_path.resolve():
        try:
            shutil.copy2(found_audio, voiceover_path)
        except Exception:
            voiceover_path = found_audio
    elif not voiceover_path.is_file() or voiceover_path.stat().st_size == 0:
        _create_fallback_wav(voiceover_path, duration_sec=float(project.get("duration") or 1.0))

    # 5. bundle.zip
    zip_path = exports_dir / f"capcut_export_{project_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(edited_srt_path, "subtitles_edited.srt")
        zf.write(target_srt_path, "subtitles_target.srt")
        zf.write(video_path, "video.mp4")
        zf.write(voiceover_path, "voiceover_merged.wav")

    return {
        "subtitles_edited.srt": edited_srt_path,
        "subtitles_target.srt": target_srt_path,
        "video.mp4": video_path,
        "voiceover_merged.wav": voiceover_path,
        "bundle.zip": zip_path,
    }


@router.get("/api/projects/{project_id}/export-capcut/{asset_name}")
async def get_capcut_asset_handler(project_id: str, asset_name: str, request: Request):
    assets = _prepare_capcut_assets(project_id, request)
    clean_name = asset_name.lower().strip()
    if clean_name in {"subtitles_edited.srt", "edited.srt"}:
        target = assets["subtitles_edited.srt"]
        media_type = "text/plain; charset=utf-8"
        download_name = "subtitles_edited.srt"
    elif clean_name in {"subtitles_target.srt", "target.srt"}:
        target = assets["subtitles_target.srt"]
        media_type = "text/plain; charset=utf-8"
        download_name = "subtitles_target.srt"
    elif clean_name in {"video.mp4", "video"}:
        target = assets["video.mp4"]
        media_type = "video/mp4"
        download_name = "video.mp4"
    elif clean_name in {"voiceover_merged.wav", "audio.wav", "audio"}:
        target = assets["voiceover_merged.wav"]
        media_type = "audio/wav"
        download_name = "voiceover_merged.wav"
    elif clean_name in {"bundle.zip", "capcut_bundle.zip", "all.zip", "zip"}:
        target = assets["bundle.zip"]
        media_type = "application/zip"
        download_name = f"capcut_export_{project_id}.zip"
    else:
        raise HTTPException(status_code=404, detail=f"Unknown asset {asset_name}")

    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"Asset {asset_name} could not be generated")
    return FileResponse(target, filename=download_name, media_type=media_type)


@router.post("/api/projects/{project_id}/open-folder")
async def open_project_folder_handler(project_id: str) -> JSONResponse:
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    proj_dir = get_project_dir(project_id)
    exports_dir = proj_dir / "exports"
    target_dir = exports_dir if exports_dir.is_dir() else proj_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(target_dir))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target_dir)])
        else:
            subprocess.Popen(["xdg-open", str(target_dir)])
    except Exception:
        pass
    return JSONResponse({"ok": True, "path": str(target_dir.resolve().as_posix())})


def register_routes(app) -> None:
    app.include_router(router)
