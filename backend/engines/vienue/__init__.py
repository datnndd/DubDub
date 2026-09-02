"""VieNeu-TTS sidecar package — Vietnamese instant voice cloning.

VieNeu-TTS (github.com/pnnbao97/VieNeu-TTS, PyPI ``vieneu``) is a Vietnamese
fine-tune of NeuTTS Air (Qwen 0.5B backbone): instant voice cloning from a
short reference clip, 48 kHz output, runs CPU (ONNX Runtime — the default
``v3turbo`` mode is torch-free) or GPU (PyTorch). Windows-capable.

It runs in its own subprocess **and its own venv** (the same isolation
primitive as dots.tts / MOSS / IndexTTS2): ``vieneu`` pulls its own GGUF/ONNX
runtime + ``sea_g2p`` phonemizer stack that must not fight the parent's pins.

Cross-platform honesty: the upstream SDK documents Windows/Linux/macOS for
the NeuTTS family, and the ``v3turbo`` mode needs no torch on CPU — but the
exact RAM/runtime claims still carry a "verify on your machine" note in
``docs/engines/vieneu-tts.md`` until benchmarked here.

License care (hard rule for the catalogue): only the **Apache-2.0** variants
are whitelisted — ``VieNeu-TTS`` 0.5B and ``VieNeu-TTS-v2-Turbo``. The 0.3B
checkpoints are CC BY-NC 4.0 (non-commercial) and must never be shipped or
recommended. The plain ``v2`` variant's license is unverified — check the HF
card before offering it.

Three public entry points: ``VieNueBackend`` (this module), ``main.py``
(sidecar, runs under the vieneu venv — never imported by the parent), and
``bootstrap.py`` (venv probe + lazy bootstrap).
"""
from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

from services.subprocess_backend import SubprocessBackend

if TYPE_CHECKING:
    import torch  # noqa: F401

logger = logging.getLogger("omnivoice.vienue")


class VieNueBackend(SubprocessBackend):
    """VieNeu-TTS — Vietnamese instant voice cloning, 48 kHz, CPU/GPU.

    Runs in a long-lived sidecar over length-prefixed JSON-over-stdio in a
    dedicated venv (``pip install vieneu``). Weights download from
    HuggingFace on first synthesize.

    Modes (env ``OMNIVOICE_VIENEU_MODE``, default ``v3turbo``):

    * ``v3turbo`` — VieNeu-TTS-v3-Turbo, 48 kHz, CPU via ONNX Runtime
      (torch-free) / GPU via PyTorch. Voice comes from the reference clip
      alone (no transcript needed on the wire; the parent still sends it and
      this sidecar ignores it in this mode).
    * ``standard`` — 0.5B GGUF/PyTorch; cloning is transcript-conditional
      (``ref_text`` forwarded).

    Installation::

        uv venv backend/engines/vienue/.venv
        uv pip install --python backend/engines/vienue/.venv/Scripts/python.exe vieneu

    (Windows path; macOS/Linux use ``.venv/bin/python``). Or simply select
    the engine — the venv auto-installs from PyPI on first use when ``uv``
    is available. License: whitelist Apache-2.0 variants only (0.5B /
    v2-Turbo); never the CC BY-NC 0.3B.
    """

    id = "vienue"
    display_name = "VieNeu-TTS (Vietnamese instant voice clone, CPU/GPU, 48 kHz)"
    supports_voice_design = False  # no description-driven voice design surface
    supports_cloning = True  # explicit: the whole voice-management UI gates on this
    # v3-Turbo emits 48 kHz (verified from the vieneu SDK: sample_rate = 48_000).
    _DEFAULT_SAMPLE_RATE = 48000
    gpu_compat = ("cuda", "cpu")

    # ── availability ───────────────────────────────────────────────────────

    @classmethod
    def is_available(cls) -> tuple[bool, str]:
        # Do NOT import vieneu here: it belongs to the sidecar venv, not the
        # parent interpreter — the reason for the subprocess isolation.
        # Verify the venv on disk only; a real health-check is gated on the
        # user's "Test engine" action in Settings.
        from engines.vienue.bootstrap import (
            VIENEU_SIDECAR_SCRIPT,
            is_vieneu_installed,
        )
        if not is_vieneu_installed():
            return False, (
                "VieNeu-TTS venv not found. Create it once with: "
                "uv venv backend/engines/vienue/.venv && uv pip install "
                "--python backend/engines/vienue/.venv/Scripts/python.exe "
                "vieneu (Windows; macOS/Linux use .venv/bin/python) — or just "
                "select this engine and let VoiceStudio auto-install `vieneu` "
                "from PyPI on first use (needs uv). Model weights download "
                "from HuggingFace on first synthesize. License: Apache-2.0 "
                "variants only (0.5B / v2-Turbo; never the CC BY-NC 0.3B). "
                "See docs/engines/vieneu-tts.md."
            )
        if not VIENEU_SIDECAR_SCRIPT.exists():
            return False, (
                "VieNeu-TTS sidecar script missing at "
                f"{VIENEU_SIDECAR_SCRIPT} — reinstall VoiceStudio."
            )
        return True, "ok (CPU via ONNX Runtime; GPU via PyTorch when CUDA is present)"

    @classmethod
    def venv_python(cls):
        from engines.vienue.bootstrap import resolve_vieneu_venv
        return resolve_vieneu_venv()

    @classmethod
    def sidecar_script(cls):
        from engines.vienue.bootstrap import VIENEU_SIDECAR_SCRIPT
        return VIENEU_SIDECAR_SCRIPT

    # ── TTSBackend protocol ────────────────────────────────────────────────

    @property
    def sample_rate(self) -> int:
        return self._DEFAULT_SAMPLE_RATE

    @property
    def supported_languages(self) -> list[str]:
        # v3-Turbo speaks Vietnamese; v2 adds English. Overridable for users
        # running a different checkpoint via OMNIVOICE_VIENEU_MODEL.
        raw = os.environ.get("OMNIVOICE_VIENEU_LANGUAGES", "")
        langs = [s.strip().lower() for s in raw.split(",") if s.strip()]
        return langs or ["vi"]

    # ── generate (parent-side arbitration) ─────────────────────────────────

    def generate(self, text: str, **kw) -> "torch.Tensor":
        """Synthesize one utterance through the VieNeu sidecar.

        kwargs honored:
          * ``ref_audio`` — reference clip path (instant voice cloning).
            Optional: without it the model falls back to its built-in
            default voice.
          * ``ref_text``  — the reference transcript. Forwarded only in
            transcript-conditional modes (``standard``); ``v3turbo`` resolves
            the voice from the clip alone and ignores it.
          * ``language``  — validated against :attr:`supported_languages` both
            here and again inside the sidecar (defense in depth).
          * ``seed``      — forwarded when the caller provides it (seeded
            generation; the parent's in-process ``torch.manual_seed`` never
            reaches a subprocess sidecar).

        ``instruct`` / ``description`` / ``num_step`` / ``guidance_scale`` /
        ``speed`` / ``denoise`` / ``postprocess_output`` are ignored with a
        log line — VieNeu has no voice-design surface and its sampling knobs
        live inside the SDK (ignore-and-log, never crash: KittenTTS pattern).

        Returns a tensor of shape (1, n_samples) at :attr:`sample_rate`.
        """
        forwarded: dict = {}

        ref_audio = kw.get("ref_audio")
        if ref_audio:
            forwarded["ref_audio"] = ref_audio
            ref_text = kw.get("ref_text")
            if ref_text:
                forwarded["ref_text"] = ref_text
        elif kw.get("ref_text"):
            logger.info(
                "vienue: ref_text supplied without ref_audio; ignoring "
                "(cloning needs the reference clip)."
            )

        language = kw.get("language")
        if language:
            lang = str(language).strip().lower()
            # Reject BEFORE the sidecar spawns, with the phrasing
            # _language_rejection_or() matches ("language not supported") so
            # the rewritten error names this engine + the way out. Raising a
            # bare RuntimeError from the sidecar used to die as the generic
            # "Generation failed. Check the selected engine and try again."
            # with zero context (found 2/9 — the engine only speaks what
            # supported_languages declares).
            if lang and lang != "auto" and lang.split("-")[0] not in self.supported_languages:
                raise ValueError(
                    f"language not supported: '{language}' — VieNeu-TTS speaks "
                    f"{', '.join(self.supported_languages)}. Switch engines in "
                    "Model Catalogue → Engines (OmniVoice covers 600+ "
                    "languages), or generate Vietnamese text."
                )
            forwarded["language"] = str(language)

        seed = kw.get("seed")
        if seed is not None:
            forwarded["seed"] = int(seed)

        dropped = [
            k for k in ("instruct", "description", "num_step", "guidance_scale",
                        "speed", "denoise", "postprocess_output")
            if kw.get(k) not in (None, False)
        ]
        if dropped:
            logger.info(
                "vienue: ignoring params the engine does not support: %s",
                ", ".join(dropped),
            )

        return super().generate(text, **forwarded)


__all__ = ["VieNueBackend"]
