# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from aiohttp import web

from videotrans.configure import config as runtime_config
from videotrans.configure.config import TEMP_DIR
from videotrans.core.job_manager import ActiveJobError
from videotrans.core.media_store import MediaRecord
from videotrans.core.job_store import (
    get_job as db_get_job,
    list_jobs as db_list_jobs,
    events_since,
)
from videotrans.core.project_store import update_project
from videotrans.util.gpus import getset_gpu
from videotrans.api.task_params import build_task_params
from videotrans.api.provider_helpers import ensure_asr_configured, ensure_translation_configured


async def list_jobs_handler(request: web.Request) -> web.Response:
    status = request.query.get("status")
    project_id = request.query.get("project_id") or request.query.get("projectId")
    try:
        limit = int(request.query.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100
    jobs = db_list_jobs(status=status, project_id=project_id, limit=limit)
    return web.json_response({"jobs": jobs})


async def create_job_handler(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON job request is required") from exc
    media_id = str(payload.get("mediaId") or "")
    options = payload.get("options")
    if not isinstance(options, dict):
        raise web.HTTPBadRequest(text="Job options are required")
    media_store = request.app["media_store"]
    media = media_store.get(media_id)
    default_job_type = "render" if request.path in {"/api/render", "/api/export"} else "full"
    job_type = str(payload.get("jobType") or options.get("jobType") or default_job_type).lower()

    if job_type == "translation" and (media is None or not media.path.is_file()):
        fallback_path = Path(TEMP_DIR) / f"webui-trans-{uuid.uuid4().hex}.mp4"
        fallback_path.touch(exist_ok=True)
        media_id = media_id or f"trans-mock-{uuid.uuid4().hex}"
        media = MediaRecord(media_id, fallback_path, fallback_path.name, 0, {"time": 1000})
    elif media is None or not media.path.is_file():
        raise web.HTTPBadRequest(text="Select and inspect a media file before starting")

    for option_key, path_key in (("backgroundAudioId", "backgroundMusicPath"), ("thumbnailId", "thumbnailPath")):
        asset_id = str(options.get(option_key) or "")
        if not asset_id:
            continue
        asset_path = request.app["edit_asset_store"].get(asset_id)
        if asset_path is None or not asset_path.is_file():
            raise web.HTTPBadRequest(text=f"Unknown or expired {option_key}")
        options[path_key] = asset_path.resolve().as_posix()

    project_id = str(payload.get("projectId") or payload.get("project_id") or options.get("projectId") or options.get("project_id") or "") or None
    if project_id:
        options["projectId"] = project_id
    try:
        params = build_task_params(media.path, options, job_type=job_type, project_id=project_id)
        import sys
        if job_type not in {"render", "translation"}:
            asr_conf = getattr(sys.modules.get("webui"), "ensure_asr_configured", ensure_asr_configured) if "webui" in sys.modules else ensure_asr_configured
            asr_conf(params["recogn_type"], request.app["settings_store"])
        if job_type not in {"asr", "render"}:
            trans_conf = getattr(sys.modules.get("webui"), "ensure_translation_configured", ensure_translation_configured) if "webui" in sys.modules else ensure_translation_configured
            trans_conf(params["translate_type"], request.app["settings_store"])
        gpu_fn = getattr(sys.modules.get("webui"), "getset_gpu", getset_gpu) if "webui" in sys.modules else getset_gpu
        gpu_fn()
        manager = request.app["job_manager"]
        job = manager.submit(params, media_id=media.id, job_type=job_type, project_id=project_id)
        if project_id:
            try:
                update_project(project_id, status="processing")
            except Exception:
                pass
    except ActiveJobError as exc:
        raise web.HTTPConflict(text=str(exc)) from exc
    except (ValueError, TypeError, OverflowError) as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    return web.json_response(job.snapshot(), status=202)


async def job_handler(request: web.Request) -> web.Response:
    job = request.app["job_manager"].get(request.match_info["job_id"])
    if not job:
        raise web.HTTPNotFound(text="Job not found")
    return web.json_response(job.snapshot())


async def job_transcript_handler(request: web.Request) -> web.Response:
    job = request.app["job_manager"].get(request.match_info["job_id"])
    if not job:
        raise web.HTTPNotFound(text="Job not found")
    return web.json_response({"segments": list(job.segments)})


async def cancel_job_handler(request: web.Request) -> web.Response:
    job = request.app["job_manager"].cancel(request.match_info["job_id"])
    if not job:
        raise web.HTTPNotFound(text="Job not found")
    return web.json_response(job.snapshot())


async def output_handler(request: web.Request) -> web.StreamResponse:
    job = request.app["job_manager"].get(request.match_info["job_id"])
    if not job:
        raise web.HTTPNotFound(text="Job not found")
    try:
        output = job.outputs[int(request.match_info["index"])]
    except (ValueError, IndexError):
        raise web.HTTPNotFound(text="Output not found")
    if not output.is_file():
        raise web.HTTPNotFound(text="Output no longer exists")
    return web.FileResponse(output, headers={"Content-Disposition": f'attachment; filename="{output.name}"'})


async def job_stream_handler(request: web.Request) -> web.StreamResponse:
    job_id = request.match_info["job_id"]
    try:
        after_seq = int(request.query.get("after_seq", 0))
    except (ValueError, TypeError):
        after_seq = 0

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await response.prepare(request)

    past_events = events_since(job_id, after_seq=after_seq)
    last_seq = after_seq
    for ev in past_events:
        seq = ev["seq"]
        payload = ev["payload"]
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        line = f"id: {seq}\nevent: message\ndata: {raw}\n\n"
        await response.write(line.encode("utf-8"))
        last_seq = max(last_seq, seq)

    manager = request.app["job_manager"]
    job = manager.get(job_id)
    db_job = db_get_job(job_id)
    status = (job.status if job else (db_job.get("status") if db_job else None)) or "unknown"

    if status in {"succeeded", "failed", "cancelled"}:
        close_payload = json.dumps({"status": status, "terminal": True, "seq": last_seq})
        await response.write(f"id: {last_seq + 1}\nevent: done\ndata: {close_payload}\n\n".encode("utf-8"))
        try:
            await response.write_eof()
        except Exception:
            pass
        return response

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    if job:
        job.subscribe(queue, loop)

    try:
        while True:
            try:
                seq, payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                if seq > last_seq:
                    raw_data = json.dumps(payload) if isinstance(payload, dict) else str(payload)
                    line = f"id: {seq}\nevent: message\ndata: {raw_data}\n\n"
                    await response.write(line.encode("utf-8"))
                    last_seq = seq
                    if isinstance(payload, dict) and payload.get("status") in {"succeeded", "failed", "cancelled"}:
                        break
            except asyncio.TimeoutError:
                await response.write(b": keep-alive\n\n")
                cur_job = db_get_job(job_id)
                if cur_job and cur_job.get("status") in {"succeeded", "failed", "cancelled"}:
                    break
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        if job:
            job.unsubscribe(queue)

    try:
        await response.write_eof()
    except Exception:
        pass
    return response


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/jobs", list_jobs_handler)
    app.router.add_post("/api/jobs", create_job_handler)
    app.router.add_post("/api/render", create_job_handler)
    app.router.add_post("/api/export", create_job_handler)
    app.router.add_get("/api/jobs/{job_id}", job_handler)
    app.router.add_get("/api/jobs/{job_id}/stream", job_stream_handler)
    app.router.add_get("/api/jobs/{job_id}/transcript", job_transcript_handler)
    app.router.add_get("/api/jobs/{job_id}/segments", job_transcript_handler)
    app.router.add_post("/api/jobs/{job_id}/cancel", cancel_job_handler)
    app.router.add_get("/api/jobs/{job_id}/outputs/{index}", output_handler)
