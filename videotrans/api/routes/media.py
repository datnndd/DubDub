# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from pathlib import Path
from urllib.parse import unquote

from aiohttp import web

from videotrans.configure.contants import AUDIO_EXITS, VIDEO_EXTS
from videotrans.core.edit_asset_store import EDIT_ASSET_STORE

# Compatibility aliases for legacy tests; request handling uses the injected service.
EDIT_ASSETS = EDIT_ASSET_STORE.items
EDIT_ASSETS_LOCK = EDIT_ASSET_STORE.lock


async def media_handler(request: web.Request) -> web.Response:
    reader = await request.multipart()
    upload_path: Path | None = None
    filename = ""
    store = request.app["media_store"]
    async for part in reader:
        if part.name == "file" and part.filename:
            filename = Path(unquote(part.filename)).name
            extension = Path(filename).suffix.lower().lstrip(".")
            if extension not in {*VIDEO_EXTS, *AUDIO_EXITS}:
                raise web.HTTPBadRequest(text=f"Unsupported media type: .{extension or 'unknown'}")
            upload_path = store.upload_dir / f"{uuid.uuid4().hex}-{filename}"
            with upload_path.open("wb") as output:
                while chunk := await part.read_chunk():
                    output.write(chunk)
    if upload_path is None or not upload_path.is_file():
        raise web.HTTPBadRequest(text="A video or audio file is required")

    try:
        media = store.inspect(upload_path, filename)
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        raise web.HTTPBadRequest(text=f"Unable to read media: {exc}") from exc
    return web.json_response(media.snapshot(), status=201)


async def edit_asset_handler(request: web.Request) -> web.Response:
    kind = request.match_info["kind"]
    allowed = {
        "background-audio": AUDIO_EXITS,
        "thumbnail": {"png", "jpg", "jpeg", "webp"},
    }
    if kind not in allowed:
        raise web.HTTPNotFound(text="Unknown edit asset type")
    saved: Path | None = None
    filename = ""
    store = request.app["media_store"]

    content_type = (request.content_type or "").lower()
    if "x-www-form-urlencoded" in content_type:
        raise web.HTTPBadRequest(text="An asset file is required")

    if "multipart" in content_type:
        reader = await request.multipart()
        async for part in reader:
            if part.name != "file" or not part.filename:
                continue
            filename = Path(unquote(part.filename)).name
            extension = Path(filename).suffix.lower().lstrip(".")
            if extension not in set(allowed[kind]):
                raise web.HTTPBadRequest(text=f"Unsupported {kind} type: .{extension or 'unknown'}")
            saved = store.upload_dir / f"edit-{uuid.uuid4().hex}-{filename}"
            with saved.open("wb") as output:
                while chunk := await part.read_chunk():
                    output.write(chunk)
    else:
        raw_name = request.headers.get("X-Filename") or request.query.get("filename") or ""
        if not raw_name:
            raise web.HTTPBadRequest(text="An asset file is required")
        filename = Path(unquote(raw_name)).name
        if not filename:
            raise web.HTTPBadRequest(text="A valid filename is required")
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in set(allowed[kind]):
            raise web.HTTPBadRequest(text=f"Unsupported {kind} type: .{extension or 'unknown'}")
        content = await request.read()
        if not content:
            raise web.HTTPBadRequest(text="An asset file is required")
        saved = store.upload_dir / f"edit-{uuid.uuid4().hex}-{filename}"
        saved.write_bytes(content)

    if saved is None or not saved.is_file() or saved.stat().st_size == 0:
        if saved and saved.is_file():
            saved.unlink(missing_ok=True)
        raise web.HTTPBadRequest(text="An asset file is required")

    asset_id = uuid.uuid4().hex
    request.app["edit_asset_store"].put(asset_id, saved)
    return web.json_response({"id": asset_id, "name": filename}, status=201)


def register_routes(app: web.Application) -> None:
    app.router.add_post("/api/media", media_handler)
    app.router.add_post("/api/assets/{kind}", edit_asset_handler)
