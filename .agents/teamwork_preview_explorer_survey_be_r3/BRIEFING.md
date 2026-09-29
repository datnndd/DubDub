# BRIEFING — 2026-09-29T06:33:00Z

## Mission
Survey the backend ASS subtitle generation and video burn-in execution pipeline in pyvideotrans to support R2 styling features (font, weight, italic, opacity, colors, outline, shadow) and video burn-in.

## 🔒 My Identity
- Archetype: explorer
- Roles: Backend ASS & Video Burn-in Explorer
- Working directory: C:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be_r3
- Original parent: d744a541-ceea-44ea-a5fc-b0a5d44d8a78
- Milestone: Preview & Dubbing Studio ASS/Burn-in R2

## 🔒 Key Constraints
- Read-only investigation — do NOT implement / modify source code
- Produce structured handoff report in handoff.md
- Document exact file paths, line numbers, mappings, formulas, and gap analysis

## Current Parent
- Conversation ID: d744a541-ceea-44ea-a5fc-b0a5d44d8a78
- Updated: 2026-09-29T06:33:00Z

## Investigation State
- **Explored paths**:
  - `frontend/src/store/editVideoSlice.ts` (`buildRenderRequest`, `subtitleStyles` state)
  - `frontend/src/types/editor.ts` (`SubtitleStyleSettings`)
  - `frontend/src/screens/Stage4EditVideo.tsx` (Subtitles inspector tab)
  - `frontend/src/components/VideoPlayer.tsx` (`capcutStyle` canvas rendering)
  - `videotrans/api/task_params.py` (`build_task_params`)
  - `videotrans/task/taskcfg.py` (`TaskCfgVTT.subtitle_style`)
  - `videotrans/util/_srt_ass.py` (`set_ass_font`, `ass_color`, `default_style`)
  - `videotrans/task/_stage_subtitle.py` (`_process_subtitles`)
  - `videotrans/task/_stage_assemble.py` (FFmpeg assemble with `-filter_complex "[0:v]subtitles=filename='...'[v_out]"`)
  - `videotrans/task/orchestrator.py` (`run`, `_persist_stage_artifacts`, `_collect_outputs`)
  - `videotrans/core/project_store.py` (`init_project_dirs`, `get_project_dir`)
  - `tests/test_stage4_edit_video.py` (existing 27 unit tests)
- **Key findings**:
  - `buildRenderRequest` forwards `subtitleStyle: state.subtitleStyles` into `options.subtitleStyle`.
  - `task_params.py` populates `params["subtitle_style"] = options.get("subtitleStyle")`, stored on `task.cfg.subtitle_style`.
  - In `_srt_ass.py`, `style_override` currently only parses `fontFamily`, `fontSize`, `color`, `outlineColor`, `outlineWidth`, and `shadowSize`.
  - `fontWeight` (ASS `Bold`: -1/0), `fontStyle` (ASS `Italic`: -1/0), and `opacity` (ASS `PrimaryColour` alpha byte `&HAABBGGRR&`) are completely unmapped in `_srt_ass.py`.
  - In ASS standard, Alpha byte `00` = 100% opaque, `FF` = 0% opaque (fully transparent); inverse formula `round((1 - op) * 255)`.
  - FFmpeg burn-in filter uses `[0:v]subtitles=filename='end.ass'[v_out]` executed in cache directory.
  - Rendered output is saved to `output/projects/{projectId}/exports/{noextname}.mp4` (or `output/{safe_stem}/{noextname}.mp4`).
- **Unexplored areas**: None. Complete investigation finished.

## Key Decisions Made
- Formulated exact mathematical mapping for Opacity -> ASS Alpha byte `00..FF` and hex conversion.
- Formulated exact mapping for Bold (`-1`/`0`) and Italic (`-1`/`0`).
- Documented sanitization for `fontFamily` (extract primary from CSS list, map "System default" -> "Arial").

## Artifact Index
- DISPATCH.md — incoming dispatch instructions
- progress.md — liveness heartbeat
- handoff.md — final handoff report
