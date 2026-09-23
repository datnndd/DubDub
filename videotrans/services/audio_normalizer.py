# -*- coding: utf-8 -*-
"""Audio normalization and duration validation service for custom voice cloning."""
from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import sys
from typing import Optional

from videotrans import tts
from videotrans.configure.excepts import FFmpegError
from videotrans.util.help_ffmpeg import runffmpeg, runffprobe, get_audio_time

logger = logging.getLogger("videotrans.audio_normalizer")

# Model-specific audio standards
PROVIDER_SAMPLE_RATES = {
    tts.ELEVENLABS_TTS: 44100,
    tts.OMNIVOICE_TTS: 24000,
    tts.VIENEU_TTS: 48000,
    tts.GEMINI_TTS: 24000,
}
DEFAULT_SAMPLE_RATE = 48000

MIN_REFERENCE_DURATION_SEC = 2.0
MAX_REFERENCE_DURATION_SEC = 30.0


def get_target_sample_rate(provider: int) -> int:
    """Return target sample rate based on TTS engine requirements."""
    return PROVIDER_SAMPLE_RATES.get(provider, DEFAULT_SAMPLE_RATE)


def probe_audio_duration(file_path: str | Path) -> float:
    """
    Measure audio file duration in seconds using soundfile or ffprobe.
    Raises ValueError if duration cannot be determined.
    """
    p = Path(file_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {p}")

    # Method 1: Try soundfile first (fast, header-based, no process spawn)
    try:
        import soundfile as sf
        with sf.SoundFile(str(p)) as f:
            if f.samplerate > 0 and len(f) > 0:
                duration = len(f) / float(f.samplerate)
                if duration > 0:
                    return duration
    except Exception:
        pass

    # Method 2: Try built-in get_audio_time (ms)
    try:
        ms = get_audio_time(str(p))
        if ms > 0:
            return ms / 1000.0
    except Exception:
        pass

    # Method 3: Direct ffprobe format=duration fallback
    try:
        out = runffprobe([
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(p),
        ])
        if out and out.strip():
            val = float(out.strip())
            if val > 0:
                return val
    except Exception as exc:
        logger.warning(f"Direct ffprobe duration check failed for {p}: {exc}")

    raise ValueError(f"Could not determine audio duration for {p.name}")


def normalize_reference_audio(
    input_path: str | Path,
    output_path: str | Path,
    provider: int = tts.VIENEU_TTS,
    min_duration: float = MIN_REFERENCE_DURATION_SEC,
    max_duration: float = MAX_REFERENCE_DURATION_SEC,
) -> dict:
    """
    Validate audio duration (2.0s - 30.0s) and transcode to pristine 16-bit mono PCM WAV
    at the target sample rate appropriate for the given TTS provider.

    Returns dict with audio metadata:
        {"duration": float, "sample_rate": int, "channels": 1, "format": "pcm_s16le"}
    """
    src = Path(input_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Source audio file not found: {src}")

    duration = probe_audio_duration(src)
    if duration < min_duration or duration > max_duration:
        raise ValueError(
            f"Audio duration must be between {min_duration:.1f} and {max_duration:.1f} seconds (got {duration:.2f}s)"
        )

    target_rate = get_target_sample_rate(provider)
    dest = Path(output_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "-y",
        "-i", str(src),
        "-vn",
        "-ac", "1",
        "-ar", str(target_rate),
        "-acodec", "pcm_s16le",
        str(dest),
    ]

    try:
        runffmpeg(cmd, force_cpu=True)
    except Exception as exc:
        logger.exception(f"Audio normalization failed for {src}: {exc}", exc_info=True)
        raise FFmpegError(f"Audio normalization failed: {exc}") from exc

    if not dest.is_file() or dest.stat().st_size == 0:
        raise RuntimeError(f"Transcoded output WAV was not generated: {dest}")

    return {
        "duration": round(duration, 3),
        "sample_rate": target_rate,
        "channels": 1,
        "format": "pcm_s16le",
    }
