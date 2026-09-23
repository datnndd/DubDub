# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Any
from aiohttp import web

from videotrans import recognition, translator, tts
from videotrans.configure import config as runtime_config
from videotrans.configure.excepts import get_msg_from_except
from videotrans.util.help_role import role_menu
from videotrans.api.catalog import (
    ASR_BY_ID,
    ASR_PROVIDERS,
    TIMING_MODES,
    TRANSLATION_BY_ID,
    TRANSLATION_MODES,
    TRANSLATION_PROVIDERS,
    TTS_PROVIDER_ALIASES,
)
from videotrans.api.task_params import _optional_index, _translation_mode
from videotrans.api.provider_helpers import (
    _save_asr_settings,
    _save_translation_settings,
    _translation_snapshot,
)


async def options_handler(request: web.Request) -> web.Response:
    languages = [{"code": code, "name": name} for code, name in translator.LANGNAME_DICT.items()]
    settings_store = request.app["settings_store"]
    asr_providers = []
    for provider in ASR_PROVIDERS:
        settings_key = provider.get("settingsKey")
        asr_providers.append({
            "id": provider["id"],
            "label": provider["label"],
            "recognType": provider["recognType"],
            "models": list(provider["models"]),
            "requiresSettings": bool(settings_key),
            "configured": bool(settings_key and settings_store.get(settings_key)),
            "testable": bool(provider.get("thirdParty")),
        })
    return web.json_response({
        "languages": languages,
        "asrProviders": asr_providers,
        "translationProviders": [
            _translation_snapshot(provider, settings_store)
            for provider in TRANSLATION_PROVIDERS
        ],
        "translationModes": [
            {"id": mode_id, "label": mode["label"], "description": mode["description"]}
            for mode_id, mode in TRANSLATION_MODES.items()
        ],
        "voices": list(enumerate(tts.TTS_NAME_LIST)),
        "defaults": {
            "sourceLanguage": "zh-cn",
            "targetLanguage": "vi",
            "recognType": recognition.Deepgram,
            "modelName": "nova-3",
            "timingMode": "voice",
            "translateType": translator.GOOGLE_INDEX,
            "translationMode": _translation_mode()[0],
            "ttsType": tts.DEFAULT_TTS,
        },
    })


async def asr_settings_handler(request: web.Request) -> web.Response:
    provider = ASR_BY_ID.get(request.match_info["provider_id"])
    if provider is None or not provider.get("settingsKey"):
        raise web.HTTPNotFound(text="This ASR provider has no WebUI API settings")
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON settings request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="ASR settings must be a JSON object")
    try:
        snapshot = _save_asr_settings(provider, payload, request.app["settings_store"])
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    return web.json_response(snapshot)


async def test_asr_settings_handler(request: web.Request) -> web.Response:
    provider = ASR_BY_ID.get(request.match_info["provider_id"])
    if provider is None or not provider.get("thirdParty"):
        raise web.HTTPNotFound(text="This ASR provider does not use a third-party connection")
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON settings request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="ASR settings must be a JSON object")

    model_name = str(payload.get("model") or "").strip()
    if model_name not in provider["models"]:
        raise web.HTTPBadRequest(text=f"Model {model_name or 'missing'} is not supported by {provider['label']}")
    try:
        if provider.get("settingsKey"):
            _save_asr_settings(provider, payload, request.app["settings_store"])
        result = await asyncio.to_thread(
            request.app["asr_tester"], provider["recognType"], model_name
        )
    except Exception as exc:
        runtime_config.logger.exception("ASR connection test failed", exc_info=True)
        raise web.HTTPBadRequest(text=f"Connection test failed: {get_msg_from_except(exc)}") from exc
    return web.json_response({
        "ok": True,
        "message": "Connection successful",
        "model": model_name,
        "result": result,
    })


async def translation_settings_handler(request: web.Request) -> web.Response:
    provider = TRANSLATION_BY_ID.get(request.match_info["provider_id"])
    if provider is None or not provider.get("keyKey"):
        raise web.HTTPNotFound(text="This translation provider has no WebUI settings")
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON settings request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Translation settings must be a JSON object")
    try:
        snapshot = _save_translation_settings(provider, payload, request.app["settings_store"])
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    return web.json_response(snapshot)


async def test_translation_settings_handler(request: web.Request) -> web.Response:
    provider = TRANSLATION_BY_ID.get(request.match_info["provider_id"])
    if provider is None:
        raise web.HTTPNotFound(text="Unsupported translation provider")
    try:
        payload = await request.json()
    except Exception as exc:
        raise web.HTTPBadRequest(text="A JSON settings request is required") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Translation settings must be a JSON object")
    try:
        _, aisendsrt = _translation_mode(payload.get("translationMode"))
        if provider.get("keyKey"):
            _save_translation_settings(provider, payload, request.app["settings_store"])
        result = await asyncio.to_thread(
            request.app["translation_tester"], provider["translateType"], aisendsrt
        )
    except Exception as exc:
        runtime_config.logger.exception("Translation connection test failed", exc_info=True)
        raise web.HTTPBadRequest(text=f"Connection test failed: {get_msg_from_except(exc)}") from exc
    return web.json_response({"ok": True, "message": "Connection successful", "result": result})


async def voices_handler(request: web.Request) -> web.Response:
    raw_provider = request.query.get("ttsType")
    if raw_provider is None:
        raw_provider = request.query.get("provider")

    tts_type = 0
    if raw_provider is not None:
        val_str = str(raw_provider).strip().lower()
        if val_str in TTS_PROVIDER_ALIASES:
            tts_type = TTS_PROVIDER_ALIASES[val_str]
        else:
            tts_type = _optional_index(raw_provider, len(tts.TTS_NAME_LIST), default=0)

    language = (
        request.query.get("language")
        or request.query.get("target_language")
        or request.query.get("targetLanguage")
        or ""
    )
    try:
        voices = request.app["role_provider"](tts_type, langcode=language) or ["No"]
        if not voices:
            voices = ["No"]
    except Exception:
        voices = ["No"]
    return web.json_response({"voices": voices})


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/options", options_handler)
    app.router.add_get("/api/voices", voices_handler)
    app.router.add_post("/api/asr-settings/{provider_id}", asr_settings_handler)
    app.router.add_post("/api/asr-settings/{provider_id}/test", test_asr_settings_handler)
    app.router.add_post("/api/translation-settings/{provider_id}", translation_settings_handler)
    app.router.add_post("/api/translation-settings/{provider_id}/test", test_translation_settings_handler)
