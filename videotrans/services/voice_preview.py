# -*- coding: utf-8 -*-
"""Voice preview synthesis engine with concurrency lock, 30s timeout, and CPU fallback."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import shutil
import time
from typing import Optional

from videotrans import tts
from videotrans.configure.config import params
from videotrans.core import voice_store
from videotrans.util.help_ffmpeg import runffmpeg

logger = logging.getLogger("videotrans.voice_preview")

_preview_lock = asyncio.Lock()
PREVIEW_TIMEOUT_SECONDS = 30.0

_preview_synthesizer = None


def set_preview_synthesizer(fn):
    """Set custom synthesizer function (useful for tests or mocking)."""
    global _preview_synthesizer
    _preview_synthesizer = fn

DEFAULT_TEXTS = {
    "vi": "Chào bạn, đây là bản nghe thử giọng nói trí tuệ nhân tạo được tổng hợp thành công.",
    "en": "Hello, this is a sample preview of your newly generated custom voice.",
}


def get_default_preview_text(language: str) -> str:
    lang = (language or "").strip().lower()
    if lang.startswith("vi"):
        return DEFAULT_TEXTS["vi"]
    return DEFAULT_TEXTS["en"]


def _run_vieneu_synthesis(ref_audio: Path, output_file: Path, text: str, use_cuda: bool = True) -> None:
    """Run VieNeu TTS inference synchronously, with CPU fallback if CUDA OOM occurs."""
    import soundfile as sf
    from vieneu import Vieneu

    def _infer(device: str, backend: str):
        engine = Vieneu(
            mode="v3turbo",
            device=device,
            backend=backend,
            max_batch_size=1,
        )
        try:
            audios = engine.infer_batch([text], ref_audio=ref_audio.as_posix())
            if not audios or len(audios) == 0:
                raise RuntimeError("VieNeu returned empty audio")
            sf.write(str(output_file), audios[0], engine.sample_rate)
        finally:
            engine.close()

    try:
        if use_cuda:
            try:
                _infer("cuda", "pytorch")
                return
            except Exception as exc:
                exc_msg = str(exc).lower()
                if "out of memory" in exc_msg or "cuda" in exc_msg:
                    logger.warning("CUDA OOM or CUDA error during VieNeu preview synthesis, falling back to CPU: %s", exc)
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except Exception:
                        pass
                else:
                    raise
        # CPU fallback
        _infer("cpu", "onnx")
    except Exception as exc:
        logger.error("VieNeu preview synthesis failed: %s", exc, exc_info=True)
        raise


def _run_omnivoice_synthesis(ref_audio: Path, ref_text: str, output_file: Path, text: str, use_cuda: bool = True) -> None:
    """Run OmniVoice TTS preview synthesis, falling back to CPU if needed."""
    from videotrans.configure.config import ROOT_DIR
    model_dir = Path(ROOT_DIR) / "models" / "models--k2-fsa--OmniVoice"
    if not (model_dir / "model.safetensors").is_file():
        raise FileNotFoundError(f"OmniVoice model not installed at {model_dir}")

    import torch
    import soundfile as sf
    from omnivoice import OmniVoice
    from videotrans.util import gpus

    is_gpu = use_cuda and torch.cuda.is_available()
    device = "cuda:0" if is_gpu else gpus.mps_or_cpu()
    dtype = torch.float16 if is_gpu else torch.float32

    model = OmniVoice.from_pretrained(
        str(model_dir),
        device_map=device,
        dtype=dtype,
    )
    try:
        wav = model.generate(
            text=text,
            ref_audio=ref_audio.as_posix(),
            ref_text=ref_text or None,
            speed=1.0,
        )
        sf.write(str(output_file), wav[0], 24000)
    finally:
        del model
        if is_gpu:
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass


async def synthesize_voice_preview(
    voice_id: str,
    text: Optional[str] = None,
    language: Optional[str] = None,
    use_cuda: bool = True,
    force_refresh: bool = False,
    db_path: Optional[str | Path] = None,
) -> Path:
    """
    Synthesize a single-utterance audio preview for a custom voice.
    Guarded by an asyncio concurrency lock and a 30s timeout.
    """
    voice = voice_store.get_voice(voice_id, db_path=db_path)
    if not voice:
        raise ValueError(f"Voice {voice_id} not found")

    voice_store.init_voice_dirs()
    preview_filename = f"{voice_id}_preview.wav"
    preview_path = voice_store.get_preview_audio_path(preview_filename)

    # 1. Return cached preview if valid and not force_refresh
    if not force_refresh and preview_path.is_file() and preview_path.stat().st_size > 0:
        if preview_path.stat().st_mtime >= voice.get("updated_at", 0):
            return preview_path

    # 2. Determine sample utterance
    lang = language or voice.get("language") or "vi"
    sample_text = (text or "").strip() or get_default_preview_text(lang)

    # 3. Reference audio path
    ref_audio_rel = voice.get("ref_audio_path", "")
    ref_audio_path: Optional[Path] = None
    if ref_audio_rel:
        try:
            ref_audio_path = voice_store.get_voice_audio_path(ref_audio_rel)
            if not ref_audio_path.is_file():
                ref_audio_path = None
        except Exception:
            ref_audio_path = None

    async with _preview_lock:
        # Re-check cache inside lock to avoid redundant concurrent synthesis
        if not force_refresh and preview_path.is_file() and preview_path.stat().st_size > 0:
            if preview_path.stat().st_mtime >= voice.get("updated_at", 0):
                return preview_path

        provider = voice.get("provider", tts.VIENEU_TTS)

        async def _do_synthesis() -> None:
            if _preview_synthesizer is not None:
                await asyncio.to_thread(_preview_synthesizer, voice, preview_path, sample_text)
                return

            # Check if neural engine can be loaded
            if provider == tts.VIENEU_TTS and ref_audio_path:
                try:
                    await asyncio.to_thread(
                        _run_vieneu_synthesis,
                        ref_audio_path,
                        preview_path,
                        sample_text,
                        use_cuda,
                    )
                    return
                except ImportError:
                    logger.info("vieneu package not installed, using reference audio snippet fallback")
                except Exception as exc:
                    logger.warning("VieNeu synthesis error, falling back to snippet preview: %s", exc)

            if provider == tts.OMNIVOICE_TTS and ref_audio_path:
                try:
                    ref_text = voice.get("ref_text", "")
                    await asyncio.to_thread(
                        _run_omnivoice_synthesis,
                        ref_audio_path,
                        ref_text,
                        preview_path,
                        sample_text,
                        use_cuda,
                    )
                    return
                except ImportError:
                    logger.info("omnivoice package not installed, using reference audio snippet fallback")
                except Exception as exc:
                    logger.warning("OmniVoice synthesis error, falling back to snippet preview: %s", exc)

            # Robust fallback: generate 3-second preview snippet from reference audio
            if ref_audio_path and ref_audio_path.is_file():
                target_rate = 48000 if provider == tts.VIENEU_TTS else 24000
                cmd = [
                    "-y",
                    "-ss", "0",
                    "-t", "3",
                    "-i", str(ref_audio_path),
                    "-vn",
                    "-ac", "1",
                    "-ar", str(target_rate),
                    "-acodec", "pcm_s16le",
                    str(preview_path),
                ]
                await asyncio.to_thread(runffmpeg, cmd, force_cpu=True)
                return

            raise RuntimeError(f"No reference audio or engine available to synthesize preview for {voice_id}")

        await asyncio.wait_for(_do_synthesis(), timeout=PREVIEW_TIMEOUT_SECONDS)

        if not preview_path.is_file() or preview_path.stat().st_size == 0:
            raise RuntimeError(f"Preview synthesis produced no output file: {preview_path}")

        # Update voice record with cached preview path
        voice_store.update_voice(voice_id, preview_audio_path=preview_filename, db_path=db_path)

        return preview_path
