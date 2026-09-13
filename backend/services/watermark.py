"""Lightweight provenance seam and optional visible export branding.

The neural watermark provider was removed by the seven-provider boundary.
``mark_synthetic`` remains as the synthesis seam, performs no model loading,
and never changes audio.
"""

from __future__ import annotations

import math

import torch

from core.prefs import resolve


def _check_available() -> bool:
    return False


def release_idle_models(idle_seconds: float, *, now: float | None = None) -> bool:
    del idle_seconds, now
    return False


def is_enabled() -> bool:
    return False


def will_mark() -> bool:
    return False


def mark_synthetic(
    waveform: torch.Tensor,
    sample_rate: int,
    *,
    context: str,
    force: bool = False,
) -> torch.Tensor:
    del sample_rate, context, force
    return waveform


def embed_watermark(
    waveform: torch.Tensor,
    sample_rate: int,
    message: list[int] | None = None,
    *,
    force: bool = False,
) -> torch.Tensor:
    del sample_rate, message, force
    return waveform


def detect_watermark(waveform: torch.Tensor, sample_rate: int) -> dict:
    del waveform, sample_rate
    return {
        "is_watermarked": False,
        "confidence": 0.0,
        "message_bits": "",
        "is_omnivoice": False,
        "error": "Machine-readable watermark detection is not available.",
    }


def is_visible_audio_enabled() -> bool:
    return resolve("watermark.visible_audio", default=False) is True


def is_visible_video_enabled() -> bool:
    return resolve("watermark.visible_video", default=True) is not False


def generate_brand_tone(sample_rate: int = 24000, duration_s: float = 0.4) -> torch.Tensor:
    notes_hz = [523.25, 659.25, 783.99]
    note_dur = duration_s / len(notes_hz)
    samples_per_note = int(note_dur * sample_rate)
    total_samples = samples_per_note * len(notes_hz)
    tone = torch.zeros(1, total_samples)
    t = torch.linspace(0, note_dur, samples_per_note)
    for idx, freq in enumerate(notes_hz):
        envelope = torch.exp(-t * 6.0) * 0.15
        start = idx * samples_per_note
        tone[0, start : start + samples_per_note] = torch.sin(2 * math.pi * freq * t) * envelope
    fade_len = int(total_samples * 0.2)
    if fade_len > 0:
        tone[0, -fade_len:] *= torch.linspace(1.0, 0.0, fade_len)
    return tone


def apply_audio_brand(waveform: torch.Tensor, sample_rate: int) -> torch.Tensor:
    if not is_visible_audio_enabled():
        return waveform
    brand = generate_brand_tone(sample_rate=sample_rate)
    gap = torch.zeros(1, int(0.1 * sample_rate))
    return torch.cat([brand, gap, waveform], dim=-1)


def get_ffmpeg_overlay_args(logo_path: str, duration_s: float = 5.0) -> list[str]:
    del logo_path
    if not is_visible_video_enabled():
        return []
    filter_str = (
        f"[1:v]scale=-1:64,format=rgba,"
        f"fade=t=out:st={duration_s - 1}:d=1:alpha=1[logo];"
        f"[0:v][logo]overlay=W-w-20:H-h-20:enable='lte(t,{duration_s})'"
    )
    return ["-filter_complex", filter_str]
