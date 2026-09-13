"""Deepgram-only ASR adapter for the web runtime."""

from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

from utils.containment import contain_system_exit

logger = logging.getLogger("omnivoice.asr")

ASR_TRANSCRIBE_TIMEOUT_S = float(
    os.environ.get("OMNIVOICE_ASR_TRANSCRIBE_TIMEOUT_S", "300.0")
)


class ASRTimeoutError(TimeoutError):
    pass


class ASRModelMissingError(RuntimeError):
    def __init__(self, payload: dict | None = None, message: str | None = None):
        super().__init__(message or "ASR model is missing")
        self.payload = payload or {}


def reset_pool_after_wedge(executor, *, what: str = "ASR") -> bool:
    reset = getattr(executor, "reset", None)
    if not callable(reset):
        return False
    try:
        reset(reason=f"{what} transcription timed out")
        return True
    except TypeError:
        try:
            reset()
            return True
        except Exception:
            logger.warning("%s executor reset failed", what, exc_info=True)
    except Exception:
        logger.warning("%s executor reset failed", what, exc_info=True)
    return False


async def run_transcribe_guarded(
    executor,
    fn,
    *,
    what: str = "ASR",
    timeout: float = ASR_TRANSCRIBE_TIMEOUT_S,
    timeout_env: str = "OMNIVOICE_ASR_TRANSCRIBE_TIMEOUT_S",
):
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(executor, contain_system_exit(fn, what))
    try:
        result = await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError as exc:
        reset_pool_after_wedge(executor, what=what)
        msg = (
            f"{what} transcription exceeded {timeout:.0f}s and was abandoned — "
            "the Deepgram request did not finish in time. Check the network and "
            f"Deepgram service status, then retry. (Raise {timeout_env} for very "
            "long transcribes.)"
        )
        raise ASRTimeoutError(msg) from exc
    return result


class ASRBackend(ABC):
    id: str = "base"
    display_name: str = "Base ASR"
    gpu_compat: tuple[str, ...] = ("cpu",)

    @classmethod
    @abstractmethod
    def is_available(cls) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        *,
        word_timestamps: bool = True,
        language: Optional[str] = None,
        **kwargs,
    ) -> dict:
        raise NotImplementedError

    def ensure_loaded(self) -> None:
        pass

    def unload(self) -> None:
        pass


_ASR_DEEPGRAM_MODEL_KEY = "asr.deepgram.model"
_ASR_DEEPGRAM_SECRET_NAME = "asr_deepgram_key"


def resolve_deepgram_model() -> str:
    from services import settings_store

    return (
        os.environ.get("DEEPGRAM_MODEL")
        or settings_store.get_text(_ASR_DEEPGRAM_MODEL_KEY)
        or "nova-2"
    )


def resolve_deepgram_api_key() -> Optional[str]:
    from services import settings_store

    return os.environ.get("DEEPGRAM_API_KEY") or settings_store.get_secret(
        _ASR_DEEPGRAM_SECRET_NAME
    )


def deepgram_has_key() -> bool:
    from services import settings_store

    return bool(os.environ.get("DEEPGRAM_API_KEY")) or (
        _ASR_DEEPGRAM_SECRET_NAME in settings_store.list_secret_names()
    )


def probe_deepgram_server(
    model: str | None = None,
    api_key: str | None = None,
    *,
    timeout_s: float = 8.0,
) -> dict:
    del model
    from time import perf_counter

    import httpx

    from core.scrub import scrub_text

    key = (api_key if api_key is not None else resolve_deepgram_api_key() or "").strip()
    out: dict = {
        "ok": False,
        "status": "not_configured",
        "latency_ms": None,
        "http_status": None,
        "detail": None,
    }
    if not key:
        return out
    started = perf_counter()
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_s, connect=min(5.0, timeout_s))) as client:
            response = client.get(
                "https://api.deepgram.com/v1/projects",
                headers={"Authorization": f"Token {key}"},
            )
    except httpx.TimeoutException as exc:
        out.update(
            status="timeout",
            latency_ms=round((perf_counter() - started) * 1000.0, 1),
            detail=scrub_text(f"{type(exc).__name__}: {exc}"),
        )
        return out
    except Exception as exc:
        out.update(
            status="unreachable",
            latency_ms=round((perf_counter() - started) * 1000.0, 1),
            detail=scrub_text(f"{type(exc).__name__}: {exc}"),
        )
        return out
    out["latency_ms"] = round((perf_counter() - started) * 1000.0, 1)
    out["http_status"] = response.status_code
    if 200 <= response.status_code < 300:
        out.update(ok=True, status="ok")
    elif response.status_code in (401, 403):
        out["status"] = "auth_failed"
    else:
        out.update(status="http_error", detail=scrub_text((response.text or "")[:300]) or None)
    return out


def normalize_deepgram_language(lang: Optional[str]) -> Optional[str]:
    if not lang:
        return None
    cleaned = str(lang).strip()
    lower = cleaned.lower()
    if lower in ("auto", "none", ""):
        return None
    if lower in ("cmn-hans", "zh-cn", "zh-hans", "zh-sg", "chinese-simplified"):
        return "zh-CN"
    if lower in ("cmn-hant", "zh-tw", "zh-hk", "zh-hant", "chinese-traditional"):
        return "zh-TW"
    if lower in ("zh", "chinese", "cmn") or lower.startswith("cmn-"):
        return "zh"
    return cleaned


class DeepgramASRBackend(ASRBackend):
    id = "deepgram-asr"
    display_name = "Deepgram (Cloud API)"
    gpu_compat = ("cpu",)

    def __init__(self):
        self._api_key = resolve_deepgram_api_key()
        self._model = resolve_deepgram_model()

    @classmethod
    def is_available(cls) -> tuple[bool, str]:
        if not resolve_deepgram_api_key():
            return False, "Configure a Deepgram API key in Model Catalogue → Engines"
        return True, "ready"

    def transcribe(
        self,
        audio_path: str,
        *,
        word_timestamps: bool = True,
        language: Optional[str] = None,
        **kwargs,
    ) -> dict:
        del word_timestamps, kwargs
        api_key = (self._api_key or resolve_deepgram_api_key() or "").strip()
        if not api_key:
            raise RuntimeError("Deepgram API key is not configured.")
        model = resolve_deepgram_model() or self._model or "nova-2"
        import httpx
        from core.scrub import scrub_text

        params = {
            "model": model,
            "smart_format": "true",
            "punctuate": "true",
            "diarize": "true",
            "utterances": "true",
        }
        normalized = normalize_deepgram_language(language)
        if normalized:
            params["language"] = normalized
        else:
            params["detect_language"] = "true"
        with open(audio_path, "rb") as handle:
            content = handle.read()
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    "https://api.deepgram.com/v1/listen",
                    params=params,
                    headers={
                        "Authorization": f"Token {api_key}",
                        "Content-Type": "audio/wav",
                    },
                    content=content,
                )
            if response.status_code != 200:
                raw_detail = getattr(response, "text", "") or ""
                detail = scrub_text(raw_detail[:300])
                msg = f"Deepgram API error ({response.status_code})"
                if detail:
                    msg += f": {detail}"
                raise RuntimeError(msg)
            return self._adapt_response(response.json())
        except Exception as exc:
            raise RuntimeError(f"Deepgram transcription failed: {type(exc).__name__}: {exc}") from exc

    @staticmethod
    def _adapt_response(response: dict) -> dict:
        results = response.get("results", {}) if isinstance(response, dict) else {}
        segments: list[dict] = []
        chunks: list[dict] = []
        for utterance in results.get("utterances") or []:
            speaker_index = utterance.get("speaker")
            speaker = f"Speaker {(speaker_index or 0) + 1}"
            words = [
                {
                    "word": word.get("word", ""),
                    "start": float(word.get("start", 0.0)),
                    "end": float(word.get("end", 0.0)),
                    "score": float(word.get("confidence", 1.0)),
                    "speaker": speaker,
                }
                for word in utterance.get("words", [])
            ]
            text = (utterance.get("transcript") or "").strip()
            start = float(utterance.get("start", 0.0))
            end = float(utterance.get("end", start))
            if text:
                chunks.append({"text": text, "timestamp": (start, end)})
                segments.append(
                    {
                        "text": text,
                        "start": start,
                        "end": end,
                        "words": words,
                        "speaker": speaker,
                        "speaker_id": speaker,
                    }
                )
        channels = results.get("channels") or []
        alternative = (channels[0].get("alternatives") or [{}])[0] if channels else {}
        if not segments:
            text = (alternative.get("transcript") or "").strip()
            words = alternative.get("words") or []
            if text:
                start = float(words[0].get("start", 0.0)) if words else 0.0
                end = float(words[-1].get("end", start)) if words else start
                chunks.append({"text": text, "timestamp": (start, end)})
                segments.append({"text": text, "start": start, "end": end, "words": words})
        languages = alternative.get("languages") or []
        language = languages[0] if languages else alternative.get("language", "en")
        return {"chunks": chunks, "segments": segments, "language": language}


_REGISTRY: dict[str, type[ASRBackend]] = {
    "deepgram-asr": DeepgramASRBackend,
}
_INSTALL_HINTS = {"deepgram-asr": "Configure a Deepgram API key in Settings."}
_LAST_ERRORS: dict[str, str] = {}


def list_backends() -> list[dict]:
    from core.device_caps import detect_host_caps
    from core.scrub import scrub_text
    from services.engine_routing import routing_fields

    caps = detect_host_caps()
    output = []
    for backend_id, backend_type in _REGISTRY.items():
        ok, message = backend_type.is_available()
        output.append(
            {
                "id": backend_id,
                "display_name": backend_type.display_name,
                "available": ok,
                "reason": None if ok else scrub_text(message),
                "install_hint": _INSTALL_HINTS[backend_id],
                "last_error": None,
                "isolation_mode": "in-process",
                "gpu_compat": ["cpu"],
                **routing_fields(("cpu",), caps),
            }
        )
    return output


def _auto_detect() -> str:
    return "deepgram-asr"


def active_backend_id() -> str:
    return "deepgram-asr"


def get_active_asr_backend(*, asr_pipe=None) -> ASRBackend:
    del asr_pipe
    return DeepgramASRBackend()


def load_active_asr_backend(*, asr_pipe=None) -> ASRBackend:
    backend = get_active_asr_backend(asr_pipe=asr_pipe)
    ensure_loaded = getattr(backend, "ensure_loaded", None)
    if callable(ensure_loaded):
        ensure_loaded()
    return backend


def get_capture_asr_backend() -> ASRBackend:
    return get_active_asr_backend()


def release_idle_capture_backend(idle_s: float, *, now: float | None = None) -> bool:
    del idle_s, now
    return False


ASR_MODEL_MISSING = "asr_model_missing"


def asr_model_missing_error(
    *, purpose: str = "transcribe", sherpa_model_id: str | None = None, backend_id: str | None = None
) -> dict | None:
    del sherpa_model_id, backend_id
    if resolve_deepgram_api_key():
        return None
    return {
        "error": ASR_MODEL_MISSING,
        "backend": "deepgram-asr",
        "purpose": purpose,
        "detail": "Deepgram Cloud ASR requires an API key. Configure it in Settings.",
        "requires_configuration": True,
    }


def asr_model_missing_detail(payload: dict) -> str:
    return str(payload.get("detail") or "Deepgram Cloud ASR requires configuration.")


def transcribe_reference(audio_path: str) -> str | None:
    if not resolve_deepgram_api_key():
        return None
    try:
        result = get_active_asr_backend().transcribe(audio_path, word_timestamps=False)
        text = " ".join(chunk.get("text", "") for chunk in result.get("chunks", []))
        return text.strip() or None
    except Exception as exc:
        logger.warning("reference transcription failed: %s", exc)
        return None
