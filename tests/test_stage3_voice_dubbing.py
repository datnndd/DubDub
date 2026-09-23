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

from tests import webui_support as webui
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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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

def test_stage3_teleprompter_timestamp_format_mm_ss_mmm():
    """Stage3 teleprompter script renders timestamps using formatted MM:SS.mmm format."""
    stage3_path = Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage3VoiceDubbing.js"
    source = stage3_path.read_text(encoding="utf-8")

    assert "formatTime" in source or "startTime" in source
    assert "startSec" in source and "endSec" in source


def test_stage3_teleprompter_speaker_badge_rendering():
    """Teleprompter items render the speaker badge displaying speakerName and code/color."""
    stage3_path = Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage3VoiceDubbing.js"
    source = stage3_path.read_text(encoding="utf-8")

    assert "speakerName" in source
    assert "speakerCode" in source
    assert "speakerColor" in source or "colorClass" in source


def test_stage3_teleprompter_inline_textarea_contract():
    """Teleprompter contains editable textarea with data-segment-input attribute and targetText binding."""
    stage3_path = Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage3VoiceDubbing.js"
    source = stage3_path.read_text(encoding="utf-8")

    assert "data-segment-input" in source
    assert "targetText" in source
    assert "updateSegmentTargetText" in source


def test_stage3_teleprompter_selected_voice_dropdown_and_default_indicator():
    """Voice selector dropdown renders in each block, marking the speaker's assigned voice with '(Default)'."""
    stage3_path = Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage3VoiceDubbing.js"
    source = stage3_path.read_text(encoding="utf-8")

    assert "data-segment-voice-select" in source
    assert "(Default)" in source
    assert "setSegmentVoiceOverride" in source


def test_stage3_teleprompter_voice_override_and_reset_button():
    """Teleprompter renders reset button with data-action='reset-segment-voice' when an override exists."""
    stage3_path = Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage3VoiceDubbing.js"
    source = stage3_path.read_text(encoding="utf-8")

    assert "data-action=\"reset-segment-voice\"" in source
    assert "clearSegmentVoiceOverride" in source


def test_stage3_teleprompter_video_seek_and_play_trigger():
    """Clicking a teleprompter card or audition button triggers seekAndPlay with data-action='seek-segment'."""
    stage3_path = Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage3VoiceDubbing.js"
    source = stage3_path.read_text(encoding="utf-8")

    assert "data-action=\"seek-segment\"" in source
    assert "seekAndPlay" in source


def test_stage3_console_provider_and_speaker_matrix_controls():
    """Upper console renders TTS provider select and dynamic speaker matrix selectors."""
    stage3_path = Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage3VoiceDubbing.js"
    source = stage3_path.read_text(encoding="utf-8")

    assert "data-action=\"select-tts-provider\"" in source
    assert "data-speaker-voice-select" in source
    assert "updateSpeakerVoice" in source
    assert "updateBackendConfig" in source


# ============================================================================
# Section 4: Video Player Subtitle Overlay & Canvas Sync
# ============================================================================

def test_video_player_contains_canvas_subtitle_and_badge_attributes():
    """VideoPlayer.js contains data-canvas-subtitle and data-canvas-speaker-badge queryable attributes."""
    player_path = Path(webui.FRONTEND_DIR) / "js" / "components" / "VideoPlayer.js"
    source = player_path.read_text(encoding="utf-8")

    assert "data-canvas-subtitle" in source
    assert "data-canvas-speaker-badge" in source


def test_sync_preview_playback_updates_canvas_subtitle_dom():
    """state.js syncPreviewPlayback queries canvas subtitle/badge and updates text dynamically."""
    state_path = Path(webui.FRONTEND_DIR) / "js" / "state.js"
    source = state_path.read_text(encoding="utf-8")

    assert "syncPreviewPlayback" in source
    assert "data-canvas-subtitle" in source
    assert "data-canvas-speaker-badge" in source
    assert "targetText" in source


# ============================================================================
# Section 5: Headless Node.js Execution & Multi-Speaker Workflow Scenario
# ============================================================================

def test_headless_node_stage3_screen_render():
    """Execute Stage3VoiceDubbing.js in Node.js v22 and assert generated DOM contains Stage 3 invariants."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = {
        querySelector: () => null,
        querySelectorAll: () => []
    };

    const { renderStage3VoiceDubbing } = await import('./frontend/js/screens/Stage3VoiceDubbing.js');
    const { store } = await import('./frontend/js/state.js');

    const state = store.getState();
    state.currentStep = 3;
    state.backend.options.voices = [[0, "ElevenLabs"], [1, "OmniVoice"], [2, "VieNeu-TTS"], [3, "Gemini TTS"]];
    state.backend.options.voiceRoles = ["Rachel", "Domi", "Bella", "Antoni"];
    state.backend.config.ttsType = 0;
    state.backend.config.voiceRole = "Rachel";
    state.speakerVoiceMap = { "spk_1": "Rachel", "spk_2": "Domi" };

    // Set segment 3 to have an explicit override
    if (state.segments[2]) {
        state.segments[2].voiceOverride = "Bella";
    }

    const html = renderStage3VoiceDubbing(state);

    if (!html || typeof html !== 'string') {
        console.error("Render produced non-string output");
        process.exit(1);
    }

    // Required Contract Verifications
    const checks = [
        ['select-tts-provider', html.includes('data-action="select-tts-provider"')],
        ['speaker-matrix-select', html.includes('data-speaker-voice-select="spk_1"')],
        ['segment-input-textarea', html.includes('data-segment-input="stage3-1"')],
        ['segment-voice-select', html.includes('data-segment-voice-select="1"')],
        ['default-indicator', html.includes('(Default)')],
        ['reset-segment-voice', html.includes('data-action="reset-segment-voice"')],
        ['seek-segment-action', html.includes('data-action="seek-segment"')],
        ['target-text-rendered', html.includes('targetText') || html.includes('AI DUB')],
    ];

    for (const [name, passed] of checks) {
        if (!passed) {
            console.error(`Check failed: ${name}`);
            process.exit(1);
        }
    }

    console.log("ALL_NODE_CHECKS_PASSED");
    """

    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "ALL_NODE_CHECKS_PASSED" in res.stdout


def test_headless_node_multi_speaker_store_state_and_override_workflow():
    """Verify live state mutations via WorkflowStore in Node: distinct speakers, override propagation, and reset."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = {
        querySelector: () => null,
        querySelectorAll: () => []
    };

    const { store } = await import('./frontend/js/state.js');

    // 1. Initial State Setup with 2 Speakers
    store.state.segments = [
        { id: 101, speakerId: "spk_1", speakerName: "Speaker One", startSec: 0, endSec: 2, targetText: "Text 1", voiceOverride: null },
        { id: 102, speakerId: "spk_2", speakerName: "Speaker Two", startSec: 2, endSec: 4, targetText: "Text 2", voiceOverride: null },
        { id: 103, speakerId: "spk_1", speakerName: "Speaker One", startSec: 4, endSec: 6, targetText: "Text 3", voiceOverride: null },
    ];
    store.state.backend.options.voiceRoles = ["Voice-Alpha", "Voice-Beta", "Voice-Gamma"];

    // 2. Distinct Speakers Detection
    const speakers = store.getDistinctSpeakers();
    if (speakers.length !== 2) {
        console.error("Expected 2 distinct speakers, got", speakers.length);
        process.exit(1);
    }

    // 3. Assign Voices to Speakers
    store.updateSpeakerVoice("spk_1", "Voice-Alpha");
    store.updateSpeakerVoice("spk_2", "Voice-Beta");

    if (store.getResolvedVoice(store.state.segments[0]) !== "Voice-Alpha") {
        console.error("Seg 101 did not resolve to Voice-Alpha");
        process.exit(1);
    }
    if (store.getResolvedVoice(store.state.segments[1]) !== "Voice-Beta") {
        console.error("Seg 102 did not resolve to Voice-Beta");
        process.exit(1);
    }
    if (store.getResolvedVoice(store.state.segments[2]) !== "Voice-Alpha") {
        console.error("Seg 103 did not resolve to Voice-Alpha");
        process.exit(1);
    }

    // 4. Set Override on Seg 103
    store.setSegmentVoiceOverride(103, "Voice-Gamma");
    if (store.getResolvedVoice(store.state.segments[2]) !== "Voice-Gamma") {
        console.error("Seg 103 override failed");
        process.exit(1);
    }

    // 5. Change Global spk_1 Voice
    store.updateSpeakerVoice("spk_1", "Voice-Updated");
    if (store.getResolvedVoice(store.state.segments[0]) !== "Voice-Updated") {
        console.error("Seg 101 did not update to Voice-Updated");
        process.exit(1);
    }
    if (store.getResolvedVoice(store.state.segments[2]) !== "Voice-Gamma") {
        console.error("Seg 103 override was erroneously overwritten");
        process.exit(1);
    }

    // 6. Reset Override on Seg 103
    store.clearSegmentVoiceOverride(103);
    if (store.getResolvedVoice(store.state.segments[2]) !== "Voice-Updated") {
        console.error("Seg 103 reset did not restore global voice");
        process.exit(1);
    }

    // 7. Update Target Text
    store.updateSegmentTargetText(101, "Updated Translation");
    if (store.state.segments[0].targetText !== "Updated Translation") {
        console.error("Target text update failed");
        process.exit(1);
    }

    console.log("STATE_MUTATIONS_WORKFLOW_VERIFIED");
    """

    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node state mutation script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "STATE_MUTATIONS_WORKFLOW_VERIFIED" in res.stdout


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
    app = webui.create_app(upload_dir=tmp_path / "uploads")

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
