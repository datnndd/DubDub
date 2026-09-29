# Original User Request

## 2026-09-27T13:59:00Z

This is a single self-contained feature; keep it small and focused. Allow users to preview and listen to any voice (both preset and custom cloned voices) before assigning it to each speaker in Stage 3 Voice Dubbing.

Working directory: c:\Users\ddat2\Downloads\Projects\pyvideotrans
Integrity mode: development

## Requirements

### R1. Candidate Voice Audition in VoiceSelector Dropdown
- Inside the `VoiceSelector` dropdown popover, provide an inline audition (Play/Pause) button next to every candidate voice (both Preset Voices and Custom Cloned Voices).
- Clicking the audition button must preview the voice without selecting it or closing the dropdown menu.
- Clicking elsewhere on the voice item row continues to select the voice and assign it as expected.

### R2. Direct Voice Audition on Speaker Cards
- On each speaker card in the Upper Voice Casting Console (`Stage3VoiceDubbing.tsx`), add a dedicated preview/audition button adjacent to the speaker's voice selector.
- Clicking this button immediately plays an audio sample of the currently assigned voice for that speaker, displaying a loading spinner while generating and a pause icon while playing.

### R3. Standard Sample Phrase & Audio Caching
- Voice previews in the selector dropdown and on speaker cards synthesize using a standard sample phrase in the project's target language (e.g. Vietnamese: "Chào bạn, đây là bản nghe thử giọng nói trí tuệ nhân tạo được tổng hợp thành công.", English: "Hello, this is a sample preview of this voice."), delegating to the backend `/api/tts/preview` endpoint when no static sample URL is present.
- Cache generated preview audio URLs in client state (keyed by `provider + voice + language`) so repeated auditions are instant without redundant backend calls.

### R4. Coordinated Audio Playback
- Maintain a single active audio player instance across all voice preview buttons (VoiceSelector dropdown, Speaker Cards, and Segment Dialogue Blocks). Clicking play on any voice immediately stops any currently playing audio stream.

## Acceptance Criteria

### Dropdown Audition
- [ ] Every preset voice row in `VoiceSelector` renders a Play button with tooltip "Audition Voice".
- [ ] Clicking the Play button on a preset voice triggers preview generation via `/api/tts/preview` and displays an inline spinner while loading.
- [ ] Clicking the Play button does not close the dropdown or change the currently selected voice.
- [ ] While playing, the button transitions to a Pause icon and clicking it halts playback.

### Speaker Card Audition
- [ ] Each speaker card in the Upper Voice Casting Console renders a preview/audition button beside the voice dropdown.
- [ ] Clicking the button plays the currently assigned voice for that speaker using the active provider and target language.
- [ ] Changing the speaker's voice dropdown updates the audition button to play the newly selected voice.

### Playback & Caching
- [ ] Starting playback on any voice stops any currently playing audio across the interface.
- [ ] Generated audio preview URLs are cached in client memory; subsequent auditions of the same voice play instantly from cache.
- [ ] Unmounting the component or closing dropdown cleanly pauses and releases active audio objects.

### Verification
- [ ] `bun test` passes with full test coverage for preset audition buttons, speaker card audition buttons, and audio coordination.
- [ ] `bun run build` generates a production bundle with 0 TypeScript/build errors.
- [ ] `uv run pytest tests/test_stage3_voice_dubbing.py` passes cleanly.

## 2026-09-29T06:12:14Z

Implement in-editor subtitle customization with embedded video rendering, a 4-asset CapCut export bundle modal, and a "Continue in CapCut" status button with tooltip instructions in DubDub AI Video Dubbing Studio.

Working directory: C:\Users\ddat2\Downloads\Projects\pyvideotrans
Integrity mode: development

## Requirements

### R1. Subtitle Customization in Stage 4 (Edit Video)
- Add controls to the "Subtitles" tab in `frontend/src/screens/Stage4EditVideo.tsx`:
  - **Font Size**: Range slider and numeric readout (12px to 64px).
  - **Font Style**: Font Family dropdown (Arial, Inter, Impact, Georgia, Roboto, System default) and Style toggles (Bold, Italic).
  - **Opacity / Transparency**: Range slider (0% to 100%) adjusting the text alpha channel.
- Update `frontend/src/store/editVideoSlice.ts` (`subtitleStyles`) to hold `fontFamily`, `fontSize`, `fontWeight`, `fontStyle`, and `opacity`.
- Ensure `frontend/src/components/VideoPlayer.tsx` live canvas preview immediately updates in real-time when any subtitle style changes.

### R2. Complete Video Generation with Embedded Subtitles (Burn-in)
- In `frontend/src/store/editVideoSlice.ts:buildRenderRequest` and `videotrans/api/task_params.py`, pass the subtitle style parameters (`fontFamily`, `fontSize`, `fontWeight`, `fontStyle`, `opacity`, `color`, `outlineColor`, `outlineWidth`, `shadowSize`).
- In `videotrans/util/_srt_ass.py` and `videotrans/task/_stage_subtitle.py`, map `fontWeight` to ASS `Bold` (-1/0), `fontStyle` to ASS `Italic` (-1/0), and `opacity` to ASS PrimaryColour alpha hex channel (`&HAABBGGRR&`).
- Ensure running the render job produces a final output video with burned-in subtitles accurately reflecting the customized typography.

### R3. 4-Asset CapCut Export Package
- Provide an export mechanism delivering all 4 required files:
  1. `subtitles_edited.srt`: The user-edited target-language subtitles.
  2. `subtitles_target.srt`: The initial raw machine-translated subtitles.
  3. `video.mp4`: The clean/dubbed video file.
  4. `voiceover_merged.wav`: The unified audio track containing all merged voice segments.
- Allow downloading all 4 assets bundled in a single `.zip` archive as well as individual file downloads.

### R4. "Continue in CapCut" Button & Workflow Modal
- In `frontend/src/components/StatusFooter.tsx` (active during Stage 4), add a dedicated "Continue in CapCut" button adjacent to the "Render dubbed video" button.
- Add a hover tooltip with a clear, concise guide:
  *"Export your video, merged audio, and .srt subtitles, then import them directly into CapCut for advanced effects and transitions."*
- Clicking the button opens the **CapCut Export Modal**:
  - Displays download links/buttons for each of the 4 individual files and a "Download All as ZIP" button.
  - Step-by-step instructions on importing into CapCut (importing video/audio tracks and adding the `.srt` file into CapCut's captions).
  - Workflow launcher buttons: "Open Folder in Explorer" (to easily drag & drop into CapCut) and "Launch CapCut" (triggering `capcut://` protocol with fallback to CapCut Web `https://www.capcut.com/editor`).

## Acceptance Criteria

### Subtitle Customization
- [ ] Font size, font family (Arial, Inter, Impact, etc.), font weight (Bold/Normal), italic toggle, and opacity slider (0-100%) are visible and functional in the Subtitles tab of Stage 4.
- [ ] Subtitle changes immediately update both the live preview canvas in `VideoPlayer.tsx` and the exported render parameters in `buildRenderRequest`.

### Video Render with Embedded Subtitles
- [ ] Generating the video burns the styled subtitles into the video stream via ASS subtitle generation with proper font, weight, and alpha transparency.

### Asset Export & Modal
- [ ] Clicking "Continue in CapCut" displays the CapCut Export Modal with all 4 assets (`subtitles_edited.srt`, `subtitles_target.srt`, video file, merged voice audio) and a "Download All as ZIP" action.
- [ ] "Open Folder in Explorer" and "Launch CapCut" buttons are present in the modal with working fallback.
- [ ] Hovering over the "Continue in CapCut" button displays the step-by-step guidance tooltip.

### Automated Testing & Quality
- [ ] Frontend unit tests in `frontend/tests/` verify subtitle style updates, CapCut button presence, tooltip display, and export modal interactions.
- [ ] Backend tests in `tests/test_stage4_edit_video.py` verify that `_srt_ass.py` correctly parses style overrides including font weight, italic, and opacity.
- [ ] All existing and new tests pass without regressions.

