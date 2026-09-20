# Challenger 2 Verification Report — Stage 4: Edit Video Redesign

**Subagent Identity**: `challenger_2` (Empirical Challenger)  
**Date**: 2026-09-20  
**Target Milestone**: Stage 4: Edit Video Redesign & Verification  
**Final Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### Observation 1: Immediate Test Collection Failure in `tests/test_stage4_edit_video.py`
Running the mandatory verification command directly from project root:
```powershell
uv run pytest tests/test_stage4_edit_video.py -v
```
Failed immediately during test collection with exit code 1:
```
============================= test session starts =============================
platform win32 -- Python 3.10.19, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Users\ddat2\Downloads\Projects\pyvideotrans
configfile: pyproject.toml
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
______________ ERROR collecting tests/test_stage4_edit_video.py _______________
ImportError while importing test module 'C:\Users\ddat2\Downloads\Projects\pyvideotrans\tests\test_stage4_edit_video.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
..\..\..\AppData\Roaming\uv\python\cpython-3.10.19-windows-x86_64-none\lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\test_stage4_edit_video.py:72: in <module>
    from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus
E   ImportError: cannot import name 'CancellationToken' from 'videotrans.task.job' (C:\Users\ddat2\Downloads\Projects\pyvideotrans\videotrans\task\job.py)
=========================== short test summary info ===========================
ERROR tests/test_stage4_edit_video.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.79s ===============================
```
- Line 72 of `tests/test_stage4_edit_video.py` imports from `videotrans.task.job`:
  ```python
  from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus
  ```
- In reality, `CancellationToken`, `TaskRequest`, `TaskResult`, and `TaskStatus` are declared in `videotrans.task.orchestrator` (see `videotrans/task/orchestrator.py:58-67`).
- Furthermore, `videotrans/task/job.py:4` imports `from PySide6.QtCore import QThread`, which throws `ModuleNotFoundError: No module named 'PySide6'` in headless and WebUI runtime environments.

### Observation 2: Test Double Signature Mismatch & Thread Exception in `tests/test_stage4_edit_video.py`
In `tests/test_stage4_edit_video.py:96-98`:
```python
def _runner(request, accept, token):
    accept(0.5, "Rendering audio mix and burning subtitles...")
    return TaskResult(status=TaskStatus.SUCCEEDED, outputs=[Path("output.mp4")])
```
In `webui.py:166`:
```python
def accept(self, event: TaskEvent) -> None:
```
When jobs are executed in tests, the worker thread in `webui.py:240` invokes `job.accept` with 2 arguments instead of a `TaskEvent`, throwing an unhandled thread exception:
```
TypeError: JobRecord.accept() takes 2 positional arguments but 3 were given
```
Additionally, `TaskResult` instantiation in `_runner` omitted the required positional arguments `job_id: str` and `output_dir: Path` defined in `videotrans/task/orchestrator.py:58-64`.

### Observation 3: Unhandled `ValueError` in Backend Volume Parsing
In `webui.py:564-565`:
```python
"backaudio_volume": max(0.0, min(1.5, float(options.get("backgroundAudioVolume", 0.8)))),
"source_audio_volume": max(0.0, min(1.5, float(options.get("originalAudioVolume", 0.0)))),
```
`float(...)` is executed directly without a `try...except (ValueError, TypeError)` guard.
When `test_adversarial_invalid_audio_mix_inputs` passes `'not-a-number'`, `build_task_params` crashes with:
```
E   ValueError: could not convert string to float: 'not-a-number'
```
This causes an unhandled HTTP 500 error on the server if client inputs are corrupted or non-numeric.

### Observation 4: Asset Ingestion Vulnerability in `edit_asset_handler`
In `webui.py:781-807`:
```python
if request.content_type and "multipart" in request.content_type.lower():
    ...
else:
    raw_name = request.headers.get("X-Filename") or request.query.get("filename") or ""
    if raw_name:
        filename = Path(unquote(raw_name)).name
    else:
        default_ext = "mp3" if kind == "background-audio" else "png"
        filename = f"asset.{default_ext}"
    ...
    content = await request.read()
    if content:
        saved = UPLOAD_DIR / f"edit-{uuid.uuid4().hex}-{filename}"
        saved.write_bytes(content)
```
When a client sends a standard urlencoded form without files (e.g. `otherField=test`), the `content_type` does not contain `"multipart"`. The handler enters the `else:` branch, falls back to `default_ext = "mp3"`, writes the raw bytes `b"otherField=test"` to disk, registers it in `EDIT_ASSETS`, and returns `201 Created` with a new asset ID instead of `400 Bad Request`.
This caused `test_asset_upload_requires_file_or_content` to fail:
```
E   AssertionError: assert 201 == 400
```

### Observation 5: Screen Render Test Failed on Tabbed Inspector Structure
In `tests/test_stage4_edit_video.py:911` (`test_headless_node_stage4_screen_render`):
The test set `state.editVideo.activeTab = "subtitles"` and then asserted:
```javascript
['audio-mix-slider', html.includes('data-mix-slider')]
```
In `frontend/js/screens/Stage4EditVideo.js:101-155`, the inspector content is conditionally rendered based on `activeTab`:
- When `activeTab === 'subtitles'`, only the Subtitles inspector is rendered.
- `audioSlider` (and therefore `data-mix-slider`) only exists inside `activeTab === 'audio'`.
Consequently, the test failed with `Check failed: audio-mix-slider`.

### Observation 6: Successful Empirical Verification of Frontend & Timeline Logic
Using our independent Node.js stress harness (`tests/stage4_stress_harness.mjs`) and pytest suite (`tests/test_stage4_adversarial_challenger2.py`), 15 adversarial test cases passed:
1. **0 duration & empty segments**: `Math.max(1, durationSec || 60)` prevents division by zero; time ruler starts at `00:00.000` with no `NaN` values.
2. **Single segment**: Correctly disables Prev/Next navigation buttons.
3. **150 dense segments**: Renders in < 20ms with monotonic, non-negative `left%` and `width%` layout coordinates.
4. **Zero-duration segment**: `width` clamped to `Math.max(0.8, ...)%`, preserving clickability; CPS calculation uses `Math.max(0.1, dur)` avoiding division by zero.
5. **Pointer scrubbing coordinates**: Clamps negative `clientX` offsets to `0.0` and offsets exceeding timeline container to `1.0`.
6. **Font size synchronization**: Clamps values strictly between `8` and `64` px; non-numeric inputs fallback to default `22` px; updates `[data-canvas-subtitle].style.fontSize` immediately.
7. **Unicode & XSS resilience**: Preserves Vietnamese tone marks (`Chào mừng`), Chinese Hanzi (`深度学习`), Arabic RTL, and emojis (`🎬 🚀`); properly escapes HTML strings (`&lt;script&gt;`, `&quot;quotes&quot;`).
8. **Timing boundary enforcement**: `updateStage4Timing` guarantees `startSec < endSec - 0.001` and enforces adjacent boundaries (`seg[k].startSec >= seg[k-1].endSec`, `seg[k].endSec <= seg[k+1].startSec`).
9. **SRT serialization**: Produces standard 1-based indexed blocks with comma milliseconds (`HH:MM:SS,mmm --> HH:MM:SS,mmm`) and double newline separation.
10. **Typing focus preservation**: Keystrokes in `data-segment-input="stage4-${id}"` set `isActivelyTyping = true`, suppressing `this.notify()` and preserving textarea DOM element and cursor.
11. **Thumbnail lifecycle**: Successful upload -> replace -> reset transitions; Object URLs are revoked upon removal.

---

## 2. Logic Chain

1. **Premise 1**: The worker claimed in `TEST_READY.md` that `tests/test_stage4_edit_video.py` is ready and passing with `uv run pytest tests/test_stage4_edit_video.py -v`.
2. **Premise 2**: Direct empirical execution of `uv run pytest tests/test_stage4_edit_video.py -v` crashes immediately with `ImportError: cannot import name 'CancellationToken' from 'videotrans.task.job'`, exiting with code 1 without running a single test.
3. **Premise 3**: Even when shimming the import redirect to `videotrans.task.orchestrator`, 3 tests fail outright (`test_asset_upload_requires_file_or_content`, `test_headless_node_stage4_screen_render`, `test_adversarial_invalid_audio_mix_inputs`) and background threads throw `TypeError: JobRecord.accept() takes 2 positional arguments but 3 were given`.
4. **Premise 4**: In `webui.py`, unhandled `ValueError` in `float(options.get("backgroundAudioVolume", ...))` and unhandled fallback in `edit_asset_handler` represent genuine production server vulnerabilities.
5. **Conclusion**: The codebase cannot be approved until the test suite imports and fixtures are fixed, and the backend routes in `webui.py` handle non-numeric volume strings and non-file asset uploads safely.

---

## 3. Caveats

- **Frontend Core Quality**: The client-side implementation (`Stage4EditVideo.js` and `state.js`) is robust and verified through our 15-case empirical stress harness. The failures reside in `tests/test_stage4_edit_video.py` imports/fixtures and `webui.py` edge case parsing.
- **PySide6 Dependency**: Testing in headless/CI environments requires test files to import orchestrator primitives from `videotrans.task.orchestrator`, not `videotrans.task.job`.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

The worker must address the following specific defects:
1. **Fix `tests/test_stage4_edit_video.py` Imports**:
   Change line 72 from:
   ```python
   from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus
   ```
   to:
   ```python
   from videotrans.task.orchestrator import (
       CancellationToken,
       EventKind,
       TaskEvent,
       TaskRequest,
       TaskResult,
       TaskStatus,
   )
   ```
2. **Fix `dummy_job_runner` in `tests/test_stage4_edit_video.py:96-98`**:
   Update `accept` call to pass a single `TaskEvent` instance:
   ```python
   def _runner(request, accept, token):
       accept(TaskEvent(request.job_id, EventKind.STAGE_STARTED, "render", message="Rendering audio mix and burning subtitles..."))
       return TaskResult(request.job_id, TaskStatus.SUCCEEDED, Path("."), (Path("output.mp4"),))
   ```
3. **Fix Volume Parsing in `webui.py:564-565`**:
   Safely parse `backgroundAudioVolume` and `originalAudioVolume` with fallback to defaults if `float()` raises `(ValueError, TypeError)`:
   ```python
   def _safe_float(val, default):
       try: return float(val)
       except (ValueError, TypeError): return default

   "backaudio_volume": max(0.0, min(1.5, _safe_float(options.get("backgroundAudioVolume"), 0.8))),
   "source_audio_volume": max(0.0, min(1.5, _safe_float(options.get("originalAudioVolume"), 0.0))),
   ```
4. **Fix Asset Ingestion Guard in `webui.py:781-807`**:
   In `edit_asset_handler`, do not write fallback raw body if `content_type` is urlencoded form or content is not binary media. Require an explicit `X-Filename` header or reject empty/form payloads with HTTP 400.
5. **Fix `test_headless_node_stage4_screen_render` in `tests/test_stage4_edit_video.py:890`**:
   Set `state.editVideo.activeTab = "audio"` (or test each tab individually) so that `data-mix-slider` is present in the rendered HTML output.

---

## 5. Verification Method

1. **Verify primary test command**:
   ```powershell
   uv run pytest tests/test_stage4_edit_video.py -v
   ```
   Must exit with code 0 and all test cases passing without import errors or unhandled thread exceptions.
2. **Verify Challenger 2 adversarial stress harness**:
   ```powershell
   node tests/stage4_stress_harness.mjs
   uv run pytest tests/test_stage4_adversarial_challenger2.py -v
   ```
   Both must report 100% pass rate.
3. **Invalidation conditions**:
   If `uv run pytest tests/test_stage4_edit_video.py -v` exits with non-zero or fails during test collection, the review remains blocked.
