"""
TTS adapter interface — Phase 3.1 (ROADMAP.md).

A uniform protocol for every TTS engine. Today we ship:

    • OmniVoiceBackend — wraps the current k2-fsa/OmniVoice model. Zero
      behaviour change for existing callers.
    • VoxCPM2Backend   — thin stub that raises with a clear install hint
      until `pip install "voxcpm>=2.0.3"` is present and enabled.

Callers should use `get_active_tts_backend()` to pick the configured engine
instead of importing a specific class. The selection is controlled by the
`OMNIVOICE_TTS_BACKEND` env var (default: `"omnivoice"`).

The protocol deliberately stays narrow: `generate(...)` returns a 1-channel
tensor sampled at `sample_rate`. Streaming is left for a later pass — the
dub generator consumes whole segments today.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from contextlib import contextmanager
from typing import Optional

import torch

logger = logging.getLogger("omnivoice.tts")


# ── HF token leak mitigation (Plan 02-04, T-02-12) ─────────────────────────
#
# Token shape is ``hf_`` + 30+ alphanumeric chars per Hugging Face's own
# format. Any error / status string surfaced through the engines API gets
# scrubbed via :func:`_mask_hf_tokens` before serialization so that a
# backend whose ``is_available()`` interpolates ``HF_TOKEN`` into its
# failure message can't accidentally leak it to the frontend. Phase 1's
# ``HFTokenRedactor`` covers logging only — FastAPI response bodies do
# NOT run through the logging filter chain.
_HF_TOKEN_MASK_RE = re.compile(r"hf_[A-Za-z0-9]{30,}")
_HF_TOKEN_MASK = "hf_***REDACTED***"


def _mask_hf_tokens(value):
    """Return ``value`` with any HF-shaped token substring redacted.

    Non-string values pass through unchanged. Used inside
    :func:`list_backends` for the ``reason`` and ``last_error`` fields.
    """
    if not isinstance(value, str):
        return value
    return _HF_TOKEN_MASK_RE.sub(_HF_TOKEN_MASK, value)


def _available_hint(msg) -> Optional[str]:
    """Advisory text carried by an *available* engine's ``is_available()``
    message, or None when the message is a plain readiness echo.

    Convention (established by VoxCPM2's version-floor hint): an engine
    that is available but wants the user to know something returns
    ``(True, "ready — <advice>")``. This extracts ``<advice>`` so
    :func:`list_backends` can surface it — previously the whole message
    was dropped for available rows (``reason`` is None when ok), so
    upgrade hints never reached the UI. Plain "ready" / "ready (…)"
    messages yield None. Output is token-masked like ``reason``.
    """
    if not isinstance(msg, str):
        return None
    head, sep, advice = msg.partition(" — ")
    advice = advice.strip()
    if not sep or not advice or not head.strip().lower().startswith("ready"):
        return None
    return _mask_hf_tokens(advice)


# ── HF Hub closed-client recovery (#880) ────────────────────────────────────
#
# huggingface_hub ≥1.x shares ONE global httpx client across every download.
# If anything closes it mid-lifecycle, every later hub call — e.g. an engine's
# first-use model download inside the generate path — dies with httpx's
# "Cannot send a request, as the client has been closed". The client is
# recoverable: ``close_session()`` drops it and the next hub call builds a
# fresh one, so the correct handling is a single targeted retry, not a
# user-facing failure.


def _is_closed_client_error(e) -> bool:
    """True iff ``e`` (or anything in its __cause__/__context__ chain) is
    httpx's closed-client lifecycle error. Cycle-safe."""
    seen, stack = set(), [e]
    while stack:
        exc = stack.pop()
        if exc is None or id(exc) in seen:
            continue
        seen.add(id(exc))
        low = str(exc).lower()
        if "client has been closed" in low or "cannot send a request" in low:
            return True
        stack.append(exc.__cause__)
        stack.append(exc.__context__)
    return False


def _retry_once_with_fresh_hf_client(loader, what: str):
    """Run ``loader()`` — a model constructor that may download from the HF
    Hub on first use — retrying transient download failures.

    Two failure shapes are retried, with deliberately different budgets:

    * the httpx **closed-client** lifecycle error (#880) — retried exactly
      ONCE, after resetting the hub's shared session. It's a client-state bug,
      not a network condition: if a fresh session hits it again, repeating
      won't help, and #880 chose to surface it rather than loop.
    * any **transient download** failure ``core.failure
      .is_hf_connectivity_error`` recognises — refused/reset connections, DNS,
      timeouts, and (#1224) a truncated body ("peer closed connection without
      sending complete message body"). A multi-GB model that dies at 90% is
      the single most retry-worthy failure in the path, so this gets the full
      bounded budget. The HF cache is resumable (correctly-sized blobs are
      skipped by hash), so each retry continues rather than restarting.

    Anything unrecognised propagates untouched, where the generation error
    classifier labels it.
    """
    from core.failure import is_hf_connectivity_error

    attempts = max(1, _int_env("OMNIVOICE_MODEL_LOAD_RETRIES", 3))
    backoff = max(0.0, _float_env("OMNIVOICE_MODEL_LOAD_BACKOFF_S", 2.0))
    client_reset_used = False
    attempt = 0
    while True:
        try:
            return loader()
        except Exception as e:
            if _is_closed_client_error(e):
                if client_reset_used:
                    raise  # #880: single-shot — a second one is not transient
                client_reset_used = True
                logger.warning(
                    "%s: HF Hub httpx client was closed mid-download (%s); "
                    "retrying once with a fresh client.", what, e,
                )
                try:
                    from huggingface_hub.utils import close_session
                    close_session()
                except Exception:  # pragma: no cover — hub too old / renamed
                    logger.warning(
                        "%s: couldn't reset the HF Hub client; retrying anyway.",
                        what,
                    )
                # Deliberately does NOT consume a download attempt: the two
                # budgets are independent, and letting the session reset eat
                # one left a resumable multi-GB download a retry short of its
                # configured budget (#1224 review).
                continue  # immediate — nothing to back off from
            attempt += 1
            if not is_hf_connectivity_error(str(e)) or attempt >= attempts:
                raise
            logger.warning(
                "%s: model download failed (%s); retrying (attempt %d/%d). "
                "Already-downloaded files are reused.",
                what, e, attempt, attempts,
            )
            if backoff:
                import time as _time
                _time.sleep(backoff * attempt)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    # inf/nan parse fine and then poison the caller: `sleep(inf)` raises
    # OverflowError, turning a retryable download failure into an unrelated
    # crash that hides the original error (#1224 review).
    if value != value or value in (float("inf"), float("-inf")):
        return default
    return value


# ── Protocol ────────────────────────────────────────────────────────────────


class TTSInputError(ValueError):
    """The caller-supplied text can't be synthesized by the selected engine
    (empty / nothing speakable after cleanup). Subclasses ValueError so the
    native /generate route's existing ValueError→400 mapping applies;
    /v1/audio/speech maps it to 400 explicitly (#1173 class — these used to
    surface as opaque 500s like "need at least one array to concatenate")."""


class TTSBackend(ABC):
    """Every TTS engine exposes the same surface, regardless of vendor."""

    #: Unique id for config + UI (e.g. "omnivoice", "voxcpm2").
    id: str = "base"

    #: Human-readable name for the UI.
    display_name: str = "Base TTS"

    #: Output sample rate. May differ per engine (OmniVoice = 24k, VoxCPM2 = 48k).
    @property
    @abstractmethod
    def sample_rate(self) -> int: ...

    #: Languages the engine supports (ISO codes or "multi").
    @property
    @abstractmethod
    def supported_languages(self) -> list[str]: ...

    #: Whether this engine can actually run in the current environment.
    #: Callers use this to fail fast with a clear message instead of loading
    #: a backend that will blow up on first call.
    @classmethod
    @abstractmethod
    def is_available(cls) -> tuple[bool, str]:
        """Return (ok, message). message explains why not, if not."""

    #: Whether this engine supports voice design from a text description
    #: (e.g. "young female, warm tone, British accent") without reference audio.
    supports_voice_design: bool = False

    #: Whether this engine understands the graded-emotion generate kwargs
    #: (``emo_vector`` / ``emo_text`` + ``use_emo_text`` / ``emo_alpha``).
    #: Surfaced via ``list_backends()`` so UI surfaces (the Audiobook expressive
    #: panel, #1208) can show emotion controls ONLY for engines that apply them
    #: — no dead controls. Default False; IndexTTS2 overrides to True. Engines
    #: that don't set it still ignore the kwargs (every generate() takes **kw),
    #: so this is a discoverability hint, not an enforcement gate.
    supports_emotion: bool = False

    def ensure_ready(self) -> None:
        """Load model weights now (blocking), so callers can separate the
        LOAD budget from the GENERATE budget (#1033/#1037 class).

        Every adapter lazily loads inside ``generate()`` via a private
        ``_ensure_loaded()`` — which meant a cold first call spent its whole
        ``OMNIVOICE_GENERATE_TIMEOUT_S`` window (default 300s) downloading /
        loading weights and got killed with a misleading "too heavy for the
        available compute" error (measured in the wild on a fresh install:
        multi-GB checkpoint download, 0% GPU util, #1014). Routes call this
        first under the model-load budget (``OMNIVOICE_MODEL_LOAD_TIMEOUT``,
        default 1200s), then start the generate clock on an already-warm
        engine. Default implementation dispatches to the adapter's own
        ``_ensure_loaded`` when present; engines without lazy state no-op.
        Must be called on the GPU pool (it's blocking), same as generate.
        """
        loader = getattr(self, "_ensure_loaded", None)
        if callable(loader):
            loader()

    #: Whether this engine already emits mastered, studio-grade audio and should
    #: therefore skip the shared apply_mastering() chain (highpass + Compressor,
    #: tuned for OmniVoice's 24 kHz output). Studio engines like VoxCPM2 (native
    #: 48 kHz) set this True so their clean output isn't pumped. Loudness
    #: normalisation is applied regardless — it's a benign peak scale.
    applies_own_mastering: bool = False

    #: Whether this engine can clone an arbitrary voice from reference audio
    #: (`ref_audio=`), as opposed to only offering a fixed set of preset
    #: voices. Default True — most engines clone. Dub/batch gate on this
    #: (issue #312 class) before committing to a job that needs it, instead
    #: of silently falling back to OmniVoice or mis-cloning per segment.
    supports_cloning: bool = True

    #: GPU/accelerator targets the engine can run on. Surfaced via the
    #: Engine Compatibility Matrix (Plan 02-04 / ENGINE-06) so users can
    #: tell at a glance which engines will use their hardware. Defaults to
    #: CPU-only — subclasses override with the union of devices their
    #: implementation supports (cuda / mps / rocm / cpu). This is metadata,
    #: not enforced — actual device selection lives in the engine's loader.
    gpu_compat: tuple[str, ...] = ("cpu",)

    #: Approximate VRAM (GB) the engine needs to render comfortably on a
    #: dedicated GPU. Metadata, like ``gpu_compat`` — never enforced, because a
    #: hard refuse would block hosts that would actually cope (drivers page to
    #: system RAM, and a short input can fit where a long one won't).
    #:
    #: What it IS for: telling the user BEFORE they wait (#1226/#1222). Two
    #: users on 4 GB cards (GTX 1650 Ti, Quadro P2000) ran the `omnivoice`
    #: engine, waited out the full compute budget, and were told the job "was
    #: too heavy for the available compute" — after the fact, with no hint
    #: that their card was under-provisioned for the engine they'd picked.
    #: Routing showed a clean green "accelerated" the whole time, because
    #: family membership was the only thing anything checked.
    #:
    #: 0 means "no meaningful floor" (CPU-class engines) and never warns.
    min_vram_gb: float = 0.0

    @abstractmethod
    def generate(
        self,
        text: str,
        *,
        ref_audio: Optional[str] = None,
        ref_text: Optional[str] = None,
        instruct: Optional[str] = None,
        language: Optional[str] = None,
        duration: Optional[float] = None,
        description: Optional[str] = None,
        num_step: int = 16,
        guidance_scale: float = 2.0,
        speed: float = 1.0,
        **extras,
    ) -> torch.Tensor:
        """Synthesize `text`. Returns a tensor of shape (1, n_samples).

        When `description` is provided and `ref_audio` is None, engines that
        support voice design will create a synthetic voice matching the
        description (e.g. "young female, warm, slight British accent").
        Engines that don't support this will ignore the parameter.
        """

    # ── Lifecycle (Phase 2 will enforce per-engine overrides) ──────────────
    #
    # Today every backend lazily loads its weights on first `generate()` and
    # keeps them in VRAM for the lifetime of the process. Switching engines
    # in Settings therefore leaks the old engine's allocations until the
    # next process restart — measurable on multi-engine sessions on 8 GB
    # MPS Macs.
    #
    # `unload()` is the contract that lets the registry release an engine
    # before instantiating the next one. It is a default no-op on the ABC
    # so this commit does not break any of the 9 existing subclasses; Phase
    # 2 (engine isolation) overrides it per-engine and adds a CI gate that
    # fails when a subclass doesn't implement it.
    #
    # Contract for overriders:
    #   • Idempotent: calling unload() twice must not raise.
    #   • Synchronous: returns after VRAM is freed (or after best-effort
    #     `torch.cuda.empty_cache()` / `torch.mps.empty_cache()`).
    #   • Safe to call before the first generate(): a backend that never
    #     loaded has nothing to release.
    # Attribute(s) that hold this backend's heavy model, cleared by the default
    # unload(). Every in-process engine loads its weights lazily into one of
    # these in `_ensure_loaded()`; the next generate() re-runs that loader. An
    # engine that holds its model elsewhere (or nowhere — e.g. an external HTTP
    # server) overrides `unload()` or leaves these unset. OmniVoice overrides
    # entirely (it drives the shared model_manager singleton).
    _MODEL_ATTRS: tuple[str, ...] = ("_model", "_tts")

    def unload(self) -> None:
        """Release the heavy model this backend holds, and free device caches.

        Called by the registry on engine switch, by the single-active-engine
        eviction (services.engine_memory), and on app shutdown. Clears each of
        ``_MODEL_ATTRS`` that is set on this instance, then empties the device
        cache — so switching engines actually hands the memory back instead of
        leaving the old model resident until GC (the 16 GB-Mac OOM class). The
        next generate() lazily reloads. Idempotent and safe before first load:
        a backend that never loaded has every attr already None/absent.
        """
        freed = False
        for attr in self._MODEL_ATTRS:
            if getattr(self, attr, None) is not None:
                setattr(self, attr, None)
                freed = True
        if freed:
            try:
                from services.model_manager import free_vram

                free_vram()
            except Exception:  # noqa: BLE001 — unload must never raise (idempotent contract)
                pass
        return None


# ── OmniVoice adapter (the current default) ─────────────────────────────────


# ── Voice-clone prompt cache (#427) ──────────────────────────────────────────
# Every cloned generation re-encodes the reference audio from scratch — a fixed
# per-request latency that compounds on batch/long-form workloads reusing one
# voice. The OmniVoice model exposes create_voice_clone_prompt(ref) →
# VoiceClonePrompt + generate(voice_clone_prompt=) to do that encoding ONCE.
# We cache the prompt (bounded LRU, keyed by ref path + mtime + ref_text) so
# repeated generations with the same voice skip the encode. Bounded because a
# VoiceClonePrompt holds tensors (VRAM). Thread-safe (generation runs in a GPU
# thread pool). Best-effort: any miss/error falls back to the inline ref path,
# so output is never affected — this is a pure latency optimization.
_PROMPT_CACHE_MAX = 8
_prompt_cache: "OrderedDict[tuple, object]" = OrderedDict()
_prompt_cache_lock = threading.Lock()


def _clone_prompt_key(ref_audio: str, ref_text, preprocess_prompt: bool = True):
    try:
        mtime = os.path.getmtime(ref_audio)
    except OSError:
        mtime = 0.0
    # preprocess_prompt is part of the key: it changes the encoded prompt
    # (silence removal + trimming + ref-text punctuation, omnivoice.py:675/722),
    # so a False request must not be served a True-encoded prompt — or poison
    # the cache for the True callers. /generate never sets it (always the True
    # default); /v1/audio/speech exposes it.
    return (os.path.abspath(ref_audio), mtime, ref_text or "", bool(preprocess_prompt))


def _get_clone_prompt(
    model, ref_audio: str, ref_text, preprocess_prompt: bool = True, *,
    store: bool = True,
):
    """Return a cached/precomputed ``VoiceClonePrompt`` for
    (ref_audio, ref_text, preprocess_prompt), or ``None`` to fall back to the
    inline ref path. Never raises.

    ``store=False`` still *reads* the cache (a hit is free) but never inserts:
    it exists for single-use references — a dub's per-segment ref clips are each
    a distinct file used exactly once, and inserting a stream of them into an
    LRU of 8 evicts the per-speaker and locked-profile prompts that ARE reused.
    Every short segment falling back to its speaker ref then re-encodes it
    (~0.4 s each, measured). Scan-resistance, not a second cache policy.
    """
    try:
        key = _clone_prompt_key(ref_audio, ref_text, preprocess_prompt)
    except Exception:
        return None
    with _prompt_cache_lock:
        hit = _prompt_cache.get(key)
        if hit is not None:
            _prompt_cache.move_to_end(key)
            return hit
    try:
        # Encode outside the lock (slow). Mirrors exactly what generate() would
        # do inline for this ref (omnivoice.py:964-978), so output is identical.
        prompt = model.create_voice_clone_prompt(
            ref_audio, ref_text=ref_text, preprocess_prompt=preprocess_prompt
        )
    except Exception as e:  # noqa: BLE001 — fall back, never break synthesis
        logger.warning("voice-clone prompt precompute failed; using inline ref: %s", e)
        return None
    if not store:
        return prompt
    with _prompt_cache_lock:
        _prompt_cache[key] = prompt
        _prompt_cache.move_to_end(key)
        while len(_prompt_cache) > _PROMPT_CACHE_MAX:
            _prompt_cache.popitem(last=False)
    return prompt


def generate_with_cached_ref(model, *, ref_audio, ref_text, **gen_kw):
    """``model.generate()`` with the reference clip encoded once, not once per call.

    The native (non-adapter) callers of the OmniVoice model — ``/generate`` and its
    streaming twin, and the audiobook/long-form renderer — used to pass
    ``ref_audio=<path>`` straight through, so the codec encoder re-ran the reference
    on **every generate call**: once per chunk, per pause-span, and per audiobook
    segment, not merely once per request. The prompt cache below (#427/#473) existed
    the whole time but only ``OmniVoiceBackend`` (the adapter path) ever called it,
    and the default engine doesn't take that path.

    This is the one place that knows the rule, so it can't be re-broken piecemeal:
    ``voice_clone_prompt`` and ``ref_audio``/``ref_text`` are **mutually exclusive** —
    pass both and the model warns and ignores the latter (omnivoice.py:957).

    The cache is **best-effort, never load-bearing**: if the prompt can't be built,
    or the model rejects the one we built, we fall back to the inline reference and
    synthesize exactly as before. A latency optimization must never be able to turn
    a generation that would have succeeded into an error.
    """
    # cache_ref=False marks a single-use reference (a dub's per-segment clips):
    # look the cache up, but never insert — see _get_clone_prompt(store=). MUST
    # be popped: the model's generate() has an explicit signature and would
    # TypeError on an unknown kwarg.
    cache_ref = bool(gen_kw.pop("cache_ref", True))
    # Stays in gen_kw too: the model needs it on the inline branch, and it is inert
    # on the prompt branch (that prompt is already encoded).
    preprocess_prompt = bool(gen_kw.get("preprocess_prompt", True))
    prompt = (
        _get_clone_prompt(model, ref_audio, ref_text, preprocess_prompt, store=cache_ref)
        if ref_audio else None
    )
    if prompt is not None:
        try:
            return model.generate(voice_clone_prompt=prompt, **gen_kw)
        except Exception as e:  # noqa: BLE001 — fall back to the inline ref
            logger.warning("voice_clone_prompt generate failed; retrying inline ref: %s", e)
    return model.generate(ref_audio=ref_audio, ref_text=ref_text, **gen_kw)


def clear_clone_prompt_cache() -> None:
    """Drop all cached voice-clone prompts (frees their tensors). Called on model
    unload so a flush/engine-switch doesn't strand VRAM."""
    with _prompt_cache_lock:
        _prompt_cache.clear()


# NB: model_manager.release_tts_side_caches() calls clear_clone_prompt_cache()
# above whenever it drops the TTS model — the prompts belong to that model
# instance and an "unload" that leaves them behind isn't an unload (#1119). It
# reaches this module through sys.modules rather than importing it, so there is
# no import cycle and no import-time side effect here.


class OmniVoiceBackend(TTSBackend):
    """Wraps `omnivoice.models.omnivoice.OmniVoice`. Zero behaviour change.

    Loads lazily on the first `generate` call, mirrors the existing
    `services.model_manager.get_model()` flow: torch.compile on CUDA,
    fp16, ASR co-loaded.
    """

    id = "omnivoice"
    display_name = "VoiceStudio (k2-fsa/OmniVoice, 600+ languages)"
    gpu_compat = ("cuda", "mps", "cpu")
    # Derived from the pool's own per-job budget (_GPU_VRAM_PER_JOB_GB = 5.0 in
    # model_manager, itself measured from the ~1.6 GB forward + autoregressive
    # decode and the co-loaded WhisperX on the clone path), plus room for the
    # resident weights. Below this the driver pages to system RAM and a render
    # that should take seconds runs for minutes — which is precisely what the
    # 4 GB reporters in #1226/#1222 hit. Deliberately the only engine with a
    # floor: the rest have no measured figure, and inventing one would put a
    # confident number in the UI that nothing backs.
    min_vram_gb = 6.0

    def __init__(self, model=None):
        # The live OmniVoice instance. Reuses the singleton owned by
        # model_manager so memory isn't doubled.
        self._model = model

    @classmethod
    def is_available(cls) -> tuple[bool, str]:
        try:
            import omnivoice.models.omnivoice  # noqa: F401
            return True, "ready"
        except Exception as e:
            return False, f"omnivoice package missing: {e}"

    @property
    def sample_rate(self) -> int:
        if self._model is None:
            return 24000  # canonical OmniVoice rate
        return getattr(self._model, "sampling_rate", 24000)

    @property
    def supported_languages(self) -> list[str]:
        # OmniVoice advertises 600+ zero-shot — `"multi"` is the honest tag.
        return ["multi"]

    def _ensure_loaded(self):
        if self._model is not None:
            return
        # Reuse model_manager's cached instance so we don't double-load.
        from services.model_manager import get_model
        import asyncio
        # Caller is sync; spin up a fresh loop if needed. get_running_loop()
        # raises only when *no* loop is running — that's the safe path where
        # we can bootstrap with asyncio.run().
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self._model = asyncio.run(get_model())
            return
        raise RuntimeError(
            "OmniVoiceBackend.generate() called inside an async context without a pre-loaded model. "
            "Pass `model=await get_model()` to the constructor."
        )

    def generate(self, text, **kw) -> torch.Tensor:
        self._ensure_loaded()
        language = kw.get("language")
        ref_audio = kw.get("ref_audio")
        ref_text = kw.get("ref_text")
        gen_kw = dict(
            text=text,
            language=language if language and language != "Auto" else None,
            instruct=kw.get("instruct"),
            duration=kw.get("duration"),
            num_step=kw.get("num_step", 16),
            guidance_scale=kw.get("guidance_scale", 2.0),
            speed=kw.get("speed", 1.0),
            denoise=kw.get("denoise", True),
            postprocess_output=kw.get("postprocess_output", True),
        )
        # /v1/audio/speech exposes preprocess_prompt (openai_compat.py) and it
        # used to be dropped on the floor here — the API accepted it and gen_kw
        # never carried it, so it silently did nothing.
        gen_kw["preprocess_prompt"] = bool(kw.get("preprocess_prompt", True))
        # Single-use reference hint (dub per-segment clips) — see
        # generate_with_cached_ref, which pops it before the model sees it.
        gen_kw["cache_ref"] = bool(kw.get("cache_ref", True))
        # The cached-reference path lives in generate_with_cached_ref, shared with
        # the native callers. Deliberately NOT a second copy: this logic living in
        # one place here and a subtly different one there is exactly how the cache
        # came to be wired into the adapter and nowhere else.
        audios = generate_with_cached_ref(
            self._model, ref_audio=ref_audio, ref_text=ref_text, **gen_kw
        )
        return audios[0]

    def unload(self) -> None:
        """Release the OmniVoice model (MM2-02). OmniVoice shares the singleton
        owned by ``model_manager``, so dropping our local ref isn't enough — we
        clear the shared one and free GPU memory too. Idempotent and safe before
        the first generate(). Best-effort: assignment is GIL-atomic, so we don't
        take the async ``_model_lock`` from this sync path; the registry wraps
        this call in try/except so a race can never block an engine switch.

        Delegates to ``model_manager.unload_shared_model`` rather than clearing
        the singleton here: this path used to free the device caches *before*
        dropping the shared reference, which frees nothing, and it is the path
        the idle sweep on a headless worker node runs (#1495)."""
        self._model = None
        clear_clone_prompt_cache()  # #427: drop cached prompts so VRAM is freed
        try:
            import services.model_manager as mm
            mm.unload_shared_model()
        except Exception as exc:
            # The reference is already gone by the time anything in here can
            # raise — only the device-cache flush is left, and that failing is
            # a driver problem, not a stuck model. Saying "retry" would send
            # the user to repeat an unload that already happened.
            logger.warning("Shared voice model released, but the device cache flush failed")
            raise RuntimeError(
                "The voice model was released, but the GPU memory cache could not be flushed."
            ) from exc


# ── Lazy registry entry for subprocess-isolated backends ──────────────────
#
# Backends that live in their own module (to avoid an import cycle with
# ``services.subprocess_backend``) register here as ``(module_path,
# attribute_name)``. ``_REGISTRY`` resolves the entry on first access via
# the descriptor below.

_LAZY_REGISTRY: dict[str, tuple[str, str]] = {
    # VieNeu-TTS — Vietnamese instant voice cloning (a Vietnamese fine-tune of
    # NeuTTS Air, Qwen 0.5B backbone; PyPI `vieneu`). Opt-in +
    # subprocess-isolated in its own venv (GGUF/ONNX runtime + sea_g2p
    # phonemizer stack). 48 kHz (v3-Turbo); CPU via ONNX Runtime (torch-free),
    # GPU via PyTorch; Windows-capable.
    "vienue": ("engines.vienue", "VieNueBackend"),
}


class _LazyRegistry(dict):
    """A dict that resolves selected keys via a deferred import.

    Keys in ``_LAZY_REGISTRY`` are not present in ``self`` until first
    access; ``__getitem__`` / ``__contains__`` / iteration all import
    them on demand. Everything else behaves like a normal dict — the
    registry-sandbox fixture in
    ``tests/backend/services/test_tts_backend_registry.py`` still gets
    snapshot semantics because once a lazy key is resolved it's stored
    in self exactly like a non-lazy key.
    """

    def __contains__(self, key) -> bool:  # noqa: D401
        return dict.__contains__(self, key) or key in _LAZY_REGISTRY

    def __getitem__(self, key):
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        if key in _LAZY_REGISTRY:
            mod_path, attr = _LAZY_REGISTRY[key]
            import importlib

            cls = getattr(importlib.import_module(mod_path), attr)
            self[key] = cls
            return cls
        raise KeyError(key)

    def __iter__(self):
        # Yield resolved keys first, then any lazy keys that haven't been
        # resolved yet. Resolving inside __iter__ would trigger a side
        # effect on every list_backends() call — we keep iteration light
        # and let the caller's __getitem__ trigger the import.
        seen: set[str] = set()
        # Snapshot the live keys before yielding. A concurrent thread's lazy
        # __getitem__ inserts into self (self[key] = cls), and list_backends()
        # runs in a FastAPI threadpool — so holding a *live* dict iterator open
        # across the per-engine is_available() probes would raise
        # "dictionary changed size during iteration". list() consumes the
        # iterator atomically under the GIL, closing that window.
        for k in list(dict.__iter__(self)):
            seen.add(k)
            yield k
        for k in _LAZY_REGISTRY:
            if k not in seen:
                yield k

    def items(self):
        for k in self:
            yield k, self[k]

    def keys(self):
        return list(iter(self))

    def values(self):
        return [self[k] for k in self]


_REGISTRY: dict[str, type[TTSBackend]] = _LazyRegistry({
    "omnivoice": OmniVoiceBackend,
})


# ── ENGINE-06 last-error cache ─────────────────────────────────────────────
#
# Populated by `list_backends()` whenever a backend's `is_available()`
# returns ok=False or raises an exception. Cleared per-id when the same
# backend reports ok=True. Surfaced via the `last_error` field on each
# registry entry so the Compat Matrix UI (Plan 02-04) can show the most
# recent failure even between calls — and prove which engine is the source
# of a hung Settings panel.
_LAST_ERRORS: dict[str, str] = {}



# Short install hints surfaced as tooltips on the Model Catalogue → Engines UI.
# Helps users understand what pip package to install and where.
_INSTALL_HINTS: dict[str, str] = {
    "omnivoice": "pip install omnivoice  (bundled -- no extra install needed)",
    "vienue": "uv venv backend/engines/vienue/.venv && uv pip install --python backend/engines/vienue/.venv/Scripts/python.exe vieneu  (Vietnamese instant voice clone -- weights auto-download from HF on first synthesize)",
}


_SETUP_SNIPPETS: dict[str, str] = {}



def _sidecar_installable_ids() -> frozenset[str]:
    """Engine ids with a one-click sidecar installer. Deferred import — the
    installer module is tiny, but keeping the import inside the function
    means a broken/absent installer can never take the engine picker down.

    All current sidecar SPECS are TTS engines, so only this registry carries
    ``one_click_install``; the first non-TTS sidecar engine will need the same
    field plumbed into asr_backend/llm_backend.list_backends and the Install
    button into their matrix rows.
    """
    try:
        from services.sidecar_install import SPECS
        return frozenset(SPECS)
    except Exception:  # pragma: no cover — defensive only
        return frozenset()


def _languages_of(cls) -> Optional[list[str]]:
    """Static language surface of a TTS engine (list_backends field).

    ``supported_languages`` is a property on most engines; resolve it from a
    throwaway instance — construction is lazy-load-free by contract (models
    load in ``ensure_ready()``, never ``__init__``). Any failure → None
    (= model-dependent / unknown), and the matrix simply hides the field:
    listing must never fail wholesale because one engine hiccups.
    """
    try:
        langs = cls().supported_languages
        return [str(x).lower() for x in langs] if langs else None
    except Exception:  # noqa: BLE001 — listing must never fail wholesale
        return None


def list_backends() -> list[dict]:
    """Enumerate every registered backend with its availability state.

    Per-entry shape (ENGINE-05 + ENGINE-06):

        {
          "id":             str,
          "display_name":   str,
          "available":      bool,
          "reason":         Optional[str],          # message when not available
          "hint":           Optional[str],          # advice when available-but-has-advice
                                                    #   (is_available "ready — <advice>" convention;
                                                    #   e.g. VoxCPM2's >=2.0.3 upgrade hint)
          "install_hint":   Optional[str],
          "setup_snippet":  Optional[str],          # exact `export VAR=...` for path-gated opt-in engines
          "one_click_install": bool,                # services.sidecar_install can provision it in-app
          "last_error":     Optional[str],          # cached most-recent failure
          "isolation_mode": "in-process" | "subprocess",
          "gpu_compat":     list[str],              # subset of {cuda, rocm, mps, xpu, cpu}
          "supports_cloning": Optional[bool],       # True/False from the class attr; None when
                                                    #   model-dependent (property, e.g. mlx-audio)
          "effective_device": str,                  # device this engine uses on THIS host
          "routing_status": "accelerated" | "cpu_fallback" | "cpu_only" | "unavailable",
          "routing_reason": Optional[str],          # scrubbed; null when none
        }

    Guarantees (ENGINE-05): a backend whose `is_available()` raises does
    NOT prevent the list from returning. The exception is captured into
    the `reason`/`last_error` fields for that one entry and every other
    backend is still listed normally.

    Security (Plan 02-04 / T-02-12): any HF-shaped token substring in
    ``reason`` or ``last_error`` is redacted before the entry is
    serialized — :func:`_mask_hf_tokens`. The frontend can render these
    fields verbatim without leaking credentials.
    """
    # Detect subprocess-isolated backends via a duck-typed marker rather
    # than `issubclass(cls, SubprocessBackend)`. Test fixtures (e.g. the
    # token_resolver suite) purge `sys.modules["services"]` between tests
    # for DB isolation, which produces a re-imported SubprocessBackend
    # class object that no longer == the one this test's subclasses closed
    # over. The marker attribute is set on SubprocessBackend itself, so
    # subclasses inherit it through any re-import path.
    # Routing is host-aware but the host caps are constant per process, so probe
    # ONCE here and resolve each engine's effective device against the same caps.
    from core.device_caps import detect_host_caps
    from services.engine_routing import routing_fields
    caps = detect_host_caps()
    installable = _sidecar_installable_ids()

    out: list[dict] = []
    for bid, cls in _REGISTRY.items():
        try:
            ok, msg = cls.is_available()
        except Exception:
            ok = False
            msg = "Availability probe failed; check the backend log."
            logger.warning("list_backends: availability probe failed for registered backend %s", bid)
        if ok:
            _LAST_ERRORS.pop(bid, None)
        else:
            # Mask any HF token inside the failure message BEFORE it lands
            # in the in-memory cache — otherwise a later list_backends()
            # call would re-surface the unmasked string.
            _LAST_ERRORS[bid] = _mask_hf_tokens(msg)
        # ENGINE-06 isolation_mode: duck-typed marker for SubprocessBackend
        # subclasses (see services.subprocess_backend.SubprocessBackend).
        if getattr(cls, "_is_subprocess_isolated", False):
            isolation = "subprocess"
        else:
            isolation = "in-process"
        gpu_compat = getattr(cls, "gpu_compat", ("cpu",))
        # Cloning capability: same descriptor guard as
        # cloning_capable_engine_ids() — a class-level getattr on a *property*
        # (mlx-audio: capability depends on the picked model) returns the
        # descriptor, not a bool, so report None (= model-dependent) there
        # instead of an always-truthy false positive.
        _clone = getattr(cls, "supports_cloning", True)
        out.append({
            "id": bid,
            "display_name": cls.display_name,
            "available": ok,
            "reason": None if ok else _mask_hf_tokens(msg),
            # Available-but-has-advice (e.g. VoxCPM2's ">=2.0.3 recommended"
            # upgrade hint). None unless ok and the message carries advice.
            "hint": _available_hint(msg) if ok else None,
            "supports_cloning": _clone if isinstance(_clone, bool) else None,
            # Graded-emotion capability (#1208) — drives the Audiobook emotion
            # panel's engine gate. Class attr, defaults False.
            "supports_emotion": bool(getattr(cls, "supports_emotion", False)),
            # Static language surface (list of ISO codes / "multi"); None when
            # model-dependent or unknown. Drives the matrix's language chips.
            "languages": _languages_of(cls),
            "install_hint": _INSTALL_HINTS.get(bid),
            # Exact `export VAR=...` line for path-gated opt-in engines, or None.
            "setup_snippet": _SETUP_SNIPPETS.get(bid),
            # True when services.sidecar_install can provision this engine
            # in-app (Settings renders an Install button instead of leading
            # with the manual setup snippet).
            "one_click_install": bid in installable,
            "last_error": _LAST_ERRORS.get(bid),
            "isolation_mode": isolation,
            "gpu_compat": list(gpu_compat),
            # effective_device / routing_status / routing_reason (scrubbed):
            "min_vram_gb": getattr(cls, "min_vram_gb", 0.0) or None,
            # effective_device / routing_status / routing_reason (scrubbed);
            # the reason now also carries the under-provisioned-GPU caveat.
            **routing_fields(gpu_compat, caps, getattr(cls, "min_vram_gb", 0.0)),
        })
    return out



def get_backend_class(backend_id: str) -> type[TTSBackend]:
    if backend_id not in _REGISTRY:
        raise ValueError(f"Unknown TTS backend: {backend_id!r}. Known: {list(_REGISTRY)}")
    return _REGISTRY[backend_id]


def cloning_capable_engine_ids() -> list[str]:
    """Engine ids that support reference-audio voice cloning — used to build
    an actionable error when the active engine can't (dub/batch gating).

    Iterates the same registry ``list_backends()`` uses, via ``.items()`` so
    lazy entries resolve through ``_LazyRegistry``'s snapshot-safe iteration
    (see ``_LazyRegistry.__iter__``) exactly like every other registry scan
    in this module.

    A class-level ``getattr`` on a *property* returns the descriptor object
    itself (always truthy) rather than its computed value — so a
    model-dependent adapter like ``MLXAudioBackend`` (only some of its 7+
    curated models can clone) would always show up here regardless of which
    model is actually configured. Excluded rather than falsely recommended:
    ``isinstance(..., bool)`` is False for a descriptor, True for a plain
    class attribute.
    """
    return [
        bid for bid, cls in _REGISTRY.items()
        if isinstance((v := getattr(cls, "supports_cloning", True)), bool) and v
    ]


def active_routing() -> dict | None:
    """Routing verdict for the currently-active TTS engine, or ``None`` if it
    can't be determined (no engine / probe failure).

    Derived from :func:`list_backends` so the verdict is byte-identical to what
    the Engine Compatibility Matrix shows for the same engine. Consumed by
    ``/setup/preflight`` and ``/system/diagnose`` to surface a GPU-routing
    verdict for the active engine (no silent CPU fallback). Never raises.
    """
    try:
        active = active_backend_id()
        for b in list_backends():
            if b.get("id") == active:
                return {
                    "engine": active,
                    "available": b.get("available"),
                    "effective_device": b.get("effective_device"),
                    "routing_status": b.get("routing_status"),
                    "routing_reason": b.get("routing_reason"),
                }
    except Exception:
        # Routing is advisory — never let a probe/registry hiccup break the
        # caller (preflight/diagnose must stay responsive — local-first).
        return None
    return None


def gpu_routing_verdict() -> dict:
    """The GpuRouting payload (see api.schemas.GpuRouting) for the active TTS
    engine + this host's compute summary. Used by ``/setup/preflight`` and
    ``/system/diagnose``. Never raises — degrades to a host-only verdict with
    ``routing_status:"none"`` if the active engine can't be resolved."""
    from core.device_caps import detect_host_caps
    try:
        caps = detect_host_caps()
        host_family, vram_gb = caps.family, round(caps.vram_gb, 1)
    except Exception:
        host_family, vram_gb = "cpu", 0.0
    r = active_routing()
    if not r:
        return {
            "engine": None, "effective_device": None,
            "routing_status": "none", "routing_reason": None,
            "host_family": host_family, "vram_gb": vram_gb,
        }
    return {
        "engine": r.get("engine"),
        "effective_device": r.get("effective_device"),
        "routing_status": r.get("routing_status"),
        "routing_reason": r.get("routing_reason"),
        "host_family": host_family, "vram_gb": vram_gb,
    }


def active_backend_id() -> str:
    # Env var > persisted UI choice > default. Env wins so power-users can
    # pin a backend without the Settings picker silently undoing it.
    from core import prefs
    return prefs.resolve("tts_backend", env="OMNIVOICE_TTS_BACKEND", default="omnivoice")


# Cached active backend instance + its id (MM2-01). Without this, every call
# built a fresh instance and the previous engine's VRAM/sidecar leaked until GC
# — measurable when switching engines on an 8 GB MPS Mac (root cause behind the
# #278 comment thread). We now keep one instance per configured backend id and
# call the outgoing engine's unload() before switching.
_active_instance: "TTSBackend | None" = None
_active_instance_id: "str | None" = None


def reset_active_backend() -> None:
    """Unload + clear the cached active backend. For app shutdown and tests.
    Idempotent and best-effort — a raising unload() never propagates."""
    global _active_instance, _active_instance_id
    inst = _active_instance
    _active_instance = None
    _active_instance_id = None
    if inst is not None:
        try:
            inst.unload()
        except Exception as exc:  # noqa: BLE001
            logger.warning("reset_active_backend: %s.unload() raised: %s",
                           type(inst).__name__, exc)


def get_active_tts_backend(*, model=None) -> TTSBackend:
    """Return the configured backend, reusing a cached instance and releasing
    the previous engine on a switch (MM2-01).

    Rule: the cache tracks the configured backend id. Switching id always
    unload()s the outgoing instance first. For OmniVoice with an explicit
    ``model=`` (caller already holds a loaded model), we return a fresh view
    over the shared singleton rather than caching it — but a switch *away from*
    a different engine still triggers that engine's unload().
    """
    global _active_instance, _active_instance_id
    bid = active_backend_id()

    # Switching engines: release the outgoing one first. Best-effort so a bad
    # unload() can never block the switch.
    switching = _active_instance is not None and _active_instance_id != bid
    if switching:
        try:
            _active_instance.unload()
        except Exception as exc:  # noqa: BLE001
            logger.warning("engine switch: %s.unload() raised: %s",
                           type(_active_instance).__name__, exc)
        _active_instance = None
        _active_instance_id = None

    cls = get_backend_class(bid)
    if cls is OmniVoiceBackend and model is not None:
        # Per-call view over the already-loaded shared singleton; don't cache it
        # (the model lifecycle is owned by model_manager), but the switch above
        # already released any *different* previous engine.
        return OmniVoiceBackend(model=model)

    if _active_instance is None or _active_instance_id != bid:
        _active_instance = OmniVoiceBackend(model=model) if cls is OmniVoiceBackend else cls()
        _active_instance_id = bid
    return _active_instance



# ── Shared engine-instance cache ──────────────────────────────────────────
#
# One instance per engine class for the lifetime of the process. It lived in
# ``api/routers/engines.py`` until the worker needed it too: a worker executing
# a remote assignment must reuse the same warm engine the local generate path
# uses, and importing an API router from ``worker/`` would invert the layering
# (``worker/executor.py`` is a translator over ``services/``). The router now
# aliases this dict, so every consumer that already reaches for
# ``engines._ENGINE_INSTANCES`` — engine_memory's eviction, model_lifecycle's
# inventory and unload — keeps operating on the one true cache.
#
# Keyed by CLASS, not by engine id, because registry-sandbox tests rebind ids
# transiently; ``get_engine_instance_for`` resolves an id through
# ``get_backend_class`` so callers can key by id without the cache doing so.
_ENGINE_INSTANCES: dict[type, object] = {}
_ENGINE_CACHE_LOCK = threading.RLock()

# Last use, on the monotonic clock — a wall clock would make an NTP step or a
# laptop resume look like a ten-minute idle and unload a model mid-job.
_ENGINE_LAST_USED: dict[type, float] = {}

# How many jobs are inside an engine right now. A long generation touches the
# cache once at the start, so on elapsed time alone a 40-minute dub looks
# exactly like an abandoned model — and the sweep would unload it out from
# under the thread rendering it.
_ENGINE_IN_USE: dict[type, int] = {}

def _idle_seconds_from_env(name: str, default: float, *, floor: float) -> float:
    """Read a tunable idle duration, ignoring anything unusable.

    These exist so the ten-minute behaviour can be observed in a minute during
    testing instead of a coffee break. A bad value must not change behaviour
    silently, and must never reach zero: a zero threshold unloads an engine the
    instant it goes idle, which on a busy machine means reloading it for every
    request.
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Ignoring %s=%r: not a number.", name, raw)
        return default
    if value < floor:
        logger.warning("Ignoring %s=%s: below the %ss floor.", name, value, floor)
        return default
    return value


#: How long an engine may sit unused before its weights are handed back.
#: Override with OMNIVOICE_ENGINE_IDLE_UNLOAD_SECONDS (testing).
ENGINE_IDLE_UNLOAD_SECONDS = _idle_seconds_from_env(
    "OMNIVOICE_ENGINE_IDLE_UNLOAD_SECONDS", 600.0, floor=5.0
)


@contextmanager
def engine_in_use(instance, *, now: Optional[float] = None):
    """Hold an engine against the idle sweep for the duration of one job.

    Leaving on the exit stamp rather than the entry one makes "idle" mean
    "idle since the work finished", which is the only reading under which the
    ten-minute window measures what it claims to.
    """
    cls = type(instance)
    with _ENGINE_CACHE_LOCK:
        _ENGINE_IN_USE[cls] = _ENGINE_IN_USE.get(cls, 0) + 1
    try:
        yield instance
    finally:
        with _ENGINE_CACHE_LOCK:
            remaining = _ENGINE_IN_USE.get(cls, 1) - 1
            if remaining > 0:
                _ENGINE_IN_USE[cls] = remaining
            else:
                _ENGINE_IN_USE.pop(cls, None)
            _ENGINE_LAST_USED[cls] = time.monotonic() if now is None else float(now)


def get_engine_instance(cls, *, now: Optional[float] = None):
    """Return the cached singleton instance of ``cls``, creating it once.

    ``SubprocessBackend.__init__`` registers an atexit shutdown hook, so
    re-instantiating per call would leak handler entries — and on real engines,
    an extra sidecar process the first time the lock is acquired. One instance
    per process is the right move.
    """
    with _ENGINE_CACHE_LOCK:
        inst = _ENGINE_INSTANCES.get(cls)
        if inst is None:
            inst = cls()
            _ENGINE_INSTANCES[cls] = inst
        _ENGINE_LAST_USED[cls] = time.monotonic() if now is None else float(now)
        return inst


def get_engine_instance_for(engine_id: str, *, now: Optional[float] = None):
    """Cached instance of the TTS engine registered under ``engine_id``.

    Deliberately NOT :func:`get_active_tts_backend`: that resolves
    ``active_backend_id()``, i.e. *this machine's* Settings preference. On a
    remote worker that would run whatever the worker's owner happens to prefer
    while the control plane's slots, breaker history and result metadata are
    keyed to the engine it believes ran — wrong audio, silently.
    """
    return get_engine_instance(get_backend_class(engine_id), now=now)


def release_idle_engines(
    idle_seconds: float = ENGINE_IDLE_UNLOAD_SECONDS,
    *,
    now: Optional[float] = None,
) -> list[str]:
    """Unload and drop every cached engine unused for ``idle_seconds``.

    Least-recently-used first, so a sweep cut short by a raising ``unload()``
    has already freed the coldest engine. Never raises: a stuck unload must not
    take down the loop that called it. Returns the engine ids released.
    """
    stamp = time.monotonic() if now is None else float(now)
    pending: list[tuple[str, object]] = []
    with _ENGINE_CACHE_LOCK:
        # Entries other consumers popped straight out of the cache
        # (engine_memory's eviction, model_lifecycle's unload) would otherwise
        # pin a stale class.
        for cls in [c for c in _ENGINE_LAST_USED if c not in _ENGINE_INSTANCES]:
            _ENGINE_LAST_USED.pop(cls, None)
        coldest_first = sorted(
            _ENGINE_INSTANCES, key=lambda c: _ENGINE_LAST_USED.get(c, 0.0)
        )
        for cls in coldest_first:
            if _ENGINE_IN_USE.get(cls):
                continue
            # An instance put here by some other path has no timestamp; start
            # its clock now rather than leaving it resident forever.
            last_used = _ENGINE_LAST_USED.setdefault(cls, stamp)
            if stamp - last_used < idle_seconds:
                continue
            inst = _ENGINE_INSTANCES.pop(cls, None)
            _ENGINE_LAST_USED.pop(cls, None)
            if inst is not None:
                pending.append((getattr(cls, "id", cls.__name__), inst))

    released: list[str] = []
    for engine_id, inst in pending:
        try:
            inst.unload()
        except Exception as exc:  # noqa: BLE001
            logger.warning("idle unload: %s.unload() raised: %s", engine_id, exc)
        released.append(engine_id)
    if released:
        logger.info("Released %d idle engine(s): %s", len(released), ", ".join(released))
    return released


# ── Shared generation-time engine resolution (issue #312 class) ───────────
#
# dub_generate.py and batch.py used to call services.model_manager.get_model()
# directly, hardcoding OmniVoice regardless of the engine selected in
# Model Catalogue → Engines — a SILENT fallback: pick VoxCPM2, dub anyway with
# OmniVoice, no error. This is the single resolution path both routers now
# call instead, mirroring generation.py's /generate resolution (engine id →
# is_available() → routing gate) plus a voice-cloning capability gate that
# /generate doesn't need (OmniVoice's native path always clones).


async def resolve_generation_backend(
    *, require_cloning: bool = False, cloning_purpose: str = "dubbing",
) -> TTSBackend:
    """Resolve + validate the active TTS engine for a generation call.

    Returns the live backend instance (:func:`get_active_tts_backend`) —
    cached, and properly unload()ed on an engine switch. Raises ``ValueError``
    with an actionable message (never silently falls back to OmniVoice) when:

      * the configured engine id is unknown (bad env var / stale pref),
      * the engine reports itself unavailable (``is_available()``),
      * the engine needs an accelerator this host lacks and has no CPU path
        (``routing_status == "unavailable"``),
      * ``require_cloning`` is True and the resolved backend can't clone
        from reference audio (``supports_cloning`` False) — checked on the
        live *instance*, not the class, so a model-dependent adapter like
        MLX-Audio (Kokoro vs. CSM) is judged by what's actually loaded.
    """
    engine_id = active_backend_id()
    try:
        backend_cls = get_backend_class(engine_id)
    except ValueError as e:
        raise ValueError(
            f"Active TTS engine '{engine_id}' is not a recognized backend ({e}). "
            "Check Model Catalogue → Engines or the OMNIVOICE_TTS_BACKEND env var."
        ) from e

    try:
        ok, msg = backend_cls.is_available()
    except Exception as exc:  # noqa: BLE001 — surface as an actionable ValueError
        ok, msg = False, f"{type(exc).__name__}: {exc}"
    if not ok:
        raise ValueError(f"TTS engine '{engine_id}' is not available: {_mask_hf_tokens(msg)}")

    from core.device_caps import detect_host_caps
    from services.engine_routing import resolve_routing
    routing = resolve_routing(
        getattr(backend_cls, "gpu_compat", ("cpu",)), detect_host_caps(),
        getattr(backend_cls, "min_vram_gb", 0.0),
    )
    if routing["routing_status"] == "unavailable":
        raise ValueError(routing["routing_reason"])

    _model = None
    if backend_cls is OmniVoiceBackend:
        # OmniVoice needs its model pre-loaded before construction: called
        # from an async context, OmniVoiceBackend._ensure_loaded() refuses to
        # bootstrap its own event loop (see its docstring) — same reason
        # generation.py's /generate special-cases this backend.
        from services.model_manager import get_model
        _model = await get_model()
    backend = get_active_tts_backend(model=_model)

    if require_cloning and not getattr(backend, "supports_cloning", True):
        raise ValueError(
            f"The active TTS engine '{engine_id}' doesn't support voice cloning, "
            f"so {cloning_purpose} can't preserve speaker voices. Switch to one "
            f"of: {', '.join(cloning_capable_engine_ids())} in "
            "Model Catalogue → Engines, or use OmniVoice for this job."
        )

    return backend


def __getattr__(name: str):  # pragma: no cover - exercised via tests
    if name == "VieNueBackend":
        return _REGISTRY["vienue"]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

