"""Seven-provider runtime boundary allowlists and sanitizers.

VoiceStudio operates strictly as a web application and Docker runtime supporting:
- TTS: OmniVoice (in-process Python only), VieNeuTTS (vienue)
- ASR: Deepgram (deepgram-asr, explicit opt-in only)
- Translation: Google Translate (google), OpenAI-compatible LLMs (openai)
- LLM: OpenAI-compatible LLMs
- OCR: RapidOCR, PaddleOCR
- HF Model Downloads: k2-fsa/OmniVoice only
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("omnivoice.provider_boundary")

ALLOWED_TTS_PROVIDERS: frozenset[str] = frozenset({"omnivoice", "vienue"})
ALLOWED_ASR_PROVIDERS: frozenset[str] = frozenset({"deepgram-asr", "deepgram"})
ALLOWED_TRANSLATE_PROVIDERS: frozenset[str] = frozenset({"google", "openai"})
ALLOWED_OCR_PROVIDERS: frozenset[str] = frozenset({"rapidocr", "paddleocr"})
ALLOWED_HF_MODELS: frozenset[str] = frozenset({"k2-fsa/OmniVoice"})


def sanitize_tts_backend(backend_id: Optional[str]) -> str:
    """Ensure selected TTS backend is within the 7-provider allowlist."""
    if backend_id and backend_id in ALLOWED_TTS_PROVIDERS:
        return backend_id
    return "omnivoice"


def sanitize_asr_backend(backend_id: Optional[str]) -> str:
    """Ensure selected ASR backend is Deepgram. Does not upload audio."""
    if backend_id in ALLOWED_ASR_PROVIDERS:
        return "deepgram-asr"
    return "deepgram-asr"


def sanitize_translate_provider(provider_id: Optional[str]) -> str:
    """Ensure translation provider is within allowlist (google or openai)."""
    if provider_id and provider_id in ALLOWED_TRANSLATE_PROVIDERS:
        return provider_id
    return "google"


def is_allowed_hf_model(repo_id: str) -> bool:
    """Verify if a Hugging Face repo is allowed for download."""
    return (repo_id or "").strip() in ALLOWED_HF_MODELS


def enforce_hf_model_boundary(repo_id: str) -> None:
    """Raise ValueError if repo_id is outside the single-model allowlist."""
    clean = (repo_id or "").strip()
    if clean not in ALLOWED_HF_MODELS:
        raise ValueError(
            f"Model download blocked: {clean!r} is not permitted. "
            f"VoiceStudio runtime allows only {sorted(ALLOWED_HF_MODELS)}."
        )
