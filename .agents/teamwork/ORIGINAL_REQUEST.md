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
