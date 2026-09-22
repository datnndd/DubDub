# -*- coding: utf-8 -*-
"""Web application factory and route assembly."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Callable

from aiohttp import web

from videotrans.configure.config import app_cfg, params as app_params
from videotrans.core.db import init_db
from videotrans.core.job_store import sweep_orphans_on_startup
from videotrans.core.job_manager import JobManager, JOBS, run_prepare_review
from videotrans.core.media_store import MediaStore, MEDIA
from videotrans.util._ffprobe import get_video_info
from videotrans.api.catalog import (
    UPLOAD_DIR,
    get_frontend_dir,
)
from videotrans.api.provider_helpers import (
    test_asr_provider,
    test_translation_provider,
)
from videotrans.api.ocr_helpers import extract_ocr_segment_text
from videotrans.api.routes import projects, jobs, media, settings, stages


@web.middleware
async def no_cache_middleware(request: web.Request, handler: Callable) -> web.StreamResponse:
    response = await handler(request)
    if (
        request.path == "/"
        or request.path.endswith((".html", ".js", ".css"))
        or request.path.startswith(("/js", "/css", "/assets"))
    ):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def frontend_version() -> str:
    digest = hashlib.sha1()
    frontend_dir = get_frontend_dir()
    for path in sorted(frontend_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        digest.update(f"{path.relative_to(frontend_dir)}:{stat.st_mtime_ns}:{stat.st_size}".encode())
    return digest.hexdigest()


async def dev_reload_handler(_request: web.Request) -> web.Response:
    return web.json_response(
        {"version": frontend_version()},
        headers={"Cache-Control": "no-store"},
    )


async def index_handler(request: web.Request) -> web.StreamResponse:
    frontend_dir = get_frontend_dir()
    dist_index = frontend_dir / "dist" / "index.html"
    index_file = dist_index if dist_index.is_file() else (frontend_dir / "index.html")

    if request.app.get("reload"):
        html = index_file.read_text(encoding="utf-8")
        script = f"""<script>
let frontendVersion = '{frontend_version()}';
setInterval(async () => {{
  try {{
    const response = await fetch('/__dev_reload__', {{ cache: 'no-store' }});
    if ((await response.json()).version !== frontendVersion) location.reload();
  }} catch {{}}
}}, 500);
</script>"""
        return web.Response(text=html.replace("</body>", f"{script}</body>"), content_type="text/html")
    response = web.FileResponse(index_file)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def create_app(
    *,
    job_manager: JobManager | None = None,
    upload_dir: Path | None = None,
    media_probe: Callable[[str | Path], dict[str, Any]] = get_video_info,
    settings_store: Any = None,
    asr_tester: Callable[[int, str], str] = test_asr_provider,
    translation_tester: Callable[[int, bool | None], str] = test_translation_provider,
    translation_runner: Callable | None = None,
    ocr_extractor: Callable | None = None,
    reload: bool = False,
) -> web.Application:
    init_db()
    sweep_orphans_on_startup()
    frontend_dir = get_frontend_dir()
    if not (frontend_dir / "index.html").is_file() and not (frontend_dir / "dist" / "index.html").is_file():
        raise RuntimeError(f"Frontend not found: {frontend_dir}")
    app = web.Application(middlewares=[no_cache_middleware], client_max_size=20 * 1024 ** 3)
    if job_manager is None and translation_runner is not None:
        job_manager = JobManager(
            runner=run_prepare_review,
            translation_runner=translation_runner,
        )
    app["job_manager"] = job_manager or JOBS
    app["media_store"] = MEDIA if upload_dir is None and media_probe is get_video_info else MediaStore(upload_dir or UPLOAD_DIR, media_probe)
    app["settings_store"] = app_params if settings_store is None else settings_store
    app["asr_tester"] = asr_tester
    app["translation_tester"] = translation_tester
    app["ocr_extractor"] = ocr_extractor or extract_ocr_segment_text
    app["reload"] = reload

    # Static and root routes
    app.router.add_get("/", index_handler)
    if reload:
        app.router.add_get("/__dev_reload__", dev_reload_handler)

    # Modular routers
    settings.register_routes(app)
    media.register_routes(app)
    projects.register_routes(app)
    jobs.register_routes(app)
    stages.register_routes(app)

    # Static assets
    app.router.add_static("/css", frontend_dir / "css")
    app.router.add_static("/js", frontend_dir / "js")
    dist_assets = frontend_dir / "dist" / "assets"
    if dist_assets.is_dir():
        app.router.add_static("/assets", dist_assets)
    else:
        app.router.add_static("/assets", frontend_dir / "assets")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="pyVideoTrans Dubbing Video WebUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--reload", action="store_true", help="reload browser tabs when frontend files change")
    args = parser.parse_args()
    app_cfg.exec_mode = "web"
    web.run_app(create_app(reload=args.reload), host=args.host, port=args.port)
