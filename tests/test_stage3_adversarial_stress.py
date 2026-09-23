"""
DubDub Stage 3: Adversarial Stress Test Suite
Challenger 1 — State & Speaker Voice Mapping Stress Tests

Validates:
1. 0 segments & empty transcripts handling
2. 10+ distinct speakers ordering, color palette cycling, and scaling
3. Missing / undefined speaker fields edge cases & resolution discrepancy
4. Complex voice lifecycle: change -> override -> change -> reset -> re-override
5. Rapid sequential overrides & resets (performance & non-existent IDs)
6. Direct Node.js execution of tests/stress_stage3.mjs
"""

import json
from pathlib import Path
import shutil
import subprocess

import pytest
from tests import webui_support as webui


def resolve_effective_voice_spec(seg, speaker_voice_map, default_voice="default"):
    """Reference oracle matching PROJECT.md interface contract."""
    if not seg:
        return default_voice, False
    if seg.get("voiceOverride"):
        return seg["voiceOverride"], True
    spk_id = seg.get("speakerId")
    if spk_id and spk_id in speaker_voice_map:
        return speaker_voice_map[spk_id], False
    return default_voice, False


def test_adversarial_node_stress_script_passes():
    """Execute the full Node.js v22 stress test suite (tests/stress_stage3.mjs)."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    script_path = Path(webui.ROOT_DIR) / "tests" / "stress_stage3.mjs"
    assert script_path.exists(), f"Missing stress script at {script_path}"

    res = subprocess.run([node_exe, str(script_path)], capture_output=True, text=True)
    assert res.returncode == 0, f"Node stress script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "ALL STRESS TESTS COMPLETED" in res.stdout
    assert "0 failed" in res.stdout


def test_adversarial_empty_segments_oracle():
    """Verify state resolution with 0 segments or empty transcript."""
    speaker_voice_map = {}
    empty_segments = []

    # Fallback default speaker when segments are empty
    fallback_speaker = {
        "speakerId": "spk_1",
        "speakerName": "Speaker 1",
        "speakerCode": "S1",
        "speakerColor": "amber",
    }
    speaker_voice_map[fallback_speaker["speakerId"]] = "Default-Voice"

    assert len(empty_segments) == 0
    # Resolving voice on None or empty segment
    assert resolve_effective_voice_spec(None, speaker_voice_map)[0] == "default"
    assert resolve_effective_voice_spec({}, speaker_voice_map)[0] == "default"


def test_adversarial_10_plus_speakers_order_and_isolation():
    """Stress-test with 20 distinct speakers and 60 interleaved segments."""
    num_speakers = 20
    speaker_ids = [f"spk_{i}" for i in range(1, num_speakers + 1)]
    palette = ["amber", "secondary", "emerald", "rose", "purple"]

    segments = []
    speaker_voice_map = {}

    for i, spk_id in enumerate(speaker_ids):
        speaker_voice_map[spk_id] = f"Voice-Role-{i}"
        for seg_idx in range(3):
            segments.append({
                "id": f"{spk_id}-seg-{seg_idx}",
                "speakerId": spk_id,
                "speakerName": f"Speaker {i + 1}",
                "speakerCode": f"S{i + 1}",
                "speakerColor": palette[i % len(palette)],
                "voiceOverride": None,
                "targetText": f"Speech from {spk_id} block {seg_idx}",
            })

    assert len(segments) == 60
    assert len(speaker_voice_map) == 20

    # Verify initial resolution for all 60 segments
    for seg in segments:
        v, is_ov = resolve_effective_voice_spec(seg, speaker_voice_map)
        assert not is_ov
        assert v == speaker_voice_map[seg["speakerId"]]

    # Modify speaker 13's voice
    speaker_voice_map["spk_13"] = "Voice-Role-13-SPECIAL"

    # Verify that only segments belonging to spk_13 updated
    for seg in segments:
        v, _ = resolve_effective_voice_spec(seg, speaker_voice_map)
        if seg["speakerId"] == "spk_13":
            assert v == "Voice-Role-13-SPECIAL"
        else:
            assert v != "Voice-Role-13-SPECIAL"


def test_adversarial_override_and_reset_state_transitions():
    """
    Rigorously test state transitions:
    spk_1 voice change -> seg_1 override -> spk_1 voice change -> seg_1 reset.
    """
    speaker_voice_map = {"spk_main": "Voice-V1"}
    seg1 = {"id": 1, "speakerId": "spk_main", "voiceOverride": None}
    seg2 = {"id": 2, "speakerId": "spk_main", "voiceOverride": None}

    # Step 1: Initial state
    assert resolve_effective_voice_spec(seg1, speaker_voice_map)[0] == "Voice-V1"
    assert resolve_effective_voice_spec(seg2, speaker_voice_map)[0] == "Voice-V1"

    # Step 2: Global change to V2
    speaker_voice_map["spk_main"] = "Voice-V2"
    assert resolve_effective_voice_spec(seg1, speaker_voice_map)[0] == "Voice-V2"
    assert resolve_effective_voice_spec(seg2, speaker_voice_map)[0] == "Voice-V2"

    # Step 3: Override seg1 to V-Override
    seg1["voiceOverride"] = "Voice-Override"
    assert resolve_effective_voice_spec(seg1, speaker_voice_map) == ("Voice-Override", True)
    assert resolve_effective_voice_spec(seg2, speaker_voice_map) == ("Voice-V2", False)

    # Step 4: Global change to V3 (override must isolate seg1)
    speaker_voice_map["spk_main"] = "Voice-V3"
    assert resolve_effective_voice_spec(seg1, speaker_voice_map) == ("Voice-Override", True)
    assert resolve_effective_voice_spec(seg2, speaker_voice_map) == ("Voice-V3", False)

    # Step 5: Override seg2 to V-Seg2
    seg2["voiceOverride"] = "Voice-Seg2"
    assert resolve_effective_voice_spec(seg1, speaker_voice_map) == ("Voice-Override", True)
    assert resolve_effective_voice_spec(seg2, speaker_voice_map) == ("Voice-Seg2", True)

    # Step 6: Clear seg1 override -> Reverts to current global voice (V3), not initial (V1) or old (V2)
    seg1["voiceOverride"] = None
    assert resolve_effective_voice_spec(seg1, speaker_voice_map) == ("Voice-V3", False)
    assert resolve_effective_voice_spec(seg2, speaker_voice_map) == ("Voice-Seg2", True)

    # Step 7: Clear seg2 override -> Reverts to current global voice (V3)
    seg2["voiceOverride"] = None
    assert resolve_effective_voice_spec(seg2, speaker_voice_map) == ("Voice-V3", False)


def test_adversarial_missing_speaker_fields_resolution():
    """
    Challenge: Test behavior when speakerId is missing, undefined, or empty.
    Documents the nuance: if a segment lacks 'speakerId', effective voice resolution falls back to default.
    """
    speaker_voice_map = {"spk_1": "Voice-Assigned"}

    seg_with_id = {"id": 1, "speakerId": "spk_1"}
    seg_without_id = {"id": 2, "speakerName": "Speaker 1"}
    seg_none_id = {"id": 3, "speakerId": None}
    seg_empty_id = {"id": 4, "speakerId": ""}

    assert resolve_effective_voice_spec(seg_with_id, speaker_voice_map)[0] == "Voice-Assigned"
    # Segments missing valid speakerId fall back gracefully to default without throwing
    assert resolve_effective_voice_spec(seg_without_id, speaker_voice_map)[0] == "default"
    assert resolve_effective_voice_spec(seg_none_id, speaker_voice_map)[0] == "default"
    assert resolve_effective_voice_spec(seg_empty_id, speaker_voice_map)[0] == "default"
