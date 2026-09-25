# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from videotrans.core.project_store import (
    create_project,
    get_project,
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

    if payload.state is not None and isinstance(payload.state, dict):
        project = update_project_state(
            project_id,
            state_dict=payload.state,
            stage=kwargs.get("stage"),
            status=kwargs.get("status"),
        )
        if project and any(k in kwargs for k in ("name", "duration")):
            extra = {k: kwargs[k] for k in ("name", "duration") if k in kwargs}
            project = update_project(project_id, **extra)
    else:
        project = update_project(project_id, **kwargs)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return JSONResponse(project)


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


def register_routes(app) -> None:
    app.include_router(router)
