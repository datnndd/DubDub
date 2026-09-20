# Completed Plan: Stage 4 CapCut-Style Lightweight Video Editing Studio

## Outcome
Redesigned **Stage 4: Edit Video** in DubDub AI Video Dubbing Studio as a lightweight video editing studio inspired by CapCut. Users can review the final dubbed video, adjust independent audio sources (original audio, dubbed TTS, background music), manage video thumbnails, fine-tune subtitle styling (font size, outline, shadow), and interact with a multi-track timeline before exporting.

## Implemented
1. **Layout & Studio Architecture**:
   - **Upper Deck**:
     - Video Preview Canvas (left) with transport controls and clean CapCut-style subtitle overlay centered near bottom.
     - Contextual Inspector / Settings Panel (right) with tabs for **Audio Mix**, **Subtitles**, and **Thumbnail**.
   - **Lower Deck**:
     - Multi-track timeline editing studio with time ruler, playhead timecode, and interactive playhead needle (`data-timeline-playhead`).
     - Tracks: Video track (16:9 clip), Subtitles track (interactive cue blocks with proportional positioning and seek-to-segment), Dubbed TTS track (speech cue blocks), and Background Music track (BGM clip or add BGM button).
2. **Audio Source Separation & Synchronization**:
   - Clearly separated audio sources: Original Video Audio, Dubbed TTS Audio, and Background Music.
   - Independent volume sliders (0–150%) and mute/unmute toggles (`toggleAudioMute`).
   - Client-side background music playback synchronized with video element play, pause, seek, and volume (`syncPreviewPlayback`).
   - Background music file upload, replace, and removal (`removeBackgroundAudio`).
3. **Video Thumbnail Management**:
   - Thumbnail upload (`#stage4-thumbnail-input`), instant preview card, and removal option (`removeThumbnail`).
4. **Clean Readable Subtitles & Font Size Adjustment**:
   - Display translated subtitles directly on video preview.
   - Default style contract: White text (`#FFFFFF`), black outline (`#000000`, 2px), subtle shadow (`rgba(0,0,0,0.75)`), centered near bottom.
   - Dynamic font size slider & number readout (14px–48px) with immediate canvas re-styling.
   - Active subtitle cue editor with start/end time adjusters and inline editable `targetText`.
5. **VideoPlayer Component**:
   - Supported `subtitleVariant === 'capcut'` unboxed clean subtitle rendering for true final video preview.

## Verification
- `uv run pytest tests/test_stage4_edit_video.py -v`: 9/9 passed in 0.93s.
- `node -c frontend/js/state.js frontend/js/screens/Stage4EditVideo.js frontend/js/components/VideoPlayer.js`: 0 syntax errors.
- Full regression suite (`uv run pytest tests/test_stage4_edit_video.py tests/test_stage3_voice_dubbing.py tests/test_stage3_adversarial_stress.py tests/test_stage3_api_and_subtitle_sync_stress.py tests/test_staged_asr_and_transcript.py tests/test_webui.py -v`): 98 passed, 0 failed.
