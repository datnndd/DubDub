# Remediation Plan: Stage 4 Test Suite Import & Fixture Defect Resolution

**Target File**: `tests/test_stage4_edit_video.py`  
**Companion File**: `webui.py`  
**Investigator**: `explorer_remediate_1`  
**Date**: 2026-09-20  
**Status**: Ready for Implementation  

---

## 1. Executive Summary

During Iteration 1 of the Stage 4 ("Edit Video") redesign, an Integrity Violation was flagged by Forensic Auditor `auditor_1`, confirmed by Reviewers 1 & 2, and Challengers 1 & 2. The primary verification command `uv run pytest tests/test_stage4_edit_video.py -v` failed immediately at collection time due to an invalid import from `videotrans.task.job`. Furthermore, once bypassed, daemon worker threads in the test suite crashed due to signature mismatches in the `dummy_job_runner` fixture, and `test_headless_node_stage4_screen_render` failed due to an invalid DOM assumption across tab boundaries.

This investigation defines the exact root causes, architectural contracts, and code modifications required to restore `tests/test_stage4_edit_video.py` to a 100% passing state.

---

## 2. Root Cause Analysis

### 2.1 Defect 1: Invalid Module Import (`tests/test_stage4_edit_video.py:72`)

#### Observation:
In `tests/test_stage4_edit_video.py` line 72:
```python
from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus
```

#### Evidence:
Inspection of `videotrans/task/job.py` confirms that `job.py` contains Qt GUI worker threads (`BaseWorker(QThread)`, `WorkerPrepare`, `WorkerRegcon`, etc.) and requires `PySide6.QtCore`. It defines none of `CancellationToken`, `TaskRequest`, `TaskResult`, or `TaskStatus`.

The UI-independent task orchestration engine is implemented in `videotrans/task/orchestrator.py`, which is the canonical source for all four types:
- `videotrans/task/orchestrator.py:20`: `class EventKind(str, Enum)`
- `videotrans/task/orchestrator.py:32`: `class TaskStatus(str, Enum)`
- `videotrans/task/orchestrator.py:38`: `class TaskEvent`
- `videotrans/task/orchestrator.py:58`: `class TaskResult`
- `videotrans/task/orchestrator.py:67`: `class CancellationToken`
- `videotrans/task/orchestrator.py:79`: `class TaskRequest`

This matches the existing import in `webui.py:25-33` and `tests/test_orchestrator.py:6-11`.

#### Solution:
Update line 72 to import from `videotrans.task.orchestrator`. In addition, include `EventKind` and `TaskEvent` so that test fixtures can construct structured events.

---

### 2.2 Defect 2: `dummy_job_runner` Signature Mismatches (`tests/test_stage4_edit_video.py:94-99`)

#### Observation:
In `tests/test_stage4_edit_video.py` lines 94-99:
```python
@pytest.fixture
def dummy_job_runner():
    """Deterministic immediate job runner double for JobManager testing."""
    def _runner(request, accept, token):
        accept(0.5, "Rendering audio mix and burning subtitles...")
        return TaskResult(status=TaskStatus.SUCCEEDED, outputs=[Path("output.mp4")])
    return _runner
```

#### Evidence:
When `JobManager.submit` executes this runner in a background worker thread (`webui.py:240`):
```python
result = runner(TaskRequest(params), job.accept, job.token)
```
Two severe type errors occur:

1. **`accept` takes a single `TaskEvent` instance**:
   In `webui.py:166`:
   ```python
   def accept(self, event: TaskEvent) -> None:
       item = {
           "kind": event.kind.value,
           "stage": event.stage,
           "message": event.message,
           "progress": event.progress,
           "details": dict(event.details),
       }
   ```
   Calling `accept(0.5, "Rendering audio mix and burning subtitles...")` passes two positional arguments (`event=0.5`, `second_arg="Rendering..."`). Python raises:
   ```text
   TypeError: JobRecord.accept() takes 2 positional arguments but 3 were given
   ```

2. **`TaskResult` requires `job_id` and `output_dir`**:
   In `videotrans/task/orchestrator.py:58-65`:
   ```python
   @dataclass(frozen=True)
   class TaskResult:
       job_id: str
       status: TaskStatus
       output_dir: Path
       outputs: tuple[Path, ...] = ()
       failure: TaskFailure | None = None
       segments: tuple[dict[str, Any], ...] = ()
   ```
   `job_id` and `output_dir` have NO default values. Calling `TaskResult(status=TaskStatus.SUCCEEDED, outputs=[Path("output.mp4")])` raises:
   ```text
   TypeError: TaskResult.__init__() missing 2 required positional arguments: 'job_id' and 'output_dir'
   ```

#### Solution:
Update `dummy_job_runner` to extract `job_id` and `output_dir` from `request.params` (with safe fallbacks), emit a proper `TaskEvent`, and construct `TaskResult` with all required positional parameters:
```python
@pytest.fixture
def dummy_job_runner():
    """Deterministic immediate job runner double for JobManager testing."""
    def _runner(request, accept, token):
        job_id = getattr(request, "job_id", None) or (request.params.get("uuid") if hasattr(request, "params") else None) or "test-job"
        output_dir = Path(request.params.get("target_dir", ".")) if hasattr(request, "params") else Path(".")
        accept(TaskEvent(
            job_id=str(job_id),
            kind=EventKind.PROGRESS,
            stage="render",
            message="Rendering audio mix and burning subtitles...",
            progress=50.0,
        ))
        return TaskResult(
            job_id=str(job_id),
            status=TaskStatus.SUCCEEDED,
            output_dir=output_dir,
            outputs=(Path("output.mp4"),),
        )
    return _runner
```

---

### 2.3 Defect 3: Headless Node Multi-Tab Screen Render Defect (`tests/test_stage4_edit_video.py:850-912`)

#### Observation:
In `test_headless_node_stage4_screen_render`:
```javascript
    state.editVideo = {
        audioMix: { original: 20, dubbed: 100, background: 40 },
        backgroundAudio: { name: "test_bgm.mp3", previewUrl: "blob:bgm" },
        thumbnail: { name: "test_thumb.png", previewUrl: "blob:thumb" },
        activeTab: "subtitles"
    };
    ...
    const checks = [
        ...
        ['audio-mix-slider', html.includes('data-mix-slider')],
        ['thumbnail-input', html.includes('stage4-thumbnail-input')],
    ];
```
This fails with `Check failed: audio-mix-slider`.

#### Evidence:
In `frontend/js/screens/Stage4EditVideo.js:101-258`, the inspector is a tabbed panel:
- `activeTab === 'audio'`: Renders audio mix sliders (`data-mix-slider`) and BGM manager.
- `activeTab === 'subtitles'`: Renders subtitle typography controls (`fontSize`, `data-stage4-subtitle`).
- `activeTab === 'thumbnail'`: Renders thumbnail upload (`stage4-thumbnail-input`, `data-thumbnail-preview`).

Setting `activeTab: "subtitles"` and asserting elements from the `audio` and `thumbnail` tabs simultaneously in a single HTML string violates the tabbed DOM contract.

#### Solution:
In the Node test script, render the screen across all three tabs (`subtitles`, `audio`, `thumbnail`), validating tab-specific elements against their corresponding rendered HTML while validating shared layout structures (preview canvas, timeline tracks, playhead) across the render outputs.

---

## 3. Companion Backend Fixes in `webui.py` (Summary)

To ensure all 32 tests in `test_stage4_edit_video.py` pass without external blockers, the implementer must also ensure the companion backend fixes identified in the Forensic Audit are applied in `webui.py`:
1. **Safe volume coercion** (`webui.py:564-565`): Handle `None` and non-numeric strings (e.g. `'not-a-number'`) gracefully in `build_task_params` instead of throwing unhandled `TypeError`/`ValueError`.
2. **Asset ingestion content guard** (`webui.py:781-808`): Reject urlencoded form bodies without media files with `HTTP 400 Bad Request`, and use `request.app["media_store"].upload_dir` for file saving.
3. **ASR check bypass** (`webui.py:845`): Skip `ensure_asr_configured` when `job_type == "render"`.

---

## 4. Exact Code Modifications for `tests/test_stage4_edit_video.py`

### 4.1 Modification 1: Module Import (Line 72)

```diff
--- a/tests/test_stage4_edit_video.py
+++ b/tests/test_stage4_edit_video.py
@@ -69,7 +69,14 @@ from aiohttp import web
 from aiohttp.test_utils import TestClient, TestServer
 import pytest
 
-from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus
+from videotrans.task.orchestrator import (
+    CancellationToken,
+    EventKind,
+    TaskEvent,
+    TaskRequest,
+    TaskResult,
+    TaskStatus,
+)
 from videotrans.task.taskcfg import InputFile
 from videotrans.util._srt_ass import set_ass_font
 import webui
```

### 4.2 Modification 2: `dummy_job_runner` Fixture (Lines 94-99)

```diff
--- a/tests/test_stage4_edit_video.py
+++ b/tests/test_stage4_edit_video.py
@@ -93,7 +93,21 @@ def isolate_edit_assets():
 @pytest.fixture
 def dummy_job_runner():
     """Deterministic immediate job runner double for JobManager testing."""
     def _runner(request, accept, token):
-        accept(0.5, "Rendering audio mix and burning subtitles...")
-        return TaskResult(status=TaskStatus.SUCCEEDED, outputs=[Path("output.mp4")])
+        job_id = getattr(request, "job_id", None) or (request.params.get("uuid") if hasattr(request, "params") else None) or "test-job"
+        output_dir = Path(request.params.get("target_dir", ".")) if hasattr(request, "params") else Path(".")
+        accept(TaskEvent(
+            job_id=str(job_id),
+            kind=EventKind.PROGRESS,
+            stage="render",
+            message="Rendering audio mix and burning subtitles...",
+            progress=50.0,
+        ))
+        return TaskResult(
+            job_id=str(job_id),
+            status=TaskStatus.SUCCEEDED,
+            output_dir=output_dir,
+            outputs=(Path("output.mp4"),),
+        )
     return _runner
```

### 4.3 Modification 3: Multi-Tab Node.js Test (`test_headless_node_stage4_screen_render`, Lines 874-905)

```diff
--- a/tests/test_stage4_edit_video.py
+++ b/tests/test_stage4_edit_video.py
@@ -874,13 +874,25 @@ def test_headless_node_stage4_screen_render():
         activeTab: "subtitles"
     };
     state.segments = [
         { id: 1, startSec: 0, endSec: 3.5, targetText: "Node rendered subtitle" }
     ];
 
-    const html = renderStage4EditVideo(state);
+    // Render subtitles tab
+    state.editVideo.activeTab = "subtitles";
+    const htmlSubtitles = renderStage4EditVideo(state);
+
+    // Render audio mix tab
+    state.editVideo.activeTab = "audio";
+    const htmlAudio = renderStage4EditVideo(state);
+
+    // Render thumbnail tab
+    state.editVideo.activeTab = "thumbnail";
+    const htmlThumbnail = renderStage4EditVideo(state);
 
-    if (!html || typeof html !== 'string') {
+    if (!htmlSubtitles || !htmlAudio || !htmlThumbnail) {
         console.error("Render produced non-string output");
         process.exit(1);
     }
 
     const checks = [
-        ['stage4-bgm-preview', html.includes('stage4-bgm-preview')],
-        ['timeline-playhead', html.includes('data-timeline-playhead')],
-        ['timeline-track-video', html.includes('Video') && html.includes('movie')],
-        ['timeline-track-subtitles', html.includes('Subtitles') && html.includes('data-segment-card')],
-        ['timeline-track-dubbed', html.includes('Dubbed')],
-        ['timeline-track-bgm', html.includes('BGM')],
-        ['audio-mix-slider', html.includes('data-mix-slider')],
-        ['thumbnail-input', html.includes('stage4-thumbnail-input')],
-        ['font-size-control', html.includes('Font Size') || html.includes('fontSize')],
-        ['active-subtitle-textarea', html.includes('data-stage4-subtitle')],
+        ['stage4-bgm-preview', htmlSubtitles.includes('stage4-bgm-preview')],
+        ['timeline-playhead', htmlSubtitles.includes('data-timeline-playhead')],
+        ['timeline-track-video', htmlSubtitles.includes('Video') && htmlSubtitles.includes('movie')],
+        ['timeline-track-subtitles', htmlSubtitles.includes('Subtitles') && htmlSubtitles.includes('data-segment-card')],
+        ['timeline-track-dubbed', htmlSubtitles.includes('Dubbed')],
+        ['timeline-track-bgm', htmlSubtitles.includes('BGM')],
+        ['audio-mix-slider', htmlAudio.includes('data-mix-slider')],
+        ['thumbnail-input', htmlThumbnail.includes('stage4-thumbnail-input')],
+        ['font-size-control', htmlSubtitles.includes('Font Size') || htmlSubtitles.includes('fontSize') || htmlSubtitles.includes('update-font-size')],
+        ['active-subtitle-textarea', htmlSubtitles.includes('data-stage4-subtitle')],
     ];
```

---

## 5. Verification Method

Once the changes are applied by the implementer:

1. **Verify Collection and Execution**:
   ```bash
   uv run pytest tests/test_stage4_edit_video.py -v
   ```
   **Acceptance Criteria**:
   - Exit code: 0
   - All 32 test functions (42 parameterized test cases) pass.
   - Zero `ImportError`, zero `TypeError`, and zero unhandled thread exceptions.

2. **Verify Regression Safety**:
   ```bash
   uv run pytest tests/test_stage3_voice_dubbing.py tests/test_webui.py -v
   ```
   **Acceptance Criteria**:
   - All 52 tests pass without regressions.
