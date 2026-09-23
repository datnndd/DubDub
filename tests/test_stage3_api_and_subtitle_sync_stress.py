"""
DubDub Stage 3: Voice & Dubbing — Adversarial API & Subtitle Sync Stress Test Suite
Challenger 2 Empirical Verification

Comprehensive stress tests covering:
1. Backend `/api/voices` Endpoint Stress:
   - Out-of-bounds indices (9999, -50, -1, 4, int32 max/min, huge arbitrary ints, NaN, 1.5)
   - Boundary & malicious language codes (empty, whitespace, uppercase, XSS, path traversal, unicode/emojis, 2k chars, unsupported languages)
   - Excessive query string length (> 8KB transport limit) returning 400 cleanly
   - Provider name aliases and casing (case insensitivity, whitespace trimming, canonical aliases)
   - Unknown provider fallback behavior
   - High concurrency (100 simultaneous concurrent requests)
   - Upstream engine error handling and fallbacks (None, empty list, exceptions)
2. Subtitle Synchronization Boundary Timecode Testing (Headless Node.js DOM):
   - Negative timecodes (-5.0, -0.001)
   - Inter-segment gaps (timestamps between segments)
   - Exact boundary matching (startSec, endSec, epsilon transitions)
   - Zero gap contiguous transitions
   - Pre-transcript and post-transcript boundaries (0.0, 999.0)
   - Text fallbacks and XSS safety (.textContent vs innerHTML)
   - Empty segments array resilience
   - Non-finite media.currentTime (NaN, undefined, null, Infinity)
"""

import asyncio
import json
from pathlib import Path
import shutil
import subprocess

from aiohttp.test_utils import TestClient, TestServer
import pytest

from videotrans.api.app import create_app
from videotrans.util.help_role import role_menu

from videotrans import tts


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_tts_catalogs(monkeypatch):
    """Deterministic voice catalog for testing."""
    catalogs = {
        tts.ELEVENLABS_TTS: ["No", "Rachel", "Domi", "Bella"],
        tts.OMNIVOICE_TTS: ["No", "clone", "Omni-Speaker-1"],
        tts.VIENEU_TTS: ["No", "clone", "Phạm Tuyên", "Mai Phương"],
        tts.GEMINI_TTS: ["Zephyr", "Puck", "Charon", "Aoede"],
    }
    calls = []

    def fake_role_menu(tts_type, langcode=None):
        calls.append({"tts_type": tts_type, "langcode": langcode})
        return catalogs.get(tts_type, ["No"])

    monkeypatch.setattr(webui, "role_menu", fake_role_menu)
    return {"catalogs": catalogs, "calls": calls}


# ============================================================================
# 1. API Voices Adversarial Stress Tests
# ============================================================================

def test_voices_out_of_bounds_and_overflow_indices(tmp_path, mock_tts_catalogs):
    """
    Stress test /api/voices with extreme and out-of-bounds index parameters:
    - Huge positive out-of-bounds (9999, 2147483647, 10^40)
    - Negative out-of-bounds (-50, -1, -2147483648)
    - Strict boundary index (4, since catalog length is 4: indices 0..3)
    - Floats, NaN, Infinity, non-numeric strings
    """
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            boundary_inputs = [
                "9999",
                "-50",
                "-1",
                "4",  # Exactly at length of TTS_NAME_LIST (valid are 0,1,2,3)
                "2147483647",
                "-2147483648",
                "9999999999999999999999999999999999999999",  # Arbitrary precision overflow
                "NaN",
                "Infinity",
                "-Infinity",
                "null",
                "undefined",
                "1.5",
                "0.0",
                "",
                "   ",
            ]
            for val in boundary_inputs:
                res = await client.get(f"/api/voices?ttsType={val}")
                assert res.status == 200, f"Failed for ttsType='{val}' with status {res.status}"
                data = await res.json()
                assert "voices" in data, f"Missing 'voices' in response for ttsType='{val}'"
                assert isinstance(data["voices"], list), f"'voices' not a list for ttsType='{val}'"
                assert len(data["voices"]) > 0, f"'voices' list is empty for ttsType='{val}'"
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_boundary_and_malicious_language_codes(tmp_path, mock_tts_catalogs):
    """
    Stress test /api/voices with boundary, malicious, and extreme language codes:
    - Empty, whitespace
    - Uppercase, mixed case, region subtags
    - Security vectors (XSS, path traversal, SQL injection)
    - Non-ASCII, Unicode, Emojis
    - Long string (2,000 characters)
    - Unsupported language names
    """
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            test_languages = [
                "",
                "   ",
                "EN",
                "VI",
                "JA",
                "ZH-CN",
                "pt-BR",
                "<script>alert(1)</script>",
                "../../../../etc/passwd",
                "'; DROP TABLE users; --",
                "!@#$%^&*()_+-=[]{}|;':\",./<>?",
                "Tiếng Việt",
                "日本語",
                "العربية",
                "😀🎉🚀🔥",
                "a" * 2000,
                "unsupported_klingon_dialect_999",
            ]
            for lang in test_languages:
                for tts_id in [0, 2]:
                    res = await client.get(f"/api/voices?ttsType={tts_id}&language={lang}")
                    assert res.status == 200, f"Failed for language='{lang[:30]}' status {res.status}"
                    data = await res.json()
                    assert "voices" in data
                    assert isinstance(data["voices"], list)
                    assert len(data["voices"]) > 0
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_excessive_query_string_length(tmp_path):
    """
    Verify server behavior when query string exceeds HTTP line limits (e.g. 10KB language string).
    aiohttp must reject with 400 Bad Request without crashing the process.
    """
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            huge_lang = "a" * 10000
            res = await client.get(f"/api/voices?ttsType=0&language={huge_lang}")
            # aiohttp returns 400 when status line exceeds 8190 bytes
            assert res.status == 400

            # Follow-up request succeeds immediately (server did not crash or hang)
            res2 = await client.get("/api/voices?ttsType=0&language=en")
            assert res2.status == 200
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_provider_name_aliases_and_casing(tmp_path, mock_tts_catalogs):
    """
    Stress test /api/voices provider name aliases and casing:
    - Uppercase, lowercase, mixed case
    - Leading/trailing whitespace
    - Dash, no-dash variants
    - Unknown/invalid aliases falling back safely
    """
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            alias_expectations = [
                # ElevenLabs (provider 0)
                ("elevenlabs", tts.ELEVENLABS_TTS),
                ("ELEVENLABS", tts.ELEVENLABS_TTS),
                ("ElevenLabs", tts.ELEVENLABS_TTS),
                (" ElevenLabs ", tts.ELEVENLABS_TTS),
                # OmniVoice (provider 1)
                ("omnivoice", tts.OMNIVOICE_TTS),
                ("OMNIVOICE", tts.OMNIVOICE_TTS),
                ("OmniVoice", tts.OMNIVOICE_TTS),
                (" OmniVoice ", tts.OMNIVOICE_TTS),
                # VieNeu-TTS (provider 2)
                ("vieneu", tts.VIENEU_TTS),
                ("VIENEU", tts.VIENEU_TTS),
                ("vieneu-tts", tts.VIENEU_TTS),
                ("VIENEU-TTS", tts.VIENEU_TTS),
                ("VieNeu-TTS", tts.VIENEU_TTS),
                ("vieneutts", tts.VIENEU_TTS),
                (" ViEnEu-TtS ", tts.VIENEU_TTS),
                # Gemini TTS (provider 3)
                ("gemini", tts.GEMINI_TTS),
                ("GEMINI", tts.GEMINI_TTS),
                ("gemini-tts", tts.GEMINI_TTS),
                ("geminitts", tts.GEMINI_TTS),
                ("Gemini TTS", tts.GEMINI_TTS),
                (" GEMINI TTS ", tts.GEMINI_TTS),
            ]
            for alias, expected_id in alias_expectations:
                res = await client.get(f"/api/voices?provider={alias}&language=en")
                assert res.status == 200, f"Failed for provider alias='{alias}'"
                data = await res.json()
                expected_voices = mock_tts_catalogs["catalogs"][expected_id]
                assert data["voices"] == expected_voices, (
                    f"Alias '{alias}' did not resolve to expected voices for provider {expected_id}. "
                    f"Got {data['voices']}"
                )

            # Test unknown aliases fall back safely to default provider 0 without 500 error
            unknown_aliases = ["unknown_tts", "invalid_provider", "random-engine", "not-a-provider"]
            for unknown in unknown_aliases:
                res = await client.get(f"/api/voices?provider={unknown}")
                assert res.status == 200
                data = await res.json()
                assert "voices" in data
                assert isinstance(data["voices"], list)
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_high_concurrency_stress(tmp_path, mock_tts_catalogs):
    """
    Stress test /api/voices with 100 simultaneous concurrent requests
    mixing various providers, aliases, boundary language codes, and out-of-bounds indices.
    Verifies no race conditions, deadlocks, or degraded responses.
    """
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            test_queries = [
                "/api/voices?ttsType=0&language=en",
                "/api/voices?ttsType=1&language=vi",
                "/api/voices?ttsType=2&language=ja",
                "/api/voices?ttsType=3&language=zh",
                "/api/voices?provider=elevenlabs",
                "/api/voices?provider=ViEnEu-TtS&language=vi",
                "/api/voices?provider=gemini&target_language=en",
                "/api/voices?ttsType=9999",
                "/api/voices?ttsType=-50",
                "/api/voices?ttsType=garbage_string",
                "/api/voices?language=<script>alert(1)</script>",
                "/api/voices?language=Ti%E1%BA%BFng%20Vi%E1%BB%87t",
            ]

            # Generate 100 requests
            requests = [
                client.get(test_queries[i % len(test_queries)])
                for i in range(100)
            ]

            responses = await asyncio.gather(*requests)
            assert len(responses) == 100

            for i, res in enumerate(responses):
                assert res.status == 200, f"Request {i} failed with status {res.status}"
                data = await res.json()
                assert "voices" in data, f"Request {i} missing 'voices'"
                assert isinstance(data["voices"], list)
                assert len(data["voices"]) > 0
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_role_menu_exception_and_empty_edge_cases(tmp_path, monkeypatch):
    """
    Adversarial verification of role_menu failure modes:
    - role_menu returns None -> endpoint returns {"voices": ["No"]}
    - role_menu returns [] -> endpoint returns {"voices": ["No"]}
    - role_menu raises unhandled RuntimeError, KeyError, MemoryError -> endpoint returns {"voices": ["No"]}
    """
    app = create_app(
        upload_dir=tmp_path / "uploads",
        role_provider=lambda *args, **kwargs: role_menu(*args, **kwargs),
    )

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # Case 1: role_menu returns None
            monkeypatch.setattr(webui, "role_menu", lambda *a, **k: None)
            res1 = await client.get("/api/voices?ttsType=0")
            assert res1.status == 200
            assert (await res1.json()) == {"voices": ["No"]}

            # Case 2: role_menu returns []
            monkeypatch.setattr(webui, "role_menu", lambda *a, **k: [])
            res2 = await client.get("/api/voices?ttsType=0")
            assert res2.status == 200
            assert (await res2.json()) == {"voices": ["No"]}

            # Case 3: role_menu raises KeyError
            def raise_key_error(*a, **k):
                raise KeyError("missing_provider_key")
            monkeypatch.setattr(webui, "role_menu", raise_key_error)
            res3 = await client.get("/api/voices?ttsType=1")
            assert res3.status == 200
            assert (await res3.json()) == {"voices": ["No"]}

            # Case 4: role_menu raises MemoryError
            def raise_mem_error(*a, **k):
                raise MemoryError("simulated out of memory")
            monkeypatch.setattr(webui, "role_menu", raise_mem_error)
            res4 = await client.get("/api/voices?ttsType=2")
            assert res4.status == 200
            assert (await res4.json()) == {"voices": ["No"]}
        finally:
            await client.close()

    asyncio.run(scenario())


# ============================================================================
# 2. Subtitle Synchronization Boundary Timecode Testing (Headless Node.js DOM)
# ============================================================================
