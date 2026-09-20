# Stage 3 Voice & Dubbing Architecture Survey: Backend & TTS Exploration Report

**Date**: 2026-09-19  
**Explorer**: Backend & TTS Explorer  
**Task ID**: DubDub Stage 3: Voice & Dubbing (Requirements R1–R4)  
**Target File**: `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be\report.md`  
**Project Root**: `c:\Users\ddat2\Downloads\Projects\pyvideotrans`

---

## 1. Executive Summary

This report delivers a thorough investigation into the backend APIs, TTS provider registry, voice discovery mechanisms, and frontend state synchronization for DubDub AI Video Dubbing Studio's **Stage 3: Voice & Dubbing**.

### Key Findings
1. **Existing Voice Endpoint**: The WebUI server has an existing `/api/voices` endpoint implemented in `webui.py` (lines 681–689) mapped to `GET /api/voices` (line 1064).
2. **Provider Catalog v3**: As part of repository cleanup (Catalog Version 3, `videotrans/configure/_app_params.py` and `tests/test_provider_catalog.py`), the codebase retains **exactly four contiguous TTS providers** (indices 0..3):
   - `0`: **ElevenLabs** (`ELEVENLABS_TTS`)
   - `1`: **OmniVoice(Built-in)** (`OMNIVOICE_TTS`)
   - `2`: **VieNeu-TTS** (`VIENEU_TTS`, the system default)
   - `3`: **Gemini TTS** (`GEMINI_TTS`)
   *Note on Edge TTS*: Edge TTS was explicitly removed from the repository (`tests/test_provider_catalog.py:66`). Stage 3 requirements R1–R4 explicitly mandate the four retained providers (ElevenLabs, OmniVoice, VieNeu-TTS, Gemini TTS).
3. **Voice Discovery Dispatcher**: `videotrans/util/help_role.py:role_menu(tts_type, langcode)` dynamically resolves available voices for each provider via cached JSON (`elevenlabs.json`), preset resource inspection (`voices_v3_turbo.json`), user config (`params["vieneu_roles"]`, `params["f5tts_role"]`), or constants (`GEMINITTS_ROLES`).
4. **Endpoint Signature & Query Inflexibility**: The current `voices_handler` only parses `ttsType` as an integer index (0..3) and `language`. If caller passes string names (e.g. `provider=elevenlabs`) or `target_language`, it silently falls back to ElevenLabs. Enhancing `/api/voices` with parameter aliasing (`provider` name or index, `target_language` / `targetLanguage` alias) is strongly recommended.
5. **Backend Multi-Speaker Dubbing Support**: The dubbing engine (`videotrans/task/_stage_dubbing.py:54-60`) already supports per-line voice overrides using `line_roles: dict[str, str]` (mapping line numbers to voice roles) alongside a global `voice_role`.
6. **Frontend State Gap**: `frontend/js/state.js` currently stores `backend.config.ttsType`, `backend.config.voiceRole`, and `backend.options.voiceRoles`, but lacks `state.speakerVoiceMap` and methods for distinct speaker detection, global speaker-to-voice propagation, and individual block overrides.

---

## 2. WebUI Architecture & Endpoints

### 2.1 Server Framework
The WebUI is an `aiohttp.web` application created by `create_app()` in `webui.py` (root level). The entry point runs on `http://127.0.0.1:7860`.

### 2.2 Voice-Related Endpoints in `webui.py`

#### A. Voice Listing Endpoint: `GET /api/voices`
- **File**: `c:\Users\ddat2\Downloads\Projects\pyvideotrans\webui.py`
- **Definition** (lines 681–689):
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
- **Registration** (line 1064):
  ```python
  app.router.add_get("/api/voices", voices_handler)
  ```
- **Query Parameters (Current)**:
  - `ttsType`: Integer index into `tts.TTS_NAME_LIST` (`0`, `1`, `2`, or `3`). Default is `0` (`ElevenLabs`).
  - `language`: Target language code (e.g. `"vi"`, `"en"`, `"zh-cn"`).
- **Returned Schema**:
  ```json
  {
    "voices": [
      "No",
      "clone",
      "Minh Đức",
      "Phạm Tuyên",
      ...
    ]
  }
  ```

#### B. Initial Options Endpoint: `GET /api/options`
- **File**: `webui.py` (lines 553–590)
- **Registration** (line 1063):
  ```python
  app.router.add_get("/api/options", options_handler)
  ```
- **Relevant Payload Segment**:
  ```python
  "voices": list(enumerate(tts.TTS_NAME_LIST)),
  "defaults": {
      "sourceLanguage": "zh-cn",
      "targetLanguage": "vi",
      ...
      "ttsType": tts.DEFAULT_TTS, # 2 (VieNeu-TTS)
  }
  ```
  `list(enumerate(tts.TTS_NAME_LIST))` yields:
  ```json
  [
    [0, "ElevenLabs"],
    [1, "OmniVoice(Built-in)"],
    [2, "VieNeu-TTS"],
    [3, "Gemini TTS"]
  ]
  ```

#### C. Task Parameter Mapping: `build_task_params()`
- **File**: `webui.py` (lines 475–550)
- **TTS Fields Handled**:
  - `options.get("ttsType", tts.DEFAULT_TTS)` -> validated against `len(tts.TTS_NAME_LIST)`
  - `options.get("voiceRole")` -> validated or falls back to first non-`"No"` voice in `role_menu(tts_type, langcode=target_language)`
  - `options.get("voiceRate")` -> mapped to `params["voice_rate"]` (e.g. `"+0%"`)
  - `timing_flags` -> mapped to `voice_autorate`, `video_autorate`, `align_sub_audio`

---

## 3. TTS Provider Catalog Deep-Dive

The repository uses **Provider Catalog Version 3** (`videotrans/configure/_app_params.py:20`). Legacy providers (Edge TTS, OpenAI TTS, ChatTTS, Chatterbox, CosyVoice, etc.) have been removed (`test_removed_provider_implementations_are_absent` in `tests/test_provider_catalog.py`).

The supported TTS registry is defined in `videotrans/tts/__init__.py`:

```python
ELEVENLABS_TTS = 0
OMNIVOICE_TTS = 1
VIENEU_TTS = 2
GEMINI_TTS = 3
DEFAULT_TTS = VIENEU_TTS

_ID_NAME_DICT = {
    ELEVENLABS_TTS: ChannelProvider(
        "ElevenLabs", "._elevenlabs", key_name="elevenlabstts_key", win="elevenlabs"
    ),
    OMNIVOICE_TTS: ChannelProvider(
        f"OmniVoice({tr('Built-in')})", "._omnivoice"
    ),
    VIENEU_TTS: ChannelProvider("VieNeu-TTS", "._vieneutts"),
    GEMINI_TTS: ChannelProvider(
        "Gemini TTS", "._geminitts", key_name="gemini_key", win="gemini"
    ),
}
TTS_NAME_LIST = [provider.name for provider in _ID_NAME_DICT.values()]
```

### 3.1 Provider Details & Voice Resolution

| Index | Constant | Provider Name | Implementation File | Credentials Key | Voice Resolution Function | Default Available Voices (Sample) |
|---|---|---|---|---|---|---|
| `0` | `ELEVENLABS_TTS` | `ElevenLabs` | `videotrans/tts/_elevenlabs.py` | `elevenlabstts_key` | `help_role.get_elevenlabs_role()` | `["No", "Roger - Laid-Back Casual Resonant", "Sarah - Mature Reassuring Confident", "Laura - Enthusiast Quirky Attitude", ...]` (21 cached voices) |
| `1` | `OMNIVOICE_TTS` | `OmniVoice(Built-in)` | `videotrans/tts/_omnivoice.py` | None (Local model `k2-fsa/OmniVoice`) | `help_role.get_f5tts_role()` | `["No", "clone", "zh_male_bj.wav", "nverguo.wav", "cosy.wav", ...]` |
| `2` | `VIENEU_TTS` | `VieNeu-TTS` (Default) | `videotrans/tts/_vieneutts.py` | None (Local `vieneu.Vieneu`) | `help_role.get_vieneu_role()` | `["No", "clone", "Minh Đức", "Phạm Tuyên", "Thái Sơn", "Thu Trang", "Tố Quyên", ...]` |
| `3` | `GEMINI_TTS` | `Gemini TTS` | `videotrans/tts/_geminitts.py` | `gemini_key` | `contants.GEMINITTS_ROLES.split(",")` | `["Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", ...]` (30 voices) |

### 3.2 Detailed Provider Behavior

#### 1. ElevenLabs (`0`)
- **Credentials**: `params["elevenlabstts_key"]`, model in `params["elevenlabstts_models"]` (e.g. `eleven_v3`, `eleven_flash_v2_5`, `eleven_multilingual_v2`).
- **Voice Discovery**:
  - Checks `{ROOT_DIR}/videotrans/voicejson/elevenlabs.json`.
  - If pre-cached, returns voice names immediately with `"No"` prefixed.
  - If `force=True` and API key is set, calls `elevenlabs.ElevenLabs(api_key=...).voices.get_all()` and updates the JSON file.
- **Multilingual Support**: Supports multilingual synthesis for all target languages.

#### 2. OmniVoice (`1`)
- **Local Neural Model**: Clones voices or uses reference audio files specified in `params["f5tts_role"]`.
- **Voice Discovery**:
  - Parses `params["f5tts_role"]` (newline separated `wav_name#ref_text`).
  - Returns `["No", "clone", *ref_wav_names]`.

#### 3. VieNeu-TTS (`2` - DEFAULT)
- **Local Engine**: Uses `vieneu.Vieneu(mode="v3turbo", device="cuda"|"cpu", backend="pytorch"|"onnx", max_batch_size=4)`.
- **Voice Discovery**:
  - Presets: Loaded from package resource `vieneu/assets/voices_v3_turbo.json` via `get_vieneu_preset_roles()`.
  - Custom Voices: Loaded from `params["vieneu_roles"]` (dict of `name -> audio_path`). Prefixed with `"Custom: "`.
  - Full List: `["No", "clone", *presets, *custom_roles]`.
- **Language Support Invariant**:
  - Enforced in `videotrans/tts/__init__.py:39`:
    ```python
    if tts_type == VIENEU_TTS and langcode[:2] not in ["vi", "en"]:
        return provider.name + tr("Dubbing channel") + " " + tr("may not support") + tr(langcode)
    ```
  - Only Vietnamese (`vi`) and English (`en`) are natively supported by VieNeu-TTS.

#### 4. Gemini TTS (`3`)
- **Credentials**: `params["gemini_key"]`, model in `params["gemini_ttsmodel"]` (e.g. `gemini-3.1-flash-tts-preview`, `gemini-2.5-flash-preview-tts`).
- **Voice Discovery**:
  - Static 30-voice constellation defined in `videotrans/configure/contants.py:80`:
    `Zephyr,Puck,Charon,Kore,Fenrir,Leda,Orus,Aoede,Callirrhoe,Autonoe,Enceladus,Iapetus,Umbriel,Algieba,Despina,Erinome,Algenib,Rasalgethi,Laomedeia,Achernar,Alnilam,Schedar,Gacrux,Pulcherrima,Achird,Zubenelgenubi,Vindemiatrix,Sadachbia,Sadaltager,Sulafat`
  - Returns these 30 voices as a list.

---

## 4. Analysis of Query Parameters & Schemas

### 4.1 Current `/api/voices` Query Handling
In `webui.py`:
```python
tts_type = _optional_index(request.query.get("ttsType"), len(tts.TTS_NAME_LIST))
language = request.query.get("language", "")
```
`_optional_index` implementation:
```python
def _optional_index(value: Any, size: int, default: int = 0) -> int:
    try:
        index = int(value)
    except (TypeError, ValueError):
        return default
    return index if 0 <= index < size else default
```

### 4.2 Limitations & Deficiencies
1. **String Provider ID Not Recognized**: If the frontend or a test passes `?provider=elevenlabs` or `?provider=vieneu`, `int("elevenlabs")` throws `ValueError`, and `_optional_index` silently falls back to `default=0` (ElevenLabs).
2. **Language Parameter Variations**: Query parameters like `target_language` or `targetLanguage` are ignored.
3. **No Provider Metadata Returned**: The response only contains `{"voices": [...]}` without echoing the resolved provider ID or language, making frontend debugging harder.

### 4.3 Recommended Endpoint Enhancement
Enhance `voices_handler` in `webui.py` to support aliases:
```python
TTS_ID_BY_NAME = {
    "elevenlabs": tts.ELEVENLABS_TTS,
    "omnivoice": tts.OMNIVOICE_TTS,
    "vieneu": tts.VIENEU_TTS,
    "vieneu-tts": tts.VIENEU_TTS,
    "gemini": tts.GEMINI_TTS,
    "gemini-tts": tts.GEMINI_TTS,
}

async def voices_handler(request: web.Request) -> web.Response:
    raw_provider = request.query.get("provider") or request.query.get("ttsType")
    if raw_provider is not None and str(raw_provider).lower() in TTS_ID_BY_NAME:
        tts_type = TTS_ID_BY_NAME[str(raw_provider).lower()]
    else:
        tts_type = _optional_index(raw_provider, len(tts.TTS_NAME_LIST), default=tts.DEFAULT_TTS)

    language = (
        request.query.get("language")
        or request.query.get("target_language")
        or request.query.get("targetLanguage")
        or ""
    )
    try:
        voices = role_menu(tts_type, langcode=language) or ["No"]
    except Exception:
        voices = ["No"]
    return web.json_response({
        "voices": voices,
        "ttsType": tts_type,
        "provider": tts.TTS_NAME_LIST[tts_type]
    })
```
*Note: Because the existing frontend reads `data.voices`, adding `"ttsType"` and `"provider"` to the returned JSON object is 100% backward compatible.*

---

## 5. Multi-Speaker Voice Assignment & Dubbing Flow in Backend

### 5.1 How the Dubbing Engine Consumes Voices
In `videotrans/task/_stage_dubbing.py` (lines 54–60):
```python
line_roles = app_cfg.line_roles
voice_role = self.cfg.voice_role
logger.debug(f'{line_roles=}')
for i, it in enumerate(subs):
    if it['end_time'] < it['start_time'] or not it['text'].strip():
        continue
    voice = line_roles.get(f'{it["line"]}', voice_role) if line_roles else voice_role
    ...
    tmp_dict = {
        "text": it['text'],
        "line": it['line'],
        "role": voice,
        "tts_type": self.cfg.tts_type,
        ...
    }
    queue_tts.append(tmp_dict)
```
- `self.cfg.voice_role`: Global default voice for dubbing.
- `app_cfg.line_roles`: A dictionary mapping segment/line number (as string `"1"`, `"2"`) to the specific voice role. If present, it overrides `voice_role` for that specific line.

This directly mirrors DubDub Stage 3 requirements:
- **Global Voice** = `state.backend.config.voiceRole`
- **Speaker Default** = `state.speakerVoiceMap[speakerName]`
- **Per-Block Override** = `seg.voiceOverride` -> becomes line override in `line_roles`.

---

## 6. Frontend Reactive Store & State Synchronization

### 6.1 Current Store Structure (`frontend/js/state.js`)
The reactive store is managed by `WorkflowStore`, accessible at `window.dubDubStore`.
- `state.backend.options.voices`: Contains `[[0, "ElevenLabs"], [1, "OmniVoice(Built-in)"], [2, "VieNeu-TTS"], [3, "Gemini TTS"]]`.
- `state.backend.options.voiceRoles`: Contains the current list of voice names (e.g. `["No", "clone", "Minh Đức", ...]`).
- `state.backend.config.ttsType`: Selected provider index (`2` default).
- `state.backend.config.voiceRole`: Selected default voice role.
- `state.languages.target.code`: Target language code (`"vi"` default).
- `state.segments`: Array of dialog block objects.

### 6.2 Current Voice Loading Method
In `frontend/js/state.js` (lines 513–526):
```javascript
async loadVoices() {
  const config = this.state.backend.config;
  try {
    const query = new URLSearchParams({ ttsType: config.ttsType, language: this.state.languages.target.code });
    const response = await fetch(`/api/voices?${query}`);
    if (!response.ok) return;
    const data = await response.json();
    this.state.backend.options.voiceRoles = data.voices;
    if (!data.voices.includes(config.voiceRole)) config.voiceRole = data.voices.find(v => v !== 'No') || 'No';
    this.notify();
  } catch (_) {
    // Voice discovery fallback
  }
}
```

### 6.3 Required Store Additions for Stage 3

1. **State Initialization**:
   Add `speakerVoiceMap: {}` to `this.state`:
   ```javascript
   this.state = {
     ...
     speakerVoiceMap: {}, // e.g. { "Alex Carter": "Minh Đức", "Elena Rostova": "Thu Trang" }
     ...
   };
   ```

2. **Distinct Speaker Detection Helper**:
   Extract all unique speakers from `state.segments`:
   ```javascript
   getDistinctSpeakers() {
     const speakers = new Set();
     for (const seg of this.state.segments) {
       const spk = seg.speakerName || seg.speakerId || seg.speakerLabel || "Speaker 1";
       if (spk) speakers.add(spk);
     }
     return Array.from(speakers);
   }
   ```

3. **Global Speaker-to-Voice Assignment**:
   ```javascript
   setSpeakerVoice(speakerName, voiceRole) {
     this.state.speakerVoiceMap[speakerName] = voiceRole;
     // Propagate to all segments of this speaker that do NOT have an explicit override
     for (const seg of this.state.segments) {
       const spk = seg.speakerName || seg.speakerId || seg.speakerLabel || "Speaker 1";
       if (spk === speakerName && !seg.voiceOverride) {
         seg.voiceRole = voiceRole;
       }
     }
     this.notify();
   }
   ```

4. **Per-Block Voice Override & Reset**:
   ```javascript
   setSegmentVoiceOverride(segmentId, voiceRole) {
     const seg = this.state.segments.find(s => String(s.id) === String(segmentId));
     if (seg) {
       seg.voiceOverride = voiceRole;
       this.notify();
     }
   }

   resetSegmentVoiceOverride(segmentId) {
     const seg = this.state.segments.find(s => String(s.id) === String(segmentId));
     if (seg) {
       delete seg.voiceOverride;
       const spk = seg.speakerName || seg.speakerId || seg.speakerLabel || "Speaker 1";
       const defaultVoice = this.state.speakerVoiceMap[spk] || this.state.backend.config.voiceRole || "No";
       seg.voiceRole = defaultVoice;
       this.notify();
     }
   }
   ```

5. **Segment Text Inline Editing**:
   `updateSegment(id, 'targetText', value)` must update `seg.targetText` and call `this.notify()`.

6. **Audio/Video Playback Synchronization**:
   `seekAndPlay(seconds, segmentId)` is already implemented in `state.js:275-296`. Stage 3 teleprompter blocks should call `seekAndPlay(seg.startSec, seg.id)`.

7. **Video Subtitle Overlay**:
   In `VideoPlayer.js:224-248`, the subtitle bar renders `currentSegment.targetText || currentSegment.sourceText`. The speaker badge can be rendered alongside `targetText`.

---

## 7. Recommended Implementation Steps

### Phase 1: Backend Robustness (`webui.py`)
1. Update `voices_handler` to accept `provider` (string or integer) and `target_language` / `targetLanguage` aliases.
2. In `options_handler`, add `ttsProviders` array formatted identically to `asrProviders` and `translationProviders`.
3. Add unit tests in `tests/test_webui.py` or new `tests/test_stage3_voice_dubbing.py` verifying `/api/voices` responses for all 4 providers.

### Phase 2: Frontend Reactive Store (`frontend/js/state.js`)
1. Add `state.speakerVoiceMap = {}`.
2. Add methods:
   - `getDistinctSpeakers()`
   - `setSpeakerVoice(speakerName, voiceRole)`
   - `setSegmentVoiceOverride(segmentId, voiceRole)`
   - `resetSegmentVoiceOverride(segmentId)`
3. Ensure `loadVoices()` updates `speakerVoiceMap` defaults if assigned voices are not in the new provider's voice list.

### Phase 3: Stage 3 Console UI (`frontend/js/screens/Stage3VoiceDubbing.js`)
1. **Upper-Right Console Deck**:
   - Replace static markup with interactive TTS Provider selector bound to `backend.config.ttsType`.
   - Render Voice Casting Matrix: For each distinct speaker in `getDistinctSpeakers()`, display badge, speaker name, and voice selector dropdown bound to `state.speakerVoiceMap[speaker]`.
2. **Teleprompter Feed**:
   - Loop over `state.segments`.
   - Render timestamp (`MM:SS.mmm`), speaker badge with Stage 2 color palette.
   - Render editable `targetText` textarea with `oninput` updating the store.
   - Render Voice Selector:
     - Shows speaker's mapped voice with `(Default)` label if not overridden.
     - Shows selected override if overridden.
     - Displays "Reset to Default" button when `seg.voiceOverride` is active.
3. **Synchronized Seek & Play**:
   - Card click calls `window.dubDubStore.seekAndPlay(seg.startSec, seg.id)`.

### Phase 4: Subtitle Overlay in Preview (`frontend/js/components/VideoPlayer.js`)
1. Ensure active segment's `targetText` is rendered dynamically during video playback with speaker badge.

### Phase 5: Automated Verification
1. Create `tests/test_stage3_voice_dubbing.py` covering:
   - Backend `/api/voices` endpoint with various query parameters.
   - Speaker-to-voice mapping propagation and override isolation in frontend state logic.
   - Component rendering checks for Stage 3 controls and teleprompter items.
2. Run `uv run pytest` to ensure 100% test pass rate.
