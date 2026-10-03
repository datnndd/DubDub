# Execution Plan: Voice Generation, Truncation, Speed Matching, and Synchronization

Date: 2026-10-02

## Status

Completed

## Outcome

Fix sentence cutoff, unnatural zero-gap transitions, and speaking speed mismatch during dubbed voice generation and assembly across the backend audio stitching pipelines and frontend playback.

The system will:
1. Never prematurely cut off the end of a voice segment mid-sentence.
2. In dubbing assembly, utilize inter-segment silence slack (`available_dur = max_allowed_end_ms - start_ms`, where `max_allowed_end_ms = max(start_ms + 1, next_start_ms - 30)`) instead of blindly truncating audio clips at `end_ms - start_ms`.
3. Eliminate hard `-t` clipping in audio stretching (`audio_fit.py` and `_rate.py`) to prevent filter buffer truncation.
4. Enforce a minimum 150 ms natural breathing pause between adjacent voice segments when gaps permit, with a 30 ms collision guard.
5. Apply smooth 20 ms fade-in and 20 ms fade-out on placed clips to eliminate DC click and pop artifacts.
6. Cap speech acceleration at a natural 1.35x maximum rate instead of 100x chipmunk distortion.
7. Allow frontend preview playback in `VideoPlayer.tsx` to play speech extending into the inter-segment gap instead of muting at `item.endSec`.
8. Prevent premature silence trimming of soft trailing syllables in `_ffmpeg_audio.py`.

## Context

- `videotrans/api/routes/projects.py`: Dubbing assembly route (`assemble_project_dubbing_handler`).
- `videotrans/services/audio_fit.py`: Web Studio audio speed adjustment service.
- `videotrans/task/_rate.py`: Core Engine `SpeedRate` and `TtsSpeedRate` classes.
- `videotrans/util/_ffmpeg_audio.py`: Audio silence trimming utilities.
- `frontend/src/components/VideoPlayer.tsx`: Stage 3 video & dubbed audio preview player.
- `frontend/src/screens/Stage3VoiceDubbing.tsx`: Stage 3 voice dubbing UI and preview generation.
- `frontend/src/store/dubbingSlice.ts`: Dubbing preview generation and segment state.

## Scope

In scope:
- Backend:
  - Slack-aware dubbing assembly with crossfade smoothing in `projects.py`.
  - Non-truncating time-stretching with a natural 1.35x rate cap in `audio_fit.py`.
  - Atempo buffer drain and 150 ms minimum gap preservation in `_rate.py`.
  - Dynamic silence trimming threshold in `_ffmpeg_audio.py`.
  - Default rate alignment in `voices.py`, `voice_preview.py`, and `stage_reset.py`.
- Frontend:
  - VideoPlayer playback window extension with safe next-segment collision clamping in `VideoPlayer.tsx`.
  - Gap guard expansion to 150 ms in `Stage3VoiceDubbing.tsx` and `dubbingSlice.ts`.
- Tests:
  - Pytest unit and regression tests for assembly, audio fit, and rate limits.
  - Bun unit tests for frontend preview playback, gap guard, and store defaults.

Out of scope:
- Redesigning external TTS third-party neural voice models.
- Automatic full-video re-timing PTS alteration when video auto-rate is turned off.

## Progress

- [x] Backend: Update `assemble_project_dubbing_handler` with slack-aware bounding and fades.
- [x] Backend: Update `audio_fit.py` and `_rate.py` to remove `-t` and clamp speed to 1.35x.
- [x] Backend: Enforce 150 ms inter-segment gap in `_rate.py` and calibrate silence removal in `_ffmpeg_audio.py`.
- [x] Frontend: Update `VideoPlayer.tsx` preview window and 150 ms gap guard in Stage 3.
- [x] Tests: Add and verify backend pytest tests and frontend bun tests.

## Decisions

- 2026-10-02: Use multi-tier strategy (gap absorption up to 150 ms boundary -> gentle atempo up to 1.35x max -> soft fade-out only if overlapping next dialogue). Never hard-truncate with `-t`.
- 2026-10-02: For adjacent segments with tight/zero gap (<150 ms), enforce a 30 ms collision guard with soft crossfade so both speakers remain clear without overlapping.

## Validation

- Backend: `pytest tests/test_dubbing_assembly.py tests/test_audio_fit.py tests/test_speed_rate.py tests/test_voice_sync_and_truncation.py tests/test_stage_reset.py tests/test_stage3_voice_dubbing.py` (59 passed in 5.23s).
- Frontend: `bun test` (159 passed across 10 test suites in 598ms).
- Build: `bun run build` (`tsc && vite build`) passed in 3.82s.

## Result

Successfully resolved all voice truncation, abrupt transitions, and speed mismatch defects:
1. End-of-sentence speech is no longer truncated: dubbing assembly absorbs inter-segment gap slack, and `-t` has been removed from audio stretch commands.
2. Abrupt transitions are eliminated: adjacent segments preserve at least a 150 ms natural breathing pause (or 30 ms collision guard on tight intervals), and all clips are smoothed with edge fades.
3. Speed is naturally bounded: maximum speed rate is capped at 1.35x across all services, schemas, and core engine classes.
4. Stage 3 preview playback now seamlessly plays audio extending into the inter-segment gap without cutting off at `item.endSec`.
