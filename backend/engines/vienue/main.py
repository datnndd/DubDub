"""VieNeu-TTS sidecar — runs under the vieneu venv, NEVER the parent.

Wire protocol — length-prefixed JSON over stdin/stdout, byte-identical to
``engines/_echo/main.py`` and ``engines/dots_tts/main.py``:

    [ 4-byte big-endian uint32 length ][ N bytes UTF-8 JSON ]

Op flow:
    1. sidecar -> parent: {"op": "ready", "engine": "vienue", "sample_rate": 48000}
    2. parent -> sidecar: {"op": "ping"} -> {"op": "pong", "vram_mb": ...}
    3. parent -> sidecar: {"op": "synthesize", "text": "...",
                           "ref_audio": "/path/ref.wav", "ref_text": "...",
                           "language": "vi", "seed": 12345}
       -> {"op": "progress", ...} (cold load) then
       -> {"op": "audio", "audio_pcm_b64": "...", "sample_rate": 48000,
           "n_samples": N}
    4. parent -> sidecar: {"op": "shutdown"} -> exit 0

Restrictions: NO imports from OmniVoice parent code (different venv). NO
logging of ``os.environ`` contents. Single-frame DoS cap matches the
parent's ``MAX_FRAME_BYTES``. Frames go down a PRIVATE dup'd fd and fd 1 is
redirected to stderr (#1428 — library noise must never corrupt the stream).
"""
from __future__ import annotations

import base64
import json
import os
import struct
import sys
import traceback


# Mirrors backend/services/subprocess_backend.py::MAX_FRAME_BYTES.
MAX_FRAME_BYTES = 64 * 1024 * 1024

#: v3-Turbo emits 48 kHz (vieneu SDK: BaseVieneuTTS/V3Turbo sample_rate).
#: Advertised in the ready frame; the real value is re-read from the
#: loaded engine before each result is emitted.
VIENEU_SAMPLE_RATE = 48000

#: Default checkpoint. v3-Turbo is the current generation (48 kHz, ONNX
#: CPU path). Overridable for air-gapped / mirror installs. License care:
#: keep to Apache-2.0 variants (0.5B / v2-Turbo) — never the CC BY-NC 0.3B.
_DEFAULT_MODEL = "pnnbao-ump/VieNeu-TTS-v3-Turbo"
_DEFAULT_MODE = "v3turbo"

#: Languages the default checkpoint speaks. Overridable together with the
#: model (e.g. OMNIVOICE_VIENEU_MODEL=…v2 + OMNIVOICE_VIENEU_LANGUAGES=vi,en).
_LANGUAGES_ENV = "OMNIVOICE_VIENEU_LANGUAGES"


# ── wire protocol ─────────────────────────────────────────────────────────


def _send(stream, obj: dict) -> None:
    body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    stream.write(struct.pack("!I", len(body)))
    stream.write(body)
    stream.flush()


def _recv(stream):
    header = stream.read(4)
    if len(header) < 4:
        return None  # EOF
    (n,) = struct.unpack("!I", header)
    if n > MAX_FRAME_BYTES:
        raise IOError(f"frame too large: {n}")
    body = bytearray()
    while len(body) < n:
        chunk = stream.read(n - len(body))
        if not chunk:
            raise IOError("short read")
        body.extend(chunk)
    return json.loads(bytes(body).decode("utf-8"))


def _measure_vram_mb() -> float:
    """This sidecar's own GPU memory in MB (MM2-08). 0 on CPU/torch-free.
    Never raises — the v3turbo CPU path has no torch at all."""
    try:
        import torch
        if torch.cuda.is_available():
            return round(torch.cuda.memory_allocated() / (1024 ** 2), 1)
    except Exception:
        pass
    return 0.0


# ── model loading (lazy, on first synthesize) ─────────────────────────────


# Module-level singleton — (tts,). Device is auto-selected inside the vieneu
# SDK (v3turbo: ONNX Runtime on CPU, PyTorch when CUDA is present).
_tts = None


def _load_tts(stdout):
    """Cold-construct the VieNeu engine."""
    global _tts
    if _tts is not None:
        return _tts

    _send(stdout, {"op": "progress", "stage": "loading_model", "percent": 0})

    from vieneu import Vieneu  # type: ignore[import-not-found]

    mode = os.environ.get("OMNIVOICE_VIENEU_MODE", _DEFAULT_MODE)
    model = os.environ.get("OMNIVOICE_VIENEU_MODEL", _DEFAULT_MODEL)
    device = os.environ.get("OMNIVOICE_VIENEU_DEVICE", "auto")

    _send(stdout, {"op": "progress", "stage": "loading_model", "percent": 50})

    _tts = Vieneu(mode=mode, backbone_repo=model, device=device)

    _send(stdout, {"op": "progress", "stage": "loading_model", "percent": 100})
    return _tts


def _allowed_languages() -> set:
    raw = os.environ.get(_LANGUAGES_ENV, "")
    langs = {s.strip().lower() for s in raw.split(",") if s.strip()}
    return langs or {"vi"}


def _check_language(raw) -> None:
    """Reject languages the configured checkpoint cannot speak, naming the
    engine and the way out (issue #1257 class — a bare code list helps nobody)."""
    if not raw or not isinstance(raw, str):
        return
    lang = raw.strip().lower()
    if not lang or lang == "auto":
        return
    allowed = _allowed_languages()
    if lang not in allowed and lang.split("-")[0] not in allowed:
        raise ValueError(
            f"VieNeu-TTS speaks {', '.join(sorted(allowed))} — language "
            f"'{raw}' is not supported by this engine. Switch engines in the "
            "Model Catalogue (OmniVoice covers 600+ languages), or set "
            f"{_LANGUAGES_ENV} if you are running a multilingual checkpoint."
        )


def _apply_seed(seed) -> None:
    """Seed every RNG the SDK stack may touch. torch is guarded: the
    v3turbo CPU path (ONNX Runtime) has no torch installed at all."""
    try:
        import random
        random.seed(int(seed))
    except Exception:
        pass
    try:
        import numpy as np
        np.random.seed(int(seed) % (2 ** 32))
    except Exception:
        pass
    try:
        import torch
        torch.manual_seed(int(seed))
    except Exception:
        pass


def _to_pcm_b64(audio, sample_rate: int) -> tuple[str, int, int]:
    """Convert a waveform (torch tensor or numpy array) in [-1, 1] to
    base64 int16 PCM."""
    import numpy as np

    if hasattr(audio, "detach"):
        arr = audio.detach().to("cpu").float().numpy()
    else:
        arr = np.asarray(audio, dtype=np.float32)
    arr = np.asarray(arr, dtype=np.float32).squeeze()
    while arr.ndim > 1:
        # Downmix along the channel axis (never across time — #1328).
        arr = arr.mean(axis=int(np.argmin(arr.shape)))
    arr = np.clip(arr, -1.0, 1.0)
    pcm = (arr * 32767.0).astype(np.int16).tobytes()
    return base64.b64encode(pcm).decode("ascii"), int(sample_rate), int(arr.shape[0])


def _handle_synthesize(msg: dict, stdout) -> None:
    """Dispatch one synthesize request. Emits the audio frame or raises."""
    text = msg.get("text")
    if not text or not isinstance(text, str):
        raise ValueError("synthesize: missing or non-string 'text'")

    _check_language(msg.get("language"))
    seed = msg.get("seed")
    if seed is not None:
        _apply_seed(int(seed))

    tts = _load_tts(stdout)

    gen_kwargs: dict = {"text": text}
    ref_audio = msg.get("ref_audio")
    if ref_audio:
        gen_kwargs["ref_audio"] = ref_audio
        ref_text = msg.get("ref_text")
        if ref_text:
            # v3turbo resolves the voice from the clip alone and takes no
            # ref_text; transcript-conditional modes (standard) do take it.
            if os.environ.get("OMNIVOICE_VIENEU_MODE", _DEFAULT_MODE) in ("standard", "turbo"):
                gen_kwargs["ref_text"] = ref_text
            else:
                print("[vienue] v3turbo: ref_text ignored (voice comes from the clip)",
                      file=sys.stderr)
    else:
        # No reference clip → the SDK falls back to its built-in default voice.
        print("[vienue] synthesize without ref_audio; using the built-in default voice",
              file=sys.stderr)

    audio = tts.infer(**gen_kwargs)
    sample_rate = int(getattr(tts, "sample_rate", VIENEU_SAMPLE_RATE))

    pcm_b64, sr, n_samples = _to_pcm_b64(audio, sample_rate)
    _send(stdout, {
        "op": "audio",
        "audio_pcm_b64": pcm_b64,
        "sample_rate": sr,
        "n_samples": n_samples,
    })


# ── main loop ─────────────────────────────────────────────────────────────


def main() -> int:
    stdin = sys.stdin.buffer
    # Frames go down a PRIVATE fd, and fd 1 is pointed at stderr (#1428) —
    # the vieneu stack logs freely to fd 1, and four bytes of log text read
    # as a length prefix is how a generation dies with
    # `OSError: frame too large: <ascii>`.
    _frame_fd = os.dup(1)
    os.dup2(2, 1)
    stdout = os.fdopen(_frame_fd, "wb")

    # Ready handshake fires BEFORE any heavy import.
    _send(stdout, {
        "op": "ready",
        "engine": "vienue",
        "sample_rate": VIENEU_SAMPLE_RATE,
    })

    while True:
        try:
            msg = _recv(stdin)
        except Exception as exc:
            _send(stdout, {
                "op": "error",
                "stage": "recv",
                "message": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            })
            return 1
        if msg is None:
            return 0

        op = msg.get("op") if isinstance(msg, dict) else None
        try:
            if op == "ping":
                _send(stdout, {"op": "pong", "vram_mb": _measure_vram_mb()})
            elif op == "synthesize":
                _handle_synthesize(msg, stdout)
            elif op == "shutdown":
                return 0
            else:
                _send(stdout, {
                    "op": "error",
                    "stage": "dispatch",
                    "message": f"unknown op: {op!r}",
                })
        except Exception as exc:
            _send(stdout, {
                "op": "error",
                "stage": op or "unknown",
                "message": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            })


if __name__ == "__main__":
    sys.exit(main())
