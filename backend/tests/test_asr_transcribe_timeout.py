"""Deepgram transcribe calls must be wall-clock bounded."""
import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services import asr_backend  # noqa: E402
from services.asr_backend import (  # noqa: E402
    ASRTimeoutError,
    ASR_TRANSCRIBE_TIMEOUT_S,
    reset_pool_after_wedge,
    run_transcribe_guarded,
)
from concurrent.futures import ThreadPoolExecutor  # noqa: E402


def test_default_timeout_is_env_overridable(monkeypatch):
    # The constant is read at import; just assert it's a sane positive default.
    assert ASR_TRANSCRIBE_TIMEOUT_S > 0


def test_slow_transcribe_raises_actionable_timeout():
    pool = ThreadPoolExecutor(max_workers=1)

    def _hang():
        time.sleep(5)  # would block far past our tiny timeout
        return "never"

    async def _go():
        with pytest.raises(ASRTimeoutError) as ei:
            await run_transcribe_guarded(pool, _hang, what="QC", timeout=0.2)
        msg = str(ei.value)
        assert "QC transcription exceeded 0s" in msg
        assert "OMNIVOICE_ASR_TRANSCRIBE_TIMEOUT_S" in msg
        assert "Deepgram" in msg
        assert "Faster-Whisper" not in msg
        assert "smaller ASR model" not in msg

    asyncio.run(_go())
    pool.shutdown(wait=False)


def test_fast_transcribe_passes_through():
    pool = ThreadPoolExecutor(max_workers=1)

    def _quick():
        return {"segments": [{"text": "hi"}]}, "deepgram-asr"

    async def _go():
        out = await run_transcribe_guarded(pool, _quick, what="Dictation", timeout=5.0)
        assert out == ({"segments": [{"text": "hi"}]}, "deepgram-asr")

    asyncio.run(_go())
    pool.shutdown(wait=True)


def _hang_forever():
    time.sleep(5)
    return "never"


def test_timeout_error_is_a_timeouterror_subclass():
    # Routers that catch broad TimeoutError (openai_compat) must also catch ours.
    assert issubclass(ASRTimeoutError, TimeoutError)


def test_timeout_resets_a_resilient_pool_to_restore_capacity():
    class _FakePool(ThreadPoolExecutor):
        def __init__(self):
            super().__init__(max_workers=1)
            self.reset_calls = 0

        def reset(self, *args, **kwargs):
            self.reset_calls += 1

    pool = _FakePool()

    async def _go():
        with pytest.raises(ASRTimeoutError):
            await run_transcribe_guarded(pool, _hang_forever, what="Dub", timeout=0.2)

    asyncio.run(_go())
    assert pool.reset_calls == 1
    pool.shutdown(wait=False)


def test_timeout_without_reset_capable_pool_does_not_crash():
    pool = ThreadPoolExecutor(max_workers=1)

    async def _go():
        with pytest.raises(ASRTimeoutError):
            await run_transcribe_guarded(pool, _hang_forever, what="QC", timeout=0.2)

    asyncio.run(_go())
    pool.shutdown(wait=False)


def test_timeout_env_name_is_parameterized():
    """The chunked dub path passes its own knob; the message must name IT, not
    the whole-file env var (actionable errors point at the right dial)."""
    pool = ThreadPoolExecutor(max_workers=1)

    async def _go():
        with pytest.raises(ASRTimeoutError) as ei:
            await run_transcribe_guarded(
                pool, _hang_forever, what="Dub chunk 1/3", timeout=0.1,
                timeout_env="OMNIVOICE_TRANSCRIBE_CHUNK_TIMEOUT_S",
            )
        msg = str(ei.value)
        assert "OMNIVOICE_TRANSCRIBE_CHUNK_TIMEOUT_S" in msg
        assert "OMNIVOICE_ASR_TRANSCRIBE_TIMEOUT_S" not in msg

    asyncio.run(_go())
    pool.shutdown(wait=False)


def test_reset_pool_after_wedge_is_shared_and_best_effort():
    """One reset mechanism for every transcribe path (#730 residual A): it
    resets a reset-capable pool, no-ops a plain executor, and never raises."""

    class _Pool:
        resets = 0

        def reset(self):
            self.resets += 1

    p = _Pool()
    assert reset_pool_after_wedge(p, what="Dub chunk 1/2") is True
    assert p.resets == 1

    plain = ThreadPoolExecutor(max_workers=1)
    try:
        assert reset_pool_after_wedge(plain) is False
    finally:
        plain.shutdown(wait=False)

    class _Broken:
        def reset(self):
            raise RuntimeError("reset blew up")

    assert reset_pool_after_wedge(_Broken()) is False  # must not raise
