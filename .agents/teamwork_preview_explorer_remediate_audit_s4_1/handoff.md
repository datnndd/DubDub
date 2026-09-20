# Handoff Report: Stage 4 Test Suite Import & Fixture Defect Investigation

**Agent Identity**: `explorer_remediate_1` (Teamwork Explorer & Synthesizer)  
**Working Directory**: `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_remediate_audit_s4_1`  
**Milestone**: Stage 4 Redesign (Iteration 2 Remediation)  
**Date**: 2026-09-20  
**Status**: Hard Handoff — Investigation Complete  

---

## 1. Observation

Direct observations and evidence from inspecting the codebase and audit reports:

### 1.1 Collection Crash on Line 72 of `tests/test_stage4_edit_video.py`
In `tests/test_stage4_edit_video.py:72`:
```python
from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus
```
When running `uv run pytest tests/test_stage4_edit_video.py -v`, pytest crashes during collection with:
```text
ImportError while importing test module 'tests\test_stage4_edit_video.py'.
tests\test_stage4_edit_video.py:72: in <module>
    from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus
E   ImportError: cannot import name 'CancellationToken' from 'videotrans.task.job'
```
Inspection of `videotrans/task/job.py` lines 1–247 confirms:
- `job.py` defines GUI thread workers subclassing `BaseWorker(QThread)`: `WorkerPrepare`, `WorkerRegcon`, `WorkerDiariz`, `WorkerTrans`, `WorkerDubb`, `WorkerAlign`, `WorkerRegcon2Pass`, `WorkerAssemb`, `WorkerTaskDone`.
- `job.py` imports `from PySide6.QtCore import QThread`.
- None of `CancellationToken`, `TaskRequest`, `TaskResult`, or `TaskStatus` exist anywhere in `videotrans/task/job.py`.

### 1.2 Canonical Definition of Task Orchestrator Primitives
Inspection of `videotrans/task/orchestrator.py` confirms that all four types (and supporting event types) are defined in `videotrans.task.orchestrator`:
- `videotrans/task/orchestrator.py:20`: `class EventKind(str, Enum)`
- `videotrans/task/orchestrator.py:32`: `class TaskStatus(str, Enum)`
- `videotrans/task/orchestrator.py:38`: `class TaskEvent`
- `videotrans/task/orchestrator.py:58`: `class TaskResult`
- `videotrans/task/orchestrator.py:67`: `class CancellationToken`
- `videotrans/task/orchestrator.py:79`: `class TaskRequest`

`webui.py:25-33` and `tests/test_orchestrator.py:6-11` already import these types directly from `videotrans.task.orchestrator`.

### 1.3 `dummy_job_runner` Signature Incompatibilities
In `tests/test_stage4_edit_video.py:94-99`:
```python
@pytest.fixture
def dummy_job_runner():
    """Deterministic immediate job runner double for JobManager testing."""
    def _runner(request, accept, token):
        accept(0.5, "Rendering audio mix and burning subtitles...")
        return TaskResult(status=TaskStatus.SUCCEEDED, outputs=[Path("output.mp4")])
    return _runner
```
When executed inside `JobManager._execute` (`webui.py:240`):
1. `JobRecord.accept` signature (`webui.py:166`):
   ```python
   def accept(self, event: TaskEvent) -> None:
   ```
   Calling `accept(0.5, "Rendering audio mix and burning subtitles...")` passes 2 arguments, raising:
   `TypeError: JobRecord.accept() takes 2 positional arguments but 3 were given`.
2. `TaskResult` dataclass definition (`videotrans/task/orchestrator.py:58-65`):
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
   `job_id: str` and `output_dir: Path` are positional arguments without default values. Calling `TaskResult(status=TaskStatus.SUCCEEDED, outputs=[Path("output.mp4")])` raises:
   `TypeError: TaskResult.__init__() missing 2 required positional arguments: 'job_id' and 'output_dir'`.

### 1.4 Headless Node Test Tab Boundary Inconsistency
In `tests/test_stage4_edit_video.py:874-898` (`test_headless_node_stage4_screen_render`):
The test sets `state.editVideo.activeTab = "subtitles"` and asserts presence of `['audio-mix-slider', html.includes('data-mix-slider')]`.
In `frontend/js/screens/Stage4EditVideo.js:101-155`, `data-mix-slider` is conditionally rendered only when `activeTab === 'audio'`, causing the test to fail in Node.js with:
`Check failed: audio-mix-slider`.

---

## 2. Logic Chain

1. **Import Defect**:
   - `tests/test_stage4_edit_video.py:72` imports `CancellationToken, TaskRequest, TaskResult, TaskStatus` from `videotrans.task.job`.
   - `videotrans.task.job` does not declare or export these symbols (Observation 1.1).
   - `videotrans.task.orchestrator` declares and exports all of them (Observation 1.2).
   - Changing the import to `from videotrans.task.orchestrator import ...` eliminates the collection crash.

2. **Fixture Signature Defect**:
   - In `JobManager._execute`, `runner` is invoked with `(TaskRequest(params), job.accept, job.token)`.
   - `job.accept` requires an instance of `TaskEvent` (Observation 1.3).
   - `TaskResult` requires `job_id` and `output_dir` (Observation 1.3).
   - Extracting `job_id` and `output_dir` from `request.params` and instantiating `TaskEvent` and `TaskResult` eliminates the daemon thread crashes in `test_create_render_job_resolves_asset_ids`, `test_create_render_job_bypasses_translation_config_check`, `test_api_render_and_export_aliases`, and `test_e2e_stage4_edit_and_render_export_scenario`.

3. **Node Multi-Tab Render Defect**:
   - `Stage4EditVideo.js` inspector is mutually exclusive by tab (`subtitles`, `audio`, `thumbnail`).
   - Testing elements from different tabs requires rendering the screen with each respective `activeTab` value (Observation 1.4).

---

## 3. Caveats

- As an Explorer agent, no code changes were written directly to `tests/test_stage4_edit_video.py` or `webui.py`.
- The companion backend fixes in `webui.py` (safe volume parsing in `build_task_params` lines 564-565, and asset upload guard in `edit_asset_handler` lines 781-808) must be applied concurrently by the implementer so that the full 32-test suite passes.
- Testing on headless environments requires Node.js v18+; if Node is missing, `test_headless_node_stage4_screen_render` skips cleanly via `pytest.skip`.

---

## 4. Conclusion

The test suite defects in `tests/test_stage4_edit_video.py` have been diagnosed with exact AST and runtime traceability.

### Concrete Recommendations for Implementer:

1. **Replace line 72 of `tests/test_stage4_edit_video.py`**:
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

2. **Replace `dummy_job_runner` on lines 94-99 of `tests/test_stage4_edit_video.py`**:
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

3. **Update `test_headless_node_stage4_screen_render` on lines 874-905**:
   Render across `activeTab = "subtitles"`, `activeTab = "audio"`, and `activeTab = "thumbnail"`, checking tab-specific DOM outputs against their matching renders.

Detailed diffs and explanations are published in:
`c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_remediate_audit_s4_1\remediation_plan.md`

---

## 5. Verification Method

To independently verify the recommendations once implemented:

```bash
uv run pytest tests/test_stage4_edit_video.py -v
```
**Expected Outcome**:
- 32 passed, 0 failed, 0 errors, with exit code 0.
- Zero `ImportError` during collection.
- Zero `JobRecord.accept` or `TaskResult` thread exceptions.

To verify existing regressions:
```bash
uv run pytest tests/test_stage3_voice_dubbing.py tests/test_webui.py -v
```
**Expected Outcome**:
- 52 passed in < 5s.
