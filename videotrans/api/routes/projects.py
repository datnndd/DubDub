# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any
from aiohttp import web

from videotrans.core.project_store import (
    create_project,
    get_project,
    list_projects,
    update_project,
    delete_project,
    find_project_by_audio_hash,
)
from videotrans.core.content_hash import compute_content_hash


async def list_projects_handler(request: web.Request) -> web.Response:
    try:
        limit = int(request.query.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100
    projects = list_projects(limit=limit)
    return web.json_response({"projects": projects})


async def create_project_handler(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON project request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Project payload must be a JSON object")

    media_id = str(payload.get("mediaId") or payload.get("media_id") or "") or None
    name = str(payload.get("name") or "Untitled Project").strip() or "Untitled Project"
    media_store = request.app["media_store"]
    media = media_store.get(media_id) if media_id else None
    media_path = str(media.path) if media else (str(payload.get("mediaPath") or "") or None)

    duration = 0.0
    if media and media.info.get("time"):
        try:
            duration = float(media.info["time"]) / 1000.0
        except (ValueError, TypeError):
            pass
    elif payload.get("duration"):
        try:
            duration = float(payload["duration"])
        except (ValueError, TypeError):
            pass

    audio_hash = ""
    if media and media.path.is_file():
        try:
            audio_hash = compute_content_hash(media.path)
        except Exception:
            pass

    stage = 1
    if payload.get("stage"):
        try:
            stage = int(payload["stage"])
        except (ValueError, TypeError):
            pass

    status = str(payload.get("status") or "pending")
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}

    if audio_hash and not state.get("segments"):
        cached_proj = find_project_by_audio_hash(audio_hash)
        if cached_proj and cached_proj.get("state", {}).get("segments"):
            state["segments"] = cached_proj["state"]["segments"]
            if cached_proj.get("stage", 1) > stage:
                stage = cached_proj["stage"]

    project = create_project(
        project_id=str(payload.get("id") or "") or None,
        name=name,
        media_id=media_id,
        media_path=media_path,
        duration=duration,
        stage=stage,
        status=status,
        audio_hash=audio_hash,
        state=state,
    )

    return web.json_response(project, status=201)


async def get_project_handler(request: web.Request) -> web.Response:
    pid = request.match_info["project_id"]
    project = get_project(pid)
    if not project:
        raise web.HTTPNotFound(text="Project not found")
    return web.json_response(project)


async def update_project_handler(request: web.Request) -> web.Response:
    pid = request.match_info["project_id"]
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON update request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Payload must be a JSON object")

    kwargs: dict[str, Any] = {}
    if "state" in payload and isinstance(payload["state"], dict):
        kwargs["state"] = payload["state"]
    if "stage" in payload:
        try:
            kwargs["stage"] = int(payload["stage"])
        except (ValueError, TypeError):
            pass
    if "status" in payload:
        kwargs["status"] = str(payload["status"])
    if "name" in payload:
        kwargs["name"] = str(payload["name"])
    if "duration" in payload:
        try:
            kwargs["duration"] = float(payload["duration"])
        except (ValueError, TypeError):
            pass

    project = update_project(pid, **kwargs)
    if not project:
        raise web.HTTPNotFound(text="Project not found")
    return web.json_response(project)


async def delete_project_handler(request: web.Request) -> web.Response:
    pid = request.match_info["project_id"]
    deleted = delete_project(pid, delete_files=True)
    if not deleted:
        raise web.HTTPNotFound(text="Project not found")
    return web.json_response({"ok": True, "id": pid})


async def resume_project_handler(request: web.Request) -> web.Response:
    pid = request.match_info["project_id"]
    project = get_project(pid)
    if not project:
        raise web.HTTPNotFound(text="Project not found")
    return web.json_response({"ok": True, "project": project})


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/projects", list_projects_handler)
    app.router.add_post("/api/projects", create_project_handler)
    app.router.add_get("/api/projects/{project_id}", get_project_handler)
    app.router.add_put("/api/projects/{project_id}", update_project_handler)
    app.router.add_delete("/api/projects/{project_id}", delete_project_handler)
    app.router.add_post("/api/projects/{project_id}/resume", resume_project_handler)
