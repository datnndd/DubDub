# Handoff Report: Stage 3 Backend & TTS Exploration

## 1. Observation
1. `webui.py:681-689` implements the voice listing handler:
   ```python
   async def voices_handler(request: web.Request) -> web.Response:
       tts_type = _optional_index(request.query.get("ttsType"), len(tts.TTS_NAME_LIST))
       language = request.query.get("language", "")
       try:
           voices = role_menu(tts_type, langcode=language) or ["No"]
       except Exception:
           voices = ["No"]
       return web.json_response({"voices": voices})
   ```
   Route registration is at `webui.py:1064`: `app.router.add_get("/api/voices", voices_handler)`.
2. `webui.py:579` exposes the TTS provider catalog in `options_handler`:
   ```python
   "voices": list(enumerate(tts.TTS_NAME_LIST)),
   ```
   yielding `[[0, "ElevenLabs"], [1, "OmniVoice(Built-in)"], [2, "VieNeu-TTS"], [3, "Gemini TTS"]]`.
3. `videotrans/tts/__init__.py:8-30` defines the contiguous supported TTS providers:
   ```python
   ELEVENLABS_TTS = 0
   OMNIVOICE_TTS = 1
   VIENEU_TTS = 2
   GEMINI_TTS = 3
   DEFAULT_TTS = VIENEU_TTS
   ```
   `tests/test_provider_catalog.py:56-72` asserts that removed providers (including Edge TTS `_edgetts.py`, OpenAI TTS `_openaitts.py`, Chatterbox, etc.) do NOT exist in the codebase.
4. Voice resolution executed via `videotrans/util/help_role.py:134-145`:
   - `tts.ELEVENLABS_TTS` (0) -> `get_elevenlabs_role()` reading `videotrans/voicejson/elevenlabs.json` (21 cached voices).
   - `tts.OMNIVOICE_TTS` (1) -> `get_f5tts_role().keys()` reading `params["f5tts_role"]`.
   - `tts.VIENEU_TTS` (2) -> `get_vieneu_role()` reading `get_vieneu_preset_roles()` and `params["vieneu_roles"]`.
   - `tts.GEMINI_TTS` (3) -> `contants.GEMINITTS_ROLES.split(",")` (30 preset names).
   Tool test output:
   - ElevenLabs: `['No', 'Roger - Laid-Back Casual Resonant', 'Sarah - Mature Reassuring Confident', ...]`
   - OmniVoice: `['No', 'clone', 'zh_male_bj.wav', 'nverguo.wav', 'cosy.wav']`
   - VieNeu-TTS: `['No', 'clone', 'Minh Đức', 'Phạm Tuyên', 'Thái Sơn', ...]`
   - Gemini TTS: `['Zephyr', 'Puck', 'Charon', 'Kore', 'Fenrir', ...]`
5. `videotrans/task/_stage_dubbing.py:54-60` shows how the backend supports multi-speaker dubbing:
   ```python
   line_roles = app_cfg.line_roles
   voice_role = self.cfg.voice_role
   ...
   voice = line_roles.get(f'{it["line"]}', voice_role) if line_roles else voice_role
   ```
6. `frontend/js/state.js:513-526` contains `loadVoices()`:
   ```javascript
   const query = new URLSearchParams({ ttsType: config.ttsType, language: this.state.languages.target.code });
   const response = await fetch(`/api/voices?${query}`);
   ```
   Currently, `state.speakerVoiceMap` and per-segment voice override methods do not exist in `frontend/js/state.js`.

## 2. Logic Chain
1. Requirement R1 asks for dynamic voice fetching via `/api/voices` when selecting any supported TTS provider (ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS).
2. Observation 1 confirms `/api/voices` is already implemented and registered in `webui.py`, but Observation 1 & 4 show it strictly expects integer `ttsType` (`0..3`) and `language`.
3. Observation 3 confirms Edge TTS is intentionally absent from Provider Catalog v3; only ElevenLabs, OmniVoice, VieNeu-TTS, and Gemini TTS are supported.
4. Observation 5 demonstrates that backend dubbing is ready for multi-speaker mapping via `line_roles`, which maps segment line numbers to voice roles.
5. Observation 6 confirms that frontend state currently lacks the speaker-to-voice matrix (`state.speakerVoiceMap`) and segment override helpers required by R2 and R3.
6. Therefore, completing Stage 3 requires:
   - Enhancing `/api/voices` to accept alias query parameters (`provider`, `target_language`).
   - Implementing `state.speakerVoiceMap`, speaker discovery, and override methods in `frontend/js/state.js`.
   - Wiring the console and teleprompter feed in `frontend/js/screens/Stage3VoiceDubbing.js`.

## 3. Caveats
- Edge TTS was queried in prompt item 2, but has been permanently excised in this repository version. Only the four contiguous providers (ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS) are retained.
- For ElevenLabs and Gemini TTS, third-party API calls require valid API keys in `params.json` (`elevenlabstts_key`, `gemini_key`); however, `/api/voices` succeeds even offline because ElevenLabs falls back to cached `elevenlabs.json` and Gemini TTS uses hardcoded constellation roles.
- VieNeu-TTS language constraint: `tts.is_allow_lang(langcode, tts.VIENEU_TTS)` warns if `langcode` is not Vietnamese or English.

## 4. Conclusion
The backend TTS infrastructure and `/api/voices` endpoint are functional and well-aligned with DubDub Stage 3 requirements. Key tasks for the implementation team are:
1. Make `/api/voices` resilient to `provider` string IDs and `target_language` parameter aliases.
2. Implement `state.speakerVoiceMap`, distinct speaker extraction, and per-block voice override methods in `frontend/js/state.js`.
3. Update `frontend/js/screens/Stage3VoiceDubbing.js` to render the dynamic Voice Casting Console and teleprompter feed with per-block voice selectors and "Reset to Default" buttons.
4. Add automated tests covering the voice endpoint and frontend state behavior in `tests/test_stage3_voice_dubbing.py`.

## 5. Verification Method
1. Run existing test suite to verify no regressions:
   ```bash
   uv run pytest tests/test_webui.py tests/test_staged_asr_and_transcript.py
   ```
2. Verify `/api/voices` endpoint directly via Python:
   ```bash
   uv run python -c "from videotrans import tts; from videotrans.util.help_role import role_menu; [print(i, tts.TTS_NAME_LIST[i], role_menu(i, 'vi')[:3]) for i in range(4)]"
   ```
3. Inspect `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be\report.md` for full implementation details.
