# -*- coding: utf-8 -*-
"""Provider configuration validation, persistence, and connection testing helpers."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from videotrans import recognition, translator
from videotrans.configure import config as runtime_config
from videotrans.configure.config import ROOT_DIR, TEMP_DIR
from videotrans.util.network import process_openai_api
from videotrans.api.catalog import (
    ASR_BY_TYPE,
    TRANSLATION_BY_TYPE,
)


def ensure_asr_configured(recogn_type: int, settings_store: Any) -> None:
    provider = ASR_BY_TYPE[recogn_type]
    settings_key = provider.get("settingsKey")
    if settings_key and not settings_store.get(settings_key):
        raise ValueError(f"Configure {provider['label']} API settings before starting")


def ensure_translation_configured(translate_type: int, settings_store: Any) -> None:
    provider = TRANSLATION_BY_TYPE[translate_type]
    key_name = provider.get("keyKey")
    if key_name and not settings_store.get(key_name):
        raise ValueError(f"Configure {provider['label']} settings before starting")


def _save_asr_settings(provider: dict[str, Any], payload: dict[str, Any], settings_store: Any) -> dict[str, bool]:
    settings_key = provider.get("settingsKey")
    if not settings_key:
        raise ValueError("This ASR provider has no WebUI API settings")
    api_key = str(payload.get("apiKey") or "").strip()
    if not api_key and not settings_store.get(settings_key):
        raise ValueError("API key is required")
    if api_key:
        settings_store[settings_key] = api_key
        settings_store.save()
    return {"configured": True}


def _translation_models(provider: dict[str, Any], settings_store: Any) -> list[str]:
    model_key = provider.get("modelKey")
    if not model_key:
        return []
    models = [item.strip() for item in str(runtime_config.settings.get(model_key, "")).split(",") if item.strip()]
    current = str(settings_store.get(model_key, "")).strip()
    if current and current not in models:
        models.insert(0, current)
    return models


def _translation_snapshot(provider: dict[str, Any], settings_store: Any) -> dict[str, Any]:
    key_name = provider.get("keyKey")
    model_key = provider.get("modelKey")
    base_url_key = provider.get("baseUrlKey")
    return {
        "id": provider["id"],
        "label": provider["label"],
        "translateType": provider["translateType"],
        "requiresSettings": bool(key_name),
        "configured": not key_name or bool(settings_store.get(key_name)),
        "baseUrl": str(settings_store.get(base_url_key, provider.get("defaultBaseUrl", ""))) if base_url_key else "",
        "model": str(settings_store.get(model_key, "")) if model_key else "",
        "models": _translation_models(provider, settings_store),
    }


def _save_translation_settings(provider: dict[str, Any], payload: dict[str, Any], settings_store: Any) -> dict[str, Any]:
    key_name = provider["keyKey"]
    api_key = str(payload.get("apiKey") or "").strip()
    if not api_key and not settings_store.get(key_name):
        raise ValueError("API key is required")

    model_key = provider["modelKey"]
    model = str(payload.get("model") or settings_store.get(model_key, "")).strip()
    if not model:
        raise ValueError("Model is required")

    base_url_key = provider["baseUrlKey"]
    base_url = str(payload.get("baseUrl") or settings_store.get(base_url_key, provider["defaultBaseUrl"])).strip()
    if provider["id"] == "openai":
        base_url = process_openai_api(base_url)
    elif base_url:
        if not re.match(r"^https?://", base_url, flags=re.I):
            raise ValueError("Base URL must start with http:// or https://")
        base_url = base_url.rstrip("/")

    if api_key:
        settings_store[key_name] = api_key
    settings_store[model_key] = model
    settings_store[base_url_key] = base_url
    settings_store.save()
    return _translation_snapshot(provider, settings_store)


def test_translation_provider(translate_type: int, aisendsrt: bool | None = None) -> str:
    if translate_type == translator.GOOGLE_INDEX and translator._check_google() is not True:
        raise RuntimeError("Google Translate is not reachable")
    raw = "你好啊我的朋友"
    translated = translator.run(
        translate_type=translate_type,
        text_list=[{"text": raw, "line": 1, "time": "00:00:00,000 --> 00:00:05,000"}],
        target_code="en",
        source_code="zh-cn",
        is_test=True,
        aisendsrt=aisendsrt,
    )
    if not translated or not translated[0].get("text"):
        raise RuntimeError("The translation provider returned no text")
    return str(translated[0]["text"])


def test_asr_provider(recogn_type: int, model_name: str) -> str:
    provider = ASR_BY_TYPE.get(recogn_type)
    if provider is None or not provider.get("thirdParty"):
        raise ValueError("Connection testing is only available for third-party ASR providers")
    if model_name not in provider["models"]:
        raise ValueError(f"Model {model_name} is not supported by {provider['label']}")

    import sys
    sample_audio = Path(ROOT_DIR) / "videotrans" / "assets" / "no-remove.wav"
    rec = getattr(sys.modules.get("webui"), "recognition", recognition) if "webui" in sys.modules else recognition
    tmp_dir = getattr(sys.modules.get("webui"), "TEMP_DIR", TEMP_DIR) if "webui" in sys.modules else TEMP_DIR
    with TemporaryDirectory(prefix="asr-test-", dir=tmp_dir) as cache_folder:
        result = rec.run(
            audio_file=sample_audio.as_posix(),
            cache_folder=cache_folder,
            recogn_type=recogn_type,
            model_name=model_name,
            detect_language="zh-cn",
            uuid=f"asr-test-{uuid.uuid4().hex}",
        )
    if not result or not result[0].get("text"):
        raise RuntimeError("The ASR provider returned no transcription")
    return str(result[0]["text"])

