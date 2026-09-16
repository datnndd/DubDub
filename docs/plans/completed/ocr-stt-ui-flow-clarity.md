# Execution Plan: Subtitle Source Clarity (Audio STT vs Video OCR)

Date: 2026-08-14

## Outcome

Provide unambiguous user control and visual state for selecting the subtitle source on the main application interface:
1. Allow the user to explicitly select between **Audio Speech Recognition (STT)** and **Hard-Subtitle OCR (Video OCR)**.
2. When **Hard-Subtitle OCR** is selected:
   - Visually and logically disable STT-only controls (`recogn_type`, `model_name`, `remove_noise`, `recogn2pass`).
   - Enable and highlight the **OCR Region** button (`btn_ocr_roi`).
   - Store and pass `subtitle_source = "video_ocr"`, normalized `roi`, and OCR options into the task configuration (`TaskCfgVTT`).
3. When **Start** is clicked with `subtitle_source == "video_ocr"`:
   - Execute PaddleOCR scanning on the video ROI to produce the source SRT.
   - Bypass audio speech recognition stage while continuing downstream translation, dubbing, alignment, and assembly as configured.

## Approach

1. **UI Layer (`videotrans/ui/_setup_rows.py`, `videotrans/ui/en.py`)**:
   - Add an explicit Subtitle Source selector (`ui.subtitle_source_type` or integrated QComboBox) in the ASR row.
   - Wire toggled state so selecting `video_ocr` disables STT engine selection (`recogn_type`, `model_name`, etc.) and enables `btn_ocr_roi`.
2. **Main Window Actions (`videotrans/mainwin/_actions_config.py`, `videotrans/mainwin/_bind_signals.py`, `videotrans/mainwin/_actions_check.py`)**:
   - Handle subtitle source mode switches.
   - Update `RoiDialog` (`ocr.py`) on confirmation to store `app_cfg.ocr_roi` / `params['ocr_roi']` and update UI status.
   - Collect `subtitle_source` and `roi` into `self.cfg` in `_actions_check.py`.
3. **Task & Pipeline Layer (`videotrans/task/taskcfg.py`, `videotrans/task/_stage_recogn.py`)**:
   - Ensure `TaskCfgVTT` captures `subtitle_source`, `ocr_roi`, `ocr_lang`.
   - Validate `_stage_recogn.py` routes to `video_ocr` scanner when `subtitle_source == "video_ocr"`.
4. **Validation**:
   - Add unit tests for UI subtitle source mode switching, STT control disabling, task configuration building, and task routing execution.

## Progress

- [x] Add explicit Subtitle Source mode controls & STT lock state to UI.
- [x] Connect `RoiDialog` confirmation to main window state.
- [x] Pass `subtitle_source` & `ocr_roi` in task configuration building (`_actions_check.py`).
- [x] Run focused tests for UI state, task configuration, and OCR stage routing.

## Validation Plan

- Unit test for UI mode switching (selecting OCR disables `recogn_type` & `model_name`, enables `btn_ocr_roi`).
- Unit test for `_actions_check.py` populating `subtitle_source = "video_ocr"` when OCR is selected.
- Unit test for `_stage_recogn.py` bypassing STT and invoking OCR scanner.
