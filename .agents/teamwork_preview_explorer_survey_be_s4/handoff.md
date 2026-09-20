# Handoff Report: Stage 4 Backend Survey & Architecture

**Agent**: `explorer_survey_be`  
**Working Directory**: `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be_s4`  
**Handoff Type**: Hard (Task Complete)  
**Date**: 2026-09-20  

---

## 1. Observation

Direct code observations from inspecting the repository:

1. **API Endpoints in `webui.py`**:
   - Lines 1143–1163 of `webui.py`:
     ```python
     app.router.add_get("/", index_handler)
     app.router.add_get("/api/options", options_handler)
     app.router.add_get("/api/voices", voices_handler)
     app.router.add_post("/api/asr-settings/{provider_id}", asr_settings_handler)
     app.router.add_post("/api/asr-settings/{provider_id}/test", test_asr_settings_handler)
     app.router.add_post("/api/translation-settings/{provider_id}", translation_settings_handler)
     app.router.add_post("/api/translation-settings/{provider_id}/test", test_translation_settings_handler)
     app.router.add_post("/api/media", media_handler)
     app.router.add_post("/api/assets/{kind}", edit_asset_handler)
     app.router.add_post("/api/jobs", create_job_handler)
     app.router.add_get("/api/jobs/{job_id}", job_handler)
     app.router.add_get("/api/jobs/{job_id}/transcript", job_transcript_handler)
     app.router.add_get("/api/jobs/{job_id}/segments", job_transcript_handler)
     app.router.add_post("/api/jobs/{job_id}/cancel", cancel_job_handler)
     app.router.add_get("/api/jobs/{job_id}/outputs/{index}", output_handler)
     app.router.add_post("/api/ocr/extract", ocr_extract_handler)
     app.router.add_post("/api/segments/split", split_segment_handler)
     ```
   - Routes `/api/export`, `/api/render`, `/api/upload` do not exist as distinct routes; media upload is handled at `/api/media`, asset upload at `/api/assets/{kind}`, and render/export at `/api/jobs` with `jobType: "render"`.

2. **Asset Upload Handler in `webui.py`**:
   - Lines 758–785 of `webui.py`:
     ```python
     async def edit_asset_handler(request: web.Request) -> web.Response:
         kind = request.match_info["kind"]
         allowed = {
             "background-audio": AUDIO_EXITS,
             "thumbnail": {"png", "jpg", "jpeg", "webp"},
         }
         ...
         saved = UPLOAD_DIR / f"edit-{uuid.uuid4().hex}-{filename}"
         ...
         asset_id = uuid.uuid4().hex
         with EDIT_ASSETS_LOCK:
             EDIT_ASSETS[asset_id] = saved
         return web.json_response({"id": asset_id, "name": filename}, status=201)
     ```

3. **Job Creation & Option Translation**:
   - Lines 804–818 of `webui.py`:
     ```python
     for option_key, path_key in (("backgroundAudioId", "backgroundMusicPath"), ("thumbnailId", "thumbnailPath")):
         asset_id = str(options.get(option_key) or "")
         if not asset_id:
             continue
         with EDIT_ASSETS_LOCK:
             asset_path = EDIT_ASSETS.get(asset_id)
         if asset_path is None or not asset_path.is_file():
             raise web.HTTPBadRequest(text=f"Unknown or expired {option_key}")
         options[path_key] = asset_path.resolve().as_posix()
     ...
     params = build_task_params(media.path, options, job_type=job_type)
     ensure_asr_configured(params["recogn_type"], request.app["settings_store"])
     if job_type not in {"asr", "render"}:
         ensure_translation_configured(params["translate_type"], request.app["settings_store"])
     ```
   - Lines 544–557 of `webui.py`:
     ```python
     "voice_rate": str(options.get("voiceRate") or "+0%"),
     "volume": str(options.get("volume") or "+0%"),
     "pitch": "+0Hz",
     **timing_flags,
     "subtitle_type": 1,
     "subtitles": str(options.get("subtitles") or ""),
     "background_music": options.get("backgroundMusicPath"),
     "backaudio_volume": max(0.0, min(1.5, float(options.get("backgroundAudioVolume", 0.8)))),
     "source_audio_volume": max(0.0, min(1.5, float(options.get("originalAudioVolume", 0.0)))),
     "thumbnail": options.get("thumbnailPath"),
     "subtitle_style": options.get("subtitleStyle") if isinstance(options.get("subtitleStyle"), dict) else None,
     "clear_cache": job_type != "render",
     "embed_bgm": True,
     ```

4. **Task Orchestrator Authoritative Subtitles & Cache**:
   - Lines 169–181 of `videotrans/task/orchestrator.py`:
     ```python
     if task.cfg.subtitles:
         task.cfg.clear_cache = False
         Path(task.cfg.source_sub).parent.mkdir(parents=True, exist_ok=True)
         Path(task.cfg.source_sub).write_text(task.cfg.subtitles, encoding="utf-8")
         Path(task.cfg.target_sub).write_text(task.cfg.subtitles, encoding="utf-8")
         from videotrans.util.help_srt import get_subtitle_from_srt
         task.source_srt_list = get_subtitle_from_srt(task.cfg.source_sub, is_file=True) or []
         task.target_srt_list = get_subtitle_from_srt(task.cfg.target_sub, is_file=True) or []
         task.should_recogn = False
         task.should_trans = False
     ```

5. **Audio Mixing Implementation**:
   - Lines 15–61 of `videotrans/task/_stage_audio.py`:
     - `_back_music()` converts `background_music` with `["-filter:a", f"volume={self.cfg.backaudio_volume}"]`, extends/loops it if `loop_backaudio`, and mixes it into `target.wav` via ffmpeg `amix=inputs=2:duration=first:dropout_transition=2`.
     - `_mix_original_audio()` checks `source_audio_volume`. If `volume <= 0`, skips mixing. If `> 0`, applies `[1:a]volume={volume}[original];[0:a][original]amix=inputs=2:duration=first:dropout_transition=2` to mix `source.wav` into `target.wav`.
   - Lines 156–161 of `videotrans/task/_stage_assemble.py`:
     Calls `self._back_music()`, then `self._mix_original_audio()`, then `self._separate()`.

6. **Cover Image / Thumbnail Embedding**:
   - Lines 248–263 of `videotrans/task/orchestrator.py`:
     ```python
     def _embed_thumbnail(cfg: TaskCfgVTT) -> None:
         thumbnail = Path(cfg.thumbnail).resolve() if cfg.thumbnail else None
         video = Path(cfg.targetdir_mp4).resolve() if cfg.targetdir_mp4 else None
         if not thumbnail or not thumbnail.is_file() or not video or not video.is_file():
             return
         from videotrans.util.help_ffmpeg import runffmpeg
         staged = Path(cfg.cache_folder) / f"thumbnail-{video.name}"
         runffmpeg([
             '-y', '-i', video.as_posix(), '-i', thumbnail.as_posix(),
             '-map', '0', '-map', '1', '-c', 'copy', '-c:v:1', 'mjpeg',
             '-disposition:v:1', 'attached_pic', staged.as_posix(),
         ])
         if staged.is_file():
             staged.replace(video)
     ```

7. **Subtitle ASS Styling**:
   - Lines 45–60 of `videotrans/util/_srt_ass.py`:
     ```python
     if style_override:
         def ass_color(value: str, fallback: str) -> str:
             match = re.fullmatch(r'#([0-9a-fA-F]{6})', str(value or ''))
             if not match:
                 return fallback
             rgb = match.group(1)
             return f"&H00{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}&"
         style.update({
             'Fontname': str(style_override.get('fontFamily') or style.get('Fontname', 'Arial')),
             'Fontsize': max(8, min(96, int(style_override.get('fontSize', style.get('Fontsize', 24))))),
             'PrimaryColour': ass_color(style_override.get('color'), '&H00FFFFFF&'),
             'OutlineColour': ass_color(style_override.get('outlineColor'), '&H00000000&'),
             'Outline': max(0, min(10, int(style_override.get('outlineWidth', 2)))),
             'Shadow': max(0, min(10, int(style_override.get('shadowSize', 2)))),
         })
     ```

---

## 2. Logic Chain

1. **Endpoint Resolution**:
   - From Observation 1, the client submits jobs to `POST /api/jobs`.
   - From Observation 3, when `jobType == "render"`, `build_task_params` sets `clear_cache = False` and bypasses the translation configuration check (`if job_type not in {"asr", "render"}`).
   - Therefore, the backend already contains the core pipeline hook for Stage 4 video rendering via `POST /api/jobs`.

2. **Asset ID to Physical File Binding**:
   - From Observation 2, asset files uploaded to `/api/assets/background-audio` and `/api/assets/thumbnail` are saved to disk and recorded in memory in `EDIT_ASSETS`.
   - From Observation 3, `create_job_handler` resolves `backgroundAudioId` -> `backgroundMusicPath` and `thumbnailId` -> `thumbnailPath`.
   - If invalid or expired IDs are sent, HTTP 400 is returned. If valid, physical paths are bound to task parameters.

3. **Audio Mixing Consistency**:
   - From Observation 3 and 5, `originalAudioVolume` and `backgroundAudioVolume` are clamped to `[0.0, 1.5]`.
   - Dubbed TTS voice volume is passed via `volume` (`"+0%"`, `"-20%"`, etc.) and applied directly during speech synthesis in `_stage_dubbing.py`.
   - In `_stage_assemble.py`, `_back_music()` mixes BGM into `target.wav` using ffmpeg `amix`, and `_mix_original_audio()` mixes `source.wav` into `target.wav`.
   - When original audio is muted (`source_audio_volume == 0`), `_mix_original_audio()` returns immediately without mixing, ensuring silence for the original track.

4. **Thumbnail Attachment Without Re-encoding**:
   - From Observation 6, `_embed_thumbnail()` executes ffmpeg with `-c copy -c:v:1 mjpeg -disposition:v:1 attached_pic`.
   - This copies existing video/audio streams losslessly and adds the cover picture metadata in a fraction of a second.
   - When no thumbnail is uploaded (`cfg.thumbnail is None`), this step is omitted, maintaining the native video's first frame.

5. **Subtitle Editing Authority & ASS Generation**:
   - From Observation 4, passing `options.subtitles` immediately overwrites `source_sub` and `target_sub` with the edited SRT and turns off `should_recogn` and `should_trans`.
   - From Observation 7, during subtitle burning, `set_ass_font()` extracts `subtitleStyle` properties (`fontSize`, `fontFamily`, `color`, `outlineColor`, `outlineWidth`, `shadowSize`) and writes an ASS file that ffmpeg burns into the final video.

---

## 3. Caveats

1. **In-Memory Asset Lifetime**:
   `EDIT_ASSETS` is stored in an in-memory dictionary. If the Python server restarts between asset upload and job submission, asset IDs will become invalid. This is acceptable for a single-server WebUI workflow, but temporary file cleanup or persistent mapping could be considered for long-lived environments.
2. **Multi-Speaker Per-Block Voice Override in Stage 4 Re-dubbing**:
   In `_stage_dubbing.py`, per-line voice roles come from `app_cfg.line_roles`. In `webui.py:build_task_params`, `line_roles` is not currently set from `options`. While Stage 3 handles preview in the browser, passing `lineRoles` or `speakerVoiceMap` in `options` to populate `app_cfg.line_roles` will ensure multi-speaker assignments are preserved during backend re-dubbing.
3. **Route Aliasing Ergonomics**:
   While the frontend currently calls `POST /api/jobs`, users or external consumers may expect `POST /api/export` or `POST /api/render`. Adding routing aliases is recommended.

---

## 4. Conclusion

1. **Backend Readiness**: The backend pipeline in `webui.py`, `videotrans/task/orchestrator.py`, `_stage_audio.py`, `_stage_assemble.py`, and `_srt_ass.py` is fully architected and capable of supporting Stage 4 CapCut-style video editing.
2. **Audio Mixing**: Independent sliders for Dubbed TTS (`volume`), Background Music (`backaudio_volume`), and Original Audio (`source_audio_volume`) are correctly wired into ffmpeg `amix` filter graphs.
3. **BGM & Thumbnail Ingestion**: Handled through `POST /api/assets/{kind}`, mapped via UUID to physical disk paths, and embedded without stream re-encoding.
4. **Authoritative Subtitles**: Edited SRT strings bypass recognition and translation stages, applying custom font size and styling via ASS conversion.
5. **Exact Payload Contracts**: Detailed JSON schemas and specifications have been documented in `survey_be.md`.

---

## 5. Verification Method

1. **Inspect Target Files**:
   - View `webui.py` lines 544–557 and 758–826 to confirm asset handling, task parameter mapping, and `jobType: "render"` handling.
   - View `videotrans/task/_stage_audio.py` lines 15–61 to verify `_back_music()` and `_mix_original_audio()`.
   - View `videotrans/task/orchestrator.py` lines 169–181 and 248–263 to verify authoritative subtitles and `_embed_thumbnail()`.
   - View `videotrans/util/_srt_ass.py` lines 45–60 to verify ASS styling.
2. **Automated Test Verification**:
   - Inspect `tests/test_stage4_edit_video.py` where:
     - `test_render_params_reuse_edited_srt_and_mix_settings` tests `webui.build_task_params(source, options, job_type="render")`.
     - `test_edit_asset_rejects_unsupported_extensions` tests extension validation for BGM and thumbnails.
   - Run tests:
     `uv run pytest tests/test_stage4_edit_video.py -v`
3. **Report Deliverable**:
   - Confirm presence and content of:
     `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be_s4\survey_be.md`
