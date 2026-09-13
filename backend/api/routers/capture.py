"""
Deepgram transcription endpoint for browser uploads.

Unlike /dub/transcribe/{job_id}, this endpoint is job-free — callers POST
raw audio bytes and get back transcribed text immediately.  Used by:

    • The frontend "Capture" (global hotkey dictation) mode
    • The MCP server's future `transcribe_audio` tool
    • CLI consumers that just want speech-to-text

The sole ASR engine is Deepgram. A missing API key is rejected before any
audio can leave the machine.
"""
from __future__ import annotations

import logging
import os
import tempfile
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from typing import Optional

router = APIRouter()
logger = logging.getLogger("omnivoice.capture")


def _truthy(value: Optional[str]) -> bool:
    """Parse a multipart form flag. Treats '1'/'true'/'yes'/'on'/'auto'
    (any case) as on; everything else — including None — as off."""
    return (value or "").strip().lower() in {"1", "true", "yes", "on", "auto"}


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None),
    refine: Optional[str] = Form(None),
):
    """Transcribe an audio file to text.

    Args:
        audio: The audio file to transcribe.
        language: Optional Deepgram language hint; omitted means auto-detect.
        refine: Opt-in OpenAI-compatible LLM cleanup. Off by default.

    Returns:
        {
            "text": "full transcription",
            "refined_text": "cleaned text",   # only when refine=true changed it
            "segments": [ {"start": 0.0, "end": 1.5, "text": "..."}, ... ],
            "language": "en",
            "duration_s": 4.2,
            "transcription_time_s": 0.8,
            "engine": "deepgram-asr"
        }
    """
    import asyncio

    # Save upload to a temp file (all backends need a file path)
    ext = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    try:
        content = await audio.read()
        tmp.write(content)
        tmp.close()

        from services.asr_backend import asr_model_missing_detail, asr_model_missing_error
        missing = await asyncio.to_thread(asr_model_missing_error)
        if missing is not None:
            raise HTTPException(
                status_code=409,
                detail={**missing, "message": asr_model_missing_detail(missing)},
            )

        def _run():
            from services.asr_backend import load_active_asr_backend
            backend = load_active_asr_backend()
            result = backend.transcribe(tmp.name, word_timestamps=True, language=language)
            return result, backend.id

        from services.model_manager import _gpu_pool
        from services.asr_backend import (
            ASRTimeoutError,
            run_transcribe_guarded,
        )
        t0 = time.perf_counter()
        try:
            result, engine_id = await run_transcribe_guarded(
                _gpu_pool, _run, what="Dictation",
            )
        except ASRTimeoutError as e:
            # Backend is alive — ASR couldn't finish. 504 with guidance, not a
            # silent hang the UI reads as "can't reach the local backend".
            logger.warning("Capture transcription timed out: %s", e)
            raise HTTPException(status_code=504, detail=str(e))
        elapsed = round(time.perf_counter() - t0, 2)

        # Normalize result shape
        segments = result.get("segments", [])
        full_text = result.get("text", "")
        if not full_text and segments:
            full_text = " ".join(s.get("text", "") for s in segments).strip()

        # Remove repetitive recognition artifacts from the final text.
        # Segments keep the raw recognition so their timings stay truthful.
        from services.refinement import collapse_repetitive_artifacts
        full_text = collapse_repetitive_artifacts(full_text)

        # Cross-transport parity: deterministically polish the final text
        # (leading capital + terminal punctuation) exactly like the live
        # dictation socket (capture_ws) does, so the widget's POST fallback and
        # MCP/CLI callers get the same typed-looking result the WS returns —
        # not the raw "...test" the REST path used to leak. Segments stay raw
        # (their timings/verbatim recognition are the contract).
        from services.text_polish import polish_text
        full_text = polish_text(full_text)

        # Calculate audio duration from segments if available
        duration = 0.0
        if segments:
            duration = max(s.get("end", 0) for s in segments)

        detected_lang = result.get("language", language or "unknown")

        # Opt-in Wave 2.1 refinement, mirroring the live-dictation socket
        # (capture_ws). Off-thread (it's a network call, not GPU); never
        # raises — maybe_refine swallows failures and a missing LLM into a
        # None pass-through, so the raw text always stands.
        refined_text = None
        if _truthy(refine) and full_text:
            from services.refinement import maybe_refine
            refined = await asyncio.to_thread(maybe_refine, full_text)
            if refined:
                # Polish the refined text too, so both surfaced strings read as
                # typed text (mirrors the raw-vs-refined contract of the WS).
                refined = polish_text(refined)
                if refined != full_text:
                    refined_text = refined

        logger.info(
            "Capture transcription done: engine=%s, elapsed=%.2fs, duration=%.1fs, mode=%s, refined=%s",
            engine_id, elapsed, duration, "deepgram",
            refined_text is not None,
        )

        response = {
            "text": full_text,
            "segments": [
                {
                    "start": round(s.get("start", 0), 2),
                    "end": round(s.get("end", 0), 2),
                    "text": s.get("text", "").strip(),
                }
                for s in segments
            ],
            "language": detected_lang,
            "duration_s": round(duration, 2),
            "transcription_time_s": elapsed,
            "engine": engine_id,
        }
        if refined_text is not None:
            response["refined_text"] = refined_text
        return response
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
