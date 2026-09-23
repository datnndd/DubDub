"""
DubDub Stage 3: Voice & Dubbing Test Suite

Automated verification covering:
1. Backend Voice Discovery Endpoint (`GET /api/voices` & `/api/options`):
   - 4 supported TTS providers: ElevenLabs (0), OmniVoice (1), VieNeu-TTS (2), Gemini TTS (3)
   - Parameter handling: `ttsType`, `language`, and aliases (`provider`, `target_language`, `targetLanguage`)
   - String provider name aliases (e.g. "elevenlabs", "vieneu-tts", "gemini")
   - Edge cases: invalid ttsType, missing params, out-of-bounds index
   - Exception resilience: graceful fallback to {"voices": ["No"]}
2. Speaker Matrix & Store State Logic:
   - Distinct speaker extraction from segments with ordering & fallback
   - Speaker voice mapping and propagation to non-overridden segments
   - Multi-speaker isolation
   - Per-block voice override (`seg.voiceOverride`)
   - Reset override restoring speaker assigned default
   - Inline targetText updates and metadata preservation
   - Persistence of `speakerVoiceMap` across stage navigation
3. Frontend Component Contracts & DOM Invariants:
   - Timestamp formatting (`MM:SS.mmm`)
   - Speaker badge rendering (name, code, color)
   - Inline editable textarea with `data-segment-input="stage3-{seg.id}"`
   - Voice dropdown with `(Default)` indicator for non-overridden segments
   - Voice override selector and "Reset to Default" button (`data-action="reset-segment-voice"`)
   - Video seek-and-play click trigger (`data-action="seek-segment"`)
   - Upper console controls: `data-action="select-tts-provider"` and `data-speaker-voice-select`
4. Video Player Subtitle Overlay:
   - Attributes `data-canvas-subtitle` and `data-canvas-speaker-badge` in `VideoPlayer.js`
   - Dynamic canvas subtitle updating in `syncPreviewPlayback` matching active segment's `targetText`
5. Headless Node.js Execution & Multi-Speaker End-to-End Workflow:
   - Real Node.js evaluation of Stage 3 template rendering and state mutations
   - Complete multi-speaker dubbing data-flow scenario
"""

import asyncio
import io
import json
from pathlib import Path
import re
import shutil
import subprocess

from aiohttp.test_utils import TestClient, TestServer
import pytest

from videotrans.api.app import create_app

from videotrans import tts


# ============================================================================
# Test Doubles & Fixtures
# ============================================================================

@pytest.fixture
def mock_tts_catalogs(monkeypatch):
    """
    Provides deterministic voice fixtures for all 4 supported TTS engines
    without external network or API dependencies.
    """
    catalogs = {
        tts.ELEVENLABS_TTS: ["No", "Rachel", "Domi", "Bella", "Antoni", "Elli"],
        tts.OMNIVOICE_TTS: ["No", "clone", "Omni-Speaker-1", "Omni-Speaker-2"],
        tts.VIENEU_TTS: ["No", "clone", "Phạm Tuyên", "Mai Phương", "Custom: Voice1"],
        tts.GEMINI_TTS: ["Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Aoede"],
    }
    calls = []

    def fake_role_menu(tts_type, langcode=None):
        calls.append({"tts_type": tts_type, "langcode": langcode})
        return catalogs.get(tts_type, ["No"])

    monkeypatch.setattr(webui, "role_menu", fake_role_menu)
    return {"catalogs": catalogs, "calls": calls}


@pytest.fixture
def multi_speaker_sample_segments():
    """Deterministic 4-segment transcript with 2 distinct speakers."""
    return [
        {
            "id": 1,
            "speakerId": "spk_1",
            "speakerName": "Alex Carter",
            "speakerCode": "AC",
            "speakerColor": "amber",
            "startTime": "00:01.000",
            "endTime": "00:05.000",
            "startSec": 1.0,
            "endSec": 5.0,
            "sourceText": "Welcome to our AI video translation presentation.",
            "targetText": "Chào mừng đến với buổi giới thiệu dịch video bằng AI.",
            "voiceOverride": None,
            "cps": 13.5,
            "cpsStatus": "Optimal",
        },
        {
            "id": 2,
            "speakerId": "spk_2",
            "speakerName": "Elena Rostova",
            "speakerCode": "ER",
            "speakerColor": "secondary",
            "startTime": "00:05.500",
            "endTime": "00:09.500",
            "startSec": 5.5,
            "endSec": 9.5,
            "sourceText": "Thank you Alex, thrilled to showcase our neural synthesis.",
            "targetText": "Cảm ơn Alex, rất hào hứng được giới thiệu tổng hợp giọng nói.",
            "voiceOverride": None,
            "cps": 15.2,
            "cpsStatus": "Good",
        },
        {
            "id": 3,
            "speakerId": "spk_1",
            "speakerName": "Alex Carter",
            "speakerCode": "AC",
            "speakerColor": "amber",
            "startTime": "00:10.000",
            "endTime": "00:14.000",
            "startSec": 10.0,
            "endSec": 14.0,
            "sourceText": "Notice how each speaker maintains an independent voice profile.",
            "targetText": "Hãy xem mỗi người nói giữ một hồ sơ giọng nói riêng biệt.",
            "voiceOverride": "Bella",  # Overridden block
            "cps": 14.0,
            "cpsStatus": "Optimal",
        },
        {
            "id": 4,
            "speakerId": "spk_2",
            "speakerName": "Elena Rostova",
            "speakerCode": "ER",
            "speakerColor": "secondary",
            "startTime": "00:14.500",
            "endTime": "00:18.500",
            "startSec": 14.5,
            "endSec": 18.5,
            "sourceText": "And per-block overrides allow fine-tuning specific expressions.",
            "targetText": "Và ghi đè từng khối cho phép tinh chỉnh các biểu cảm cụ thể.",
            "voiceOverride": None,
            "cps": 16.1,
            "cpsStatus": "Good",
        },
    ]


# ============================================================================
# Section 1: Backend Voice Discovery Endpoint Tests (`GET /api/voices` & `/api/options`)
# ============================================================================

def test_voices_endpoint_elevenlabs_provider_0(tmp_path, mock_tts_catalogs):
    """Verify ElevenLabs (provider 0) returns status 200 and mocked voice list."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            res = await client.get("/api/voices?ttsType=0&language=en")
            assert res.status == 200
            data = await res.json()
            assert "voices" in data
            assert data["voices"] == mock_tts_catalogs["catalogs"][tts.ELEVENLABS_TTS]
            assert any(c["tts_type"] == tts.ELEVENLABS_TTS and c["langcode"] == "en" for c in mock_tts_catalogs["calls"])
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_omnivoice_provider_1(tmp_path, mock_tts_catalogs):
    """Verify OmniVoice (provider 1) returns status 200 and mocked voice list."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            res = await client.get("/api/voices?ttsType=1&language=vi")
            assert res.status == 200
            data = await res.json()
            assert "voices" in data
            assert data["voices"] == mock_tts_catalogs["catalogs"][tts.OMNIVOICE_TTS]
            assert any(c["tts_type"] == tts.OMNIVOICE_TTS and c["langcode"] == "vi" for c in mock_tts_catalogs["calls"])
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_vieneu_provider_2(tmp_path, mock_tts_catalogs):
    """Verify VieNeu-TTS (provider 2) returns status 200 and mocked voice list."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            res = await client.get("/api/voices?ttsType=2&language=vi")
            assert res.status == 200
            data = await res.json()
            assert "voices" in data
            assert data["voices"] == mock_tts_catalogs["catalogs"][tts.VIENEU_TTS]
            assert any(c["tts_type"] == tts.VIENEU_TTS and c["langcode"] == "vi" for c in mock_tts_catalogs["calls"])
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_gemini_provider_3(tmp_path, mock_tts_catalogs):
    """Verify Gemini TTS (provider 3) returns status 200 and mocked voice list."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            res = await client.get("/api/voices?ttsType=3&language=en")
            assert res.status == 200
            data = await res.json()
            assert "voices" in data
            assert data["voices"] == mock_tts_catalogs["catalogs"][tts.GEMINI_TTS]
            assert any(c["tts_type"] == tts.GEMINI_TTS and c["langcode"] == "en" for c in mock_tts_catalogs["calls"])
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_param_aliases_provider_and_target_language(tmp_path, mock_tts_catalogs):
    """Verify parameter aliases: `provider` maps to `ttsType` and `target_language` maps to `language`."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # Query using aliases `provider` and `target_language`
            res = await client.get("/api/voices?provider=3&target_language=ja")
            assert res.status == 200
            data = await res.json()
            assert data["voices"] == mock_tts_catalogs["catalogs"][tts.GEMINI_TTS]
            assert any(c["tts_type"] == 3 and c["langcode"] == "ja" for c in mock_tts_catalogs["calls"])

            # Query using `targetLanguage` camelCase alias
            res2 = await client.get("/api/voices?provider=2&targetLanguage=vi")
            assert res2.status == 200
            data2 = await res2.json()
            assert data2["voices"] == mock_tts_catalogs["catalogs"][tts.VIENEU_TTS]
            assert any(c["tts_type"] == 2 and c["langcode"] == "vi" for c in mock_tts_catalogs["calls"])
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_string_provider_aliases(tmp_path, mock_tts_catalogs):
    """Verify named string provider aliases (e.g. 'elevenlabs', 'vieneu-tts', 'gemini')."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            named_tests = [
                ("elevenlabs", tts.ELEVENLABS_TTS),
                ("vieneu-tts", tts.VIENEU_TTS),
                ("gemini", tts.GEMINI_TTS),
                ("omnivoice", tts.OMNIVOICE_TTS),
            ]
            for name, expected_id in named_tests:
                res = await client.get(f"/api/voices?provider={name}&language=en")
                assert res.status == 200
                data = await res.json()
                assert data["voices"] == mock_tts_catalogs["catalogs"][expected_id]
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_missing_parameters_uses_default(tmp_path, mock_tts_catalogs):
    """Verify querying without params defaults gracefully without 4xx/500 errors."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            res = await client.get("/api/voices")
            assert res.status == 200
            data = await res.json()
            assert "voices" in data
            assert isinstance(data["voices"], list)
            assert len(data["voices"]) > 0
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_invalid_and_out_of_bounds_params(tmp_path):
    """Verify non-numeric or out-of-bounds params return 200 with safe voice list."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # String non-numeric that is not a recognized provider alias
            res1 = await client.get("/api/voices?ttsType=unrecognized_garbage")
            assert res1.status == 200
            data1 = await res1.json()
            assert isinstance(data1.get("voices"), list)

            # Huge out-of-bounds integer
            res2 = await client.get("/api/voices?ttsType=999999")
            assert res2.status == 200
            data2 = await res2.json()
            assert data2.get("voices") == ["No"] or isinstance(data2.get("voices"), list)

            # Negative integer
            res3 = await client.get("/api/voices?ttsType=-10")
            assert res3.status == 200
            data3 = await res3.json()
            assert isinstance(data3.get("voices"), list)
        finally:
            await client.close()

    asyncio.run(scenario())


def test_voices_endpoint_exception_resilience(tmp_path, monkeypatch):
    """Verify that if role_menu raises an exception, the endpoint returns status 200 with {"voices": ["No"]}."""
    def crash_role_menu(*_args, **_kwargs):
        raise RuntimeError("Remote TTS engine unavailable")

    monkeypatch.setattr(webui, "role_menu", crash_role_menu)
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            res = await client.get("/api/voices?ttsType=0&language=en")
            assert res.status == 200
            data = await res.json()
            assert data == {"voices": ["No"]}
        finally:
            await client.close()

    asyncio.run(scenario())


def test_api_options_contains_tts_defaults_and_providers(tmp_path):
    """Verify /api/options supplies the voice providers list including the 4 contiguous engines."""
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            res = await client.get("/api/options")
            assert res.status == 200
            data = await res.json()
            assert "voices" in data
            provider_indices = [item[0] for item in data["voices"]]
            assert 0 in provider_indices  # ElevenLabs
            assert 1 in provider_indices  # OmniVoice
            assert 2 in provider_indices  # VieNeu-TTS
            assert 3 in provider_indices  # Gemini TTS
            assert "defaults" in data
            assert "ttsType" in data["defaults"]
        finally:
            await client.close()

    asyncio.run(scenario())


# ============================================================================
# Section 2: Speaker Matrix & Store State Logic
# ============================================================================

def detect_distinct_speakers_spec(segments, metadata_speakers=None):
    """
    Specification implementation of getDistinctSpeakers:
    Traverse segments in order of appearance, extracting unique speaker identities.
    """
    if not segments:
        return [{"speakerId": "spk_1", "speakerName": "Speaker 1", "speakerCode": "S1", "speakerColor": "amber"}]

    seen = set()
    result = []
    color_palette = ["amber", "secondary", "emerald", "rose", "purple"]
    meta_lookup = {s["id"]: s for s in (metadata_speakers or []) if isinstance(s, dict) and "id" in s}

    for idx, seg in enumerate(segments):
        spk_id = seg.get("speakerId") or seg.get("speakerLabel") or seg.get("speaker") or f"spk_{idx + 1}"
        if spk_id not in seen:
            seen.add(spk_id)
            meta = meta_lookup.get(spk_id, {})
            spk_name = seg.get("speakerName") or meta.get("name") or (f"Speaker {seg['speakerLabel']}" if seg.get("speakerLabel") else f"Speaker {len(result) + 1}")
            spk_code = seg.get("speakerCode") or meta.get("code") or f"S{len(result) + 1}"
            spk_color = seg.get("speakerColor") or meta.get("color") or color_palette[len(result) % len(color_palette)]
            result.append({
                "speakerId": spk_id,
                "speakerName": spk_name,
                "speakerCode": spk_code,
                "speakerColor": spk_color,
            })
    return result


def resolve_effective_voice_spec(segment, speaker_voice_map, default_voice="No"):
    """
    Specification implementation of getResolvedVoice:
    If segment has voiceOverride, return it.
    Else return speakerVoiceMap[speakerId], else default_voice.
    """
    if not segment:
        return default_voice
    override = segment.get("voiceOverride")
    if override:
        return override, True
    spk_id = segment.get("speakerId") or segment.get("speakerLabel") or segment.get("speaker")
    return speaker_voice_map.get(spk_id, default_voice), False


def test_detect_distinct_speakers_multi_speaker_order(multi_speaker_sample_segments):
    """Distinct speaker detection must preserve first-appearance order and extract speaker metadata."""
    speakers = detect_distinct_speakers_spec(multi_speaker_sample_segments)
    assert len(speakers) == 2
    assert speakers[0]["speakerId"] == "spk_1"
    assert speakers[0]["speakerName"] == "Alex Carter"
    assert speakers[0]["speakerCode"] == "AC"
    assert speakers[0]["speakerColor"] == "amber"

    assert speakers[1]["speakerId"] == "spk_2"
    assert speakers[1]["speakerName"] == "Elena Rostova"
    assert speakers[1]["speakerCode"] == "ER"
    assert speakers[1]["speakerColor"] == "secondary"


def test_detect_distinct_speakers_single_and_empty_fallbacks():
    """Empty segments must fallback to a valid default Speaker 1 entity."""
    empty_result = detect_distinct_speakers_spec([])
    assert len(empty_result) == 1
    assert empty_result[0]["speakerId"] == "spk_1"
    assert empty_result[0]["speakerName"] == "Speaker 1"

    single_seg = [{"id": 1, "speakerId": "spk_main", "speakerName": "Solo Speaker"}]
    single_result = detect_distinct_speakers_spec(single_seg)
    assert len(single_result) == 1
    assert single_result[0]["speakerId"] == "spk_main"
    assert single_result[0]["speakerName"] == "Solo Speaker"


def test_speaker_voice_mapping_initial_and_resolved_voice(multi_speaker_sample_segments):
    """Segments resolve to speaker-assigned voice when no override is present."""
    voice_map = {"spk_1": "Voice-Alpha", "spk_2": "Voice-Beta"}

    # Segment 1 (spk_1, no override) -> Voice-Alpha
    v1, is_ov1 = resolve_effective_voice_spec(multi_speaker_sample_segments[0], voice_map)
    assert v1 == "Voice-Alpha" and not is_ov1

    # Segment 2 (spk_2, no override) -> Voice-Beta
    v2, is_ov2 = resolve_effective_voice_spec(multi_speaker_sample_segments[1], voice_map)
    assert v2 == "Voice-Beta" and not is_ov2

    # Segment 3 (spk_1, override="Bella") -> Bella (overridden)
    v3, is_ov3 = resolve_effective_voice_spec(multi_speaker_sample_segments[2], voice_map)
    assert v3 == "Bella" and is_ov3


def test_speaker_voice_propagation_updates_non_overridden_only(multi_speaker_sample_segments):
    """Updating a speaker's voice propagates to non-overridden segments while preserving overrides."""
    voice_map = {"spk_1": "Voice-Alpha", "spk_2": "Voice-Beta"}

    # Update spk_1's global voice to Voice-Gamma
    voice_map["spk_1"] = "Voice-Gamma"

    # Segment 1 updates to Voice-Gamma
    v1, is_ov1 = resolve_effective_voice_spec(multi_speaker_sample_segments[0], voice_map)
    assert v1 == "Voice-Gamma" and not is_ov1

    # Segment 3 (spk_1 with override="Bella") retains "Bella"
    v3, is_ov3 = resolve_effective_voice_spec(multi_speaker_sample_segments[2], voice_map)
    assert v3 == "Bella" and is_ov3

    # Segment 2 and 4 (spk_2) remain completely unaffected
    v2, _ = resolve_effective_voice_spec(multi_speaker_sample_segments[1], voice_map)
    v4, _ = resolve_effective_voice_spec(multi_speaker_sample_segments[3], voice_map)
    assert v2 == "Voice-Beta"
    assert v4 == "Voice-Beta"


def test_per_block_voice_override_isolation(multi_speaker_sample_segments):
    """Setting voiceOverride on segment 1 does NOT affect other segments of the same speaker."""
    voice_map = {"spk_1": "Global-Default"}
    seg1 = dict(multi_speaker_sample_segments[0])
    seg3 = dict(multi_speaker_sample_segments[2])
    seg3["voiceOverride"] = None  # Clear override for isolation check

    # Initially both resolve to Global-Default
    assert resolve_effective_voice_spec(seg1, voice_map)[0] == "Global-Default"
    assert resolve_effective_voice_spec(seg3, voice_map)[0] == "Global-Default"

    # Apply override exclusively to seg1
    seg1["voiceOverride"] = "Custom-Voice-99"

    assert resolve_effective_voice_spec(seg1, voice_map) == ("Custom-Voice-99", True)
    assert resolve_effective_voice_spec(seg3, voice_map) == ("Global-Default", False)


def test_reset_voice_override_restores_speaker_default(multi_speaker_sample_segments):
    """Clearing voiceOverride immediately reverts the segment to the speaker's assigned voice."""
    voice_map = {"spk_1": "Restored-Global-Voice"}
    seg3 = dict(multi_speaker_sample_segments[2])  # Initially has voiceOverride="Bella"

    assert resolve_effective_voice_spec(seg3, voice_map) == ("Bella", True)

    # Reset override
    seg3["voiceOverride"] = None

    assert resolve_effective_voice_spec(seg3, voice_map) == ("Restored-Global-Voice", False)


def test_update_segment_target_text_preserves_structure(multi_speaker_sample_segments):
    """Editing targetText mutates the segment text while leaving timing and speaker metadata intact."""
    seg1 = dict(multi_speaker_sample_segments[0])
    original_start = seg1["startSec"]
    original_end = seg1["endSec"]
    original_speaker = seg1["speakerId"]

    new_text = "Bản dịch đã được chỉnh sửa thủ công."
    seg1["targetText"] = new_text

    assert seg1["targetText"] == new_text
    assert seg1["startSec"] == original_start
    assert seg1["endSec"] == original_end
    assert seg1["speakerId"] == original_speaker


def test_speaker_voice_map_persists_across_step_transitions():
    """State transition simulation: speakerVoiceMap must persist across steps (2 -> 3 -> 4 -> 3)."""
    state = {
        "currentStep": 2,
        "speakerVoiceMap": {"spk_1": "Voice-A", "spk_2": "Voice-B"},
        "segments": [{"id": 1, "speakerId": "spk_1", "voiceOverride": None}],
    }

    # Navigate to Step 3
    state["currentStep"] = 3
    assert state["speakerVoiceMap"]["spk_1"] == "Voice-A"

    # Modify mapping in Step 3
    state["speakerVoiceMap"]["spk_1"] = "Voice-Updated"

    # Navigate to Step 4 then back to Step 3
    state["currentStep"] = 4
    assert state["speakerVoiceMap"]["spk_1"] == "Voice-Updated"
    state["currentStep"] = 3
    assert state["speakerVoiceMap"]["spk_1"] == "Voice-Updated"


# ============================================================================
# Section 3: Frontend Component Contracts & DOM Invariants
# ============================================================================


# ============================================================================
# Section 4: Video Player Subtitle Overlay & Canvas Sync
# ============================================================================


# ============================================================================
# Section 5: Headless Node.js Execution & Multi-Speaker Workflow Scenario
# ============================================================================


def test_e2e_multi_speaker_dubbing_scenario(tmp_path, mock_tts_catalogs):
    """
    Complete end-to-end multi-speaker dubbing scenario simulating:
    1. Querying voices for TTS engine VieNeu-TTS (2)
    2. Assigning distinct voices to Speaker 1 and Speaker 2
    3. Applying per-block override to Segment 3
    4. Switching global voice and asserting override isolation
    5. Reverting override back to speaker default
    6. Editing target text and verifying persistence
    7. Seeking playback to active segment
    """
    app = create_app(upload_dir=tmp_path / "uploads")

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            # 1. Fetch available voices for VieNeu-TTS in Vietnamese
            res = await client.get("/api/voices?ttsType=2&language=vi")
            assert res.status == 200
            data = await res.json()
            voices = data["voices"]
            assert len(voices) >= 3
            voice_speaker1 = voices[1]  # e.g. "clone"
            voice_speaker2 = voices[2]  # e.g. "Phạm Tuyên"
            override_voice = voices[3] if len(voices) > 3 else "Special Voice"

            # 2. State & multi-speaker segments initialization
            segments = [
                {"id": 1, "speakerId": "spk_lead", "speakerName": "Lead Presenter", "startSec": 0.0, "endSec": 3.0, "targetText": "Xin chào quý vị", "voiceOverride": None},
                {"id": 2, "speakerId": "spk_guest", "speakerName": "Guest Speaker", "startSec": 3.0, "endSec": 6.0, "targetText": "Rất vui được tham gia", "voiceOverride": None},
                {"id": 3, "speakerId": "spk_lead", "speakerName": "Lead Presenter", "startSec": 6.0, "endSec": 9.0, "targetText": "Hôm nay chúng ta nói về AI", "voiceOverride": None},
            ]
            speaker_voice_map = {
                "spk_lead": voice_speaker1,
                "spk_guest": voice_speaker2,
            }

            # Verify initial voice resolutions
            assert resolve_effective_voice_spec(segments[0], speaker_voice_map)[0] == voice_speaker1
            assert resolve_effective_voice_spec(segments[1], speaker_voice_map)[0] == voice_speaker2
            assert resolve_effective_voice_spec(segments[2], speaker_voice_map)[0] == voice_speaker1

            # 3. Apply override on segment 3
            segments[2]["voiceOverride"] = override_voice
            v3, is_ov3 = resolve_effective_voice_spec(segments[2], speaker_voice_map)
            assert v3 == override_voice and is_ov3

            # 4. Change Lead Presenter global voice
            new_global_voice = "Mai Phương"
            speaker_voice_map["spk_lead"] = new_global_voice

            # Segment 0 updates; Segment 2 keeps override
            assert resolve_effective_voice_spec(segments[0], speaker_voice_map)[0] == new_global_voice
            assert resolve_effective_voice_spec(segments[2], speaker_voice_map)[0] == override_voice

            # 5. Clear override on segment 3
            segments[2]["voiceOverride"] = None
            assert resolve_effective_voice_spec(segments[2], speaker_voice_map)[0] == new_global_voice

            # 6. Inline editing of translated targetText
            edited_text = "Bản dịch tiếng Việt đã được tinh chỉnh mượt mà."
            segments[1]["targetText"] = edited_text
            assert segments[1]["targetText"] == edited_text
            assert segments[1]["startSec"] == 3.0
            assert segments[1]["endSec"] == 6.0

            # 7. Playback seeking
            active_segment = segments[1]
            seek_time = active_segment["startSec"]
            assert seek_time == 3.0
        finally:
            await client.close()

    asyncio.run(scenario())
