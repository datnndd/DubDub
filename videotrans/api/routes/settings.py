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
    raw_provider = (
        request.query.get("ttsType")
        or request.query.get("tts_type")
        or request.query.get("provider")
    )

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
        raw_voices = request.app["role_provider"](tts_type, langcode=language)
        if raw_voices is None or (isinstance(raw_voices, (list, tuple)) and len(raw_voices) == 0):
            return web.json_response({"voices": ["No"]})
        voices = raw_voices
    except Exception:
        return web.json_response({"voices": ["No"]})

    from videotrans.core import voice_store
    items: list[dict[str, Any]] = []
    try:
        custom_voices = voice_store.list_voices(provider=tts_type, active_only=True)
        custom_by_name = {v["name"].casefold(): v for v in custom_voices}
    except Exception:
        custom_voices = []
        custom_by_name = {}

    for v in voices:
        v_str = str(v)
        c_name = v_str[8:] if v_str.startswith("Custom: ") else v_str
        matched_custom = custom_by_name.get(c_name.casefold())
        if matched_custom:
            items.append({
                "id": matched_custom["id"],
                "name": matched_custom["name"],
                "provider": tts_type,
                "kind": "clone",
                "sampleUrl": f"/api/custom-voices/{matched_custom['id']}/audio",
            })
        elif v_str.lower() == "clone":
            items.append({
                "id": "clone",
                "name": "Clone Voice",
                "provider": tts_type,
                "kind": "clone",
            })
        elif v_str == "No":
            items.append({
                "id": "No",
                "name": "No Dubbing (Mute/Retain)",
                "provider": tts_type,
                "kind": "preset",
            })
        else:
            items.append({
                "id": v_str,
                "name": v_str,
                "provider": tts_type,
                "kind": "preset",
            })

    existing_item_ids = {it["id"] for it in items}
    for cv in custom_voices:
        if cv["id"] not in existing_item_ids:
            items.append({
                "id": cv["id"],
                "name": cv["name"],
                "provider": tts_type,
                "kind": "clone",
                "sampleUrl": f"/api/custom-voices/{cv['id']}/audio",
            })
            existing_item_ids.add(cv["id"])

    return web.json_response({"voices": voices, "items": items})


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/options", options_handler)
    app.router.add_get("/api/voices", voices_handler)
    app.router.add_post("/api/asr-settings/{provider_id}", asr_settings_handler)
    app.router.add_post("/api/asr-settings/{provider_id}/test", test_asr_settings_handler)
    app.router.add_post("/api/translation-settings/{provider_id}", translation_settings_handler)
    app.router.add_post("/api/translation-settings/{provider_id}/test", test_translation_settings_handler)
