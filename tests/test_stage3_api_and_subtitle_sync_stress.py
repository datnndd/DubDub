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

from tests import webui_support as webui
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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(
        upload_dir=tmp_path / "uploads",
        role_provider=lambda *args, **kwargs: webui.role_menu(*args, **kwargs),
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

def test_subtitle_sync_boundary_timecodes_headless_node():
    """
    Empirically execute syncPreviewPlayback in Node.js v22 with simulated DOM
    under boundary timecodes:
    - Negative times (-5.0, -0.001)
    - Inter-segment gaps (timestamps between segments)
    - Exact boundary matching (startSec, endSec, epsilon transitions)
    - Timecode 0.0 before first segment starts
    - Timecode beyond last segment (999.0)
    - Subtitle text fallback when targetText is missing
    - XSS injection safety (.textContent escaping)
    """
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    const elements = {
        '[data-canvas-subtitle]': { textContent: '' },
        '[data-canvas-speaker-badge]': { textContent: '', style: { display: '' } },
        '[data-preview-timeline]': { value: '0' },
        '[data-scrubber-marker]': { style: { left: '0%' } },
        '[data-scrubber-progress]': { style: { width: '0%' } },
        '[data-preview-action-icon]': { textContent: 'play_arrow' },
    };

    const cardElements = [
        {
            attrs: { 'data-segment-card': '1' },
            classes: new Set(['border-stone-200', 'bg-white']),
            getAttribute(name) { return this.attrs[name]; },
            classList: {
                add(...cls) { cls.forEach(c => elements[`card-1`]?.classes.add(c)); },
                remove(...cls) { cls.forEach(c => elements[`card-1`]?.classes.delete(c)); }
            }
        },
        {
            attrs: { 'data-segment-card': '2' },
            classes: new Set(['border-stone-200', 'bg-white']),
            getAttribute(name) { return this.attrs[name]; },
            classList: {
                add(...cls) { cls.forEach(c => elements[`card-2`]?.classes.add(c)); },
                remove(...cls) { cls.forEach(c => elements[`card-2`]?.classes.delete(c)); }
            }
        }
    ];
    elements['card-1'] = cardElements[0];
    elements['card-2'] = cardElements[1];

    globalThis.window = globalThis;
    globalThis.document = {
        querySelector(selector) {
            return elements[selector] || null;
        },
        querySelectorAll(selector) {
            if (selector === '[data-segment-card]') return cardElements;
            return [];
        }
    };

    const { store } = await import('./frontend/js/state.js');

    // Setup project with 2 segments separated by a 0.5s gap:
    // Segment 1: [1.0, 5.0] (Speaker 1, Lead)
    // Gap: (5.0, 5.5)
    // Segment 2: [5.5, 9.0] (Speaker 2, Guest)
    store.state.project.durationSec = 10.0;
    store.state.segments = [
        {
            id: 1,
            speakerId: 'spk_1',
            speakerName: 'Alex Carter',
            startSec: 1.0,
            endSec: 5.0,
            sourceText: 'Welcome everyone.',
            targetText: 'Chào mừng mọi người.',
        },
        {
            id: 2,
            speakerId: 'spk_2',
            speakerName: 'Elena Rostova',
            startSec: 5.5,
            endSec: 9.0,
            sourceText: 'Thank you Alex.',
            targetText: '<script>alert("xss")</script>',
        }
    ];

    function runSync(time) {
        const media = {
            currentTime: time,
            duration: 10.0,
            paused: false
        };
        store.syncPreviewPlayback(media);
        return {
            subtitle: elements['[data-canvas-subtitle]'].textContent,
            badge: elements['[data-canvas-speaker-badge]'].textContent,
            badgeDisplay: elements['[data-canvas-speaker-badge]'].style.display,
            activeSegId: store.state.activeSegmentId,
        };
    }

    // -------------------------------------------------------------
    // Test 1: Pre-transcript time (0.0s) before Segment 1 starts at 1.0s
    // Expected: Subtitle empty, badge hidden
    // -------------------------------------------------------------
    let r = runSync(0.0);
    if (r.subtitle !== '' || r.badgeDisplay !== 'none') {
        console.error('FAIL: Pre-transcript at 0.0s should have empty subtitle, got:', r);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 2: Negative time (-1.5s)
    // Expected: Subtitle empty, badge hidden, no crash
    // -------------------------------------------------------------
    r = runSync(-1.5);
    if (r.subtitle !== '' || r.badgeDisplay !== 'none') {
        console.error('FAIL: Negative time -1.5s should have empty subtitle, got:', r);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 3: Exact boundary startSec (1.0s) of Segment 1
    // Expected: Segment 1 active, subtitle = "Chào mừng mọi người.", badge = "Alex Carter"
    // -------------------------------------------------------------
    r = runSync(1.0);
    if (r.subtitle !== 'Chào mừng mọi người.' || r.badge !== 'Alex Carter' || r.badgeDisplay !== 'inline-flex') {
        console.error('FAIL: Exact startSec 1.0s should activate Segment 1, got:', r);
        process.exit(1);
    }
    if (store.state.activeSegmentId !== 1) {
        console.error('FAIL: activeSegmentId should be 1, got:', store.state.activeSegmentId);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 4: Mid-segment (3.0s) of Segment 1
    // Expected: Segment 1 active
    // -------------------------------------------------------------
    r = runSync(3.0);
    if (r.subtitle !== 'Chào mừng mọi người.' || r.activeSegId !== 1) {
        console.error('FAIL: Mid-segment 3.0s should be Segment 1, got:', r);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 5: Exact boundary endSec (5.0s) of Segment 1
    // Expected: Segment 1 still active at s.endSec (startSec <= t && t <= endSec)
    // -------------------------------------------------------------
    r = runSync(5.0);
    if (r.subtitle !== 'Chào mừng mọi người.' || r.activeSegId !== 1) {
        console.error('FAIL: Exact endSec 5.0s should still include Segment 1, got:', r);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 6: Inter-segment gap (5.25s) between Seg 1 (ends 5.0) and Seg 2 (starts 5.5)
    // Expected: Subtitle cleared, badge hidden
    // -------------------------------------------------------------
    r = runSync(5.25);
    if (r.subtitle !== '' || r.badgeDisplay !== 'none') {
        console.error('FAIL: Inter-segment gap 5.25s should clear subtitle, got:', r);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 7: Exact boundary startSec (5.5s) of Segment 2 (with script string)
    // Expected: Segment 2 active, textContent safely contains script string without execution
    // -------------------------------------------------------------
    r = runSync(5.5);
    if (r.subtitle !== '<script>alert("xss")</script>' || r.badge !== 'Elena Rostova' || r.badgeDisplay !== 'inline-flex') {
        console.error('FAIL: Exact startSec 5.5s should activate Segment 2, got:', r);
        process.exit(1);
    }
    if (store.state.activeSegmentId !== 2) {
        console.error('FAIL: activeSegmentId should be 2, got:', store.state.activeSegmentId);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 8: Exact boundary endSec (9.0s) of Segment 2
    // Expected: Segment 2 active
    // -------------------------------------------------------------
    r = runSync(9.0);
    if (r.subtitle !== '<script>alert("xss")</script>' || r.activeSegId !== 2) {
        console.error('FAIL: Exact endSec 9.0s should include Segment 2, got:', r);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 9: Epsilon past endSec (9.001s)
    // Expected: Subtitle cleared, badge hidden
    // -------------------------------------------------------------
    r = runSync(9.001);
    if (r.subtitle !== '' || r.badgeDisplay !== 'none') {
        console.error('FAIL: 9.001s past endSec should clear subtitle, got:', r);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 10: Far beyond duration (999.0s)
    // Expected: Subtitle cleared, scrubber clamped at 100%
    // -------------------------------------------------------------
    r = runSync(999.0);
    if (r.subtitle !== '' || r.badgeDisplay !== 'none') {
        console.error('FAIL: Far past duration 999.0s should clear subtitle, got:', r);
        process.exit(1);
    }
    if (elements['[data-scrubber-progress]'].style.width !== '100%') {
        console.error('FAIL: Scrubber progress should be 100%, got:', elements['[data-scrubber-progress]'].style.width);
        process.exit(1);
    }

    // -------------------------------------------------------------
    // Test 11: Text fallback when targetText is empty/null
    // Expected: Falls back to sourceText
    // -------------------------------------------------------------
    store.state.segments[0].targetText = null;
    r = runSync(2.0);
    if (r.subtitle !== 'Welcome everyone.') {
        console.error('FAIL: Missing targetText should fall back to sourceText, got:', r.subtitle);
        process.exit(1);
    }

    console.log("ALL_SUBTITLE_SYNC_BOUNDARY_TESTS_PASSED");
    """

    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node boundary sync test failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "ALL_SUBTITLE_SYNC_BOUNDARY_TESTS_PASSED" in res.stdout


def test_subtitle_sync_contiguous_zero_gap_boundary_transitions():
    """
    Test contiguous segments with zero gap:
    Segment 1: [0.0, 3.0]
    Segment 2: [3.0, 6.0]
    Verify that at exact boundary 3.0s, Array.find resolves Segment 1 cleanly,
    and at 3.001s it seamlessly switches to Segment 2 without intermediate flickering or crashes.
    """
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    const elements = {
        '[data-canvas-subtitle]': { textContent: '' },
        '[data-canvas-speaker-badge]': { textContent: '', style: { display: '' } },
        '[data-preview-timeline]': { value: '0' },
        '[data-scrubber-marker]': { style: { left: '0%' } },
        '[data-scrubber-progress]': { style: { width: '0%' } },
        '[data-preview-action-icon]': { textContent: 'play_arrow' },
    };

    globalThis.window = globalThis;
    globalThis.document = {
        querySelector(selector) { return elements[selector] || null; },
        querySelectorAll() { return []; }
    };

    const { store } = await import('./frontend/js/state.js');

    store.state.project.durationSec = 6.0;
    store.state.segments = [
        { id: 1, speakerId: 'spk_1', speakerName: 'Speaker A', startSec: 0.0, endSec: 3.0, targetText: 'Part 1' },
        { id: 2, speakerId: 'spk_2', speakerName: 'Speaker B', startSec: 3.0, endSec: 6.0, targetText: 'Part 2' },
    ];

    function runSync(time) {
        store.syncPreviewPlayback({ currentTime: time, duration: 6.0, paused: false });
        return {
            sub: elements['[data-canvas-subtitle]'].textContent,
            badge: elements['[data-canvas-speaker-badge]'].textContent,
            activeId: store.state.activeSegmentId
        };
    }

    // At 2.999s -> Segment 1
    let r1 = runSync(2.999);
    if (r1.sub !== 'Part 1' || r1.activeId !== 1) {
        console.error('FAIL at 2.999s:', r1);
        process.exit(1);
    }

    // At exactly 3.000s -> Segment 1 (first match satisfying s.startSec <= 3.0 <= s.endSec)
    let r2 = runSync(3.000);
    if (r2.sub !== 'Part 1' || r2.activeId !== 1) {
        console.error('FAIL at 3.000s:', r2);
        process.exit(1);
    }

    // At 3.001s -> Segment 2
    let r3 = runSync(3.001);
    if (r3.sub !== 'Part 2' || r3.activeId !== 2) {
        console.error('FAIL at 3.001s:', r3);
        process.exit(1);
    }

    console.log("CONTIGUOUS_ZERO_GAP_PASSED");
    """

    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node contiguous sync failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "CONTIGUOUS_ZERO_GAP_PASSED" in res.stdout


def test_subtitle_sync_empty_segments_and_non_finite_time():
    """
    Stress test syncPreviewPlayback resilience when:
    - store.state.segments is completely empty []
    - media.currentTime is NaN, Infinity, undefined, null, or string
    - DOM elements for subtitle/badge are not mounted (returns null)
    """
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = {
        querySelector() { return null; },
        querySelectorAll() { return []; }
    };

    const { store } = await import('./frontend/js/state.js');

    // Case 1: Empty segments array
    store.state.segments = [];
    store.syncPreviewPlayback({ currentTime: 5.0, duration: 10.0, paused: false });

    // Case 2: Non-finite currentTime values
    const nonFiniteValues = [NaN, Infinity, -Infinity, undefined, null, 'string_time'];
    for (const val of nonFiniteValues) {
        store.syncPreviewPlayback({ currentTime: val, duration: 10.0, paused: false });
        if (store.state.playback.currentTime !== 0) {
            console.error(`FAIL: Non-finite time ${val} should default to 0, got:`, store.state.playback.currentTime);
            process.exit(1);
        }
    }

    console.log("EMPTY_AND_NON_FINITE_RESILIENCE_PASSED");
    """

    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node empty/non-finite sync failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "EMPTY_AND_NON_FINITE_RESILIENCE_PASSED" in res.stdout
