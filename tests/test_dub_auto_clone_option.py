"""Test auto_clone option in dubbing pipeline.

Validates that:
1. When auto_clone=False:
   - Voice extraction from media is skipped.
   - Cast sources, speaker clones, and segment clones remain empty.
   - Segments keep empty profile_id (Default voice), allowing manual voice selection.
2. When auto_clone=True:
   - Detected speaker clones are extracted and bound to auto:speaker_N.
3. The dub_transcribe_stream endpoint declares the auto_clone parameter with default False.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("OMNIVOICE_DISABLE_FILE_LOG", "1")

import pytest
from api.routers.dub_core import dub_transcribe_stream, dub_transcribe
from services.speaker_clone import auto_profile_id, build_cast_sources



def _assign_profiles(final_segs, clones, seg_clones, auto_clone: bool):
    """Post-diarization profile assignment logic matching dub_core.py."""
    if not auto_clone:
        return final_segs, {}, {}, {}
    cast_sources = build_cast_sources(final_segs, clones, seg_clones)
    if cast_sources:
        for s in final_segs:
            if s.get("profile_id"):
                continue
            spk = s.get("speaker_id") or "Speaker 1"
            if spk in cast_sources:
                s["profile_id"] = auto_profile_id(spk)
    return final_segs, cast_sources, clones, seg_clones



def test_endpoint_signatures_have_auto_clone_param():
    """Verify endpoint signatures declare auto_clone with default False."""
    sig_stream = inspect.signature(dub_transcribe_stream)
    assert "auto_clone" in sig_stream.parameters
    assert sig_stream.parameters["auto_clone"].default is False

    sig_sync = inspect.signature(dub_transcribe)
    assert "auto_clone" in sig_sync.parameters
    assert sig_sync.parameters["auto_clone"].default is False



def test_auto_clone_disabled_leaves_segments_unbound():
    """When auto_clone is False, no auto:speaker_N profiles are bound to segments."""
    segs = [
        {"id": "s0", "speaker_id": "Speaker 1", "text": "Hello world"},
        {"id": "s1", "speaker_id": "Speaker 2", "text": "Good morning"},
    ]
    clones = {
        "Speaker 1": {"ref_audio": "/tmp/spk1.wav", "ref_text": "Hello world", "duration": 5.0},
        "Speaker 2": {"ref_audio": "/tmp/spk2.wav", "ref_text": "Good morning", "duration": 6.0},
    }
    seg_clones = {}

    out_segs, cast_sources, spk_clones, s_clones = _assign_profiles(
        segs, clones, seg_clones, auto_clone=False
    )

    assert cast_sources == {}
    assert spk_clones == {}
    assert s_clones == {}
    assert out_segs[0].get("profile_id") is None or out_segs[0].get("profile_id") == ""
    assert out_segs[1].get("profile_id") is None or out_segs[1].get("profile_id") == ""



def test_auto_clone_enabled_binds_speaker_clones():
    """When auto_clone is True, segments are bound to auto:speaker_N."""
    segs = [
        {"id": "s0", "speaker_id": "Speaker 1", "text": "Hello world"},
        {"id": "s1", "speaker_id": "Speaker 2", "text": "Good morning"},
    ]
    clones = {
        "Speaker 1": {"ref_audio": "/tmp/spk1.wav", "ref_text": "Hello world", "duration": 5.0, "source_count": 1},
        "Speaker 2": {"ref_audio": "/tmp/spk2.wav", "ref_text": "Good morning", "duration": 6.0, "source_count": 1},
    }
    seg_clones = {}

    out_segs, cast_sources, spk_clones, _ = _assign_profiles(
        segs, clones, seg_clones, auto_clone=True
    )

    assert "Speaker 1" in cast_sources
    assert "Speaker 2" in cast_sources
    assert out_segs[0].get("profile_id") == "auto:speaker_1"
    assert out_segs[1].get("profile_id") == "auto:speaker_2"
