# -*- coding: utf-8 -*-
"""Catalog definitions, directory paths, provider registries, and aliases for WebUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from videotrans import recognition, translator, tts
from videotrans.configure.config import ROOT_DIR, TEMP_DIR

FRONTEND_DIR = Path(ROOT_DIR) / "frontend"
UPLOAD_DIR = Path(TEMP_DIR) / "webui_uploads"
OUTPUT_DIR = Path(ROOT_DIR) / "output"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_frontend_dir() -> Path:
    """Return the configured frontend source directory."""
    return FRONTEND_DIR


ASR_PROVIDERS = (
    {
        "id": "qwen-asr",
        "label": "Qwen-ASR",
        "recognType": recognition.QWENASR,
        "models": ("1.7B", "0.6B"),
    },
    {
        "id": "deepgram",
        "label": "Deepgram",
        "recognType": recognition.Deepgram,
        "models": tuple(recognition.get_model_by_type(recognition.Deepgram)),
        "settingsKey": "deepgram_apikey",
        "thirdParty": True,
    },
    {
        "id": "gemini-stt",
        "label": "Gemini STT",
        "recognType": recognition.GEMINI_SPEECH,
        "models": ("gemini-flash-latest",),
        "settingsKey": "gemini_key",
        "thirdParty": True,
    },
    {
        "id": "google-stt",
        "label": "Google STT API",
        "recognType": recognition.GOOGLE_SPEECH,
        "models": ("google-web-speech",),
        "thirdParty": True,
    },
    {
        "id": "elevenlabs",
        "label": "ElevenLabs",
        "recognType": recognition.ElevenLabs,
        "models": ("scribe_v2",),
        "settingsKey": "elevenlabstts_key",
        "thirdParty": True,
    },
    {
        "id": "whisper-large-v3",
        "label": "Whisper Large-v3",
        "recognType": recognition.FASTER_WHISPER,
        "models": ("large-v3",),
    },
)
ASR_BY_TYPE = {provider["recognType"]: provider for provider in ASR_PROVIDERS}
ASR_BY_ID = {provider["id"]: provider for provider in ASR_PROVIDERS}

TIMING_MODES = {
    "voice": {"voice_autorate": True, "video_autorate": False, "align_sub_audio": False},
    "video": {"voice_autorate": False, "video_autorate": True, "align_sub_audio": False},
    "align": {"voice_autorate": False, "video_autorate": False, "align_sub_audio": True},
}

TRANSLATION_MODES = {
    "line": {
        "label": "Line-by-line",
        "description": "Send plain subtitle text in batches.",
        "aisendsrt": False,
    },
    "srt": {
        "label": "Send SRT",
        "description": "Send subtitle blocks with timestamps and structure.",
        "aisendsrt": True,
    },
}

TRANSLATION_PROVIDERS = (
    {
        "id": "google",
        "label": "Google Translate",
        "translateType": translator.GOOGLE_INDEX,
    },
    {
        "id": "openai",
        "label": "OpenAI ChatGPT",
        "translateType": translator.CHATGPT_INDEX,
        "baseUrlKey": "chatgpt_api",
        "defaultBaseUrl": "https://api.openai.com/v1",
        "keyKey": "chatgpt_key",
        "modelKey": "chatgpt_model",
    },
    {
        "id": "gemini",
        "label": "Gemini",
        "translateType": translator.GEMINI_INDEX,
        "baseUrlKey": "gemini_api",
        "defaultBaseUrl": "",
        "keyKey": "gemini_key",
        "modelKey": "gemini_model",
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "translateType": translator.DEEPSEEK_INDEX,
        "baseUrlKey": "deepseek_api",
        "defaultBaseUrl": "https://api.deepseek.com/v1",
        "keyKey": "deepseek_key",
        "modelKey": "deepseek_model",
    },
)
TRANSLATION_BY_TYPE = {provider["translateType"]: provider for provider in TRANSLATION_PROVIDERS}
TRANSLATION_BY_ID = {provider["id"]: provider for provider in TRANSLATION_PROVIDERS}

TTS_PROVIDER_ALIASES: dict[str, int] = {
    "elevenlabs": tts.ELEVENLABS_TTS,
    "omnivoice": tts.OMNIVOICE_TTS,
    "vieneu": tts.VIENEU_TTS,
    "vieneu-tts": tts.VIENEU_TTS,
    "vieneutts": tts.VIENEU_TTS,
    "gemini": tts.GEMINI_TTS,
    "gemini-tts": tts.GEMINI_TTS,
    "geminitts": tts.GEMINI_TTS,
}
for _idx, _name in enumerate(tts.TTS_NAME_LIST):
    TTS_PROVIDER_ALIASES[_name.lower()] = _idx
    TTS_PROVIDER_ALIASES[_name.lower().replace(" ", "")] = _idx
