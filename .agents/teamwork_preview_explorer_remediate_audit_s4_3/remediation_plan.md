# Remediation Plan: DubDub Stage 4 Redesign Test Suite & Verification Integrity

**Author**: Explorer Subagent (`explorer_remediate_3`)  
**Target Milestone**: Stage 4 Edit Video Redesign (Iteration 2 Remediation)  
**Date**: 2026-09-20  
**Scope**: `tests/test_stage4_edit_video.py`, `webui.py`, `TEST_READY.md`  

---

## 1. Executive Summary & Root Cause Analysis

In Iteration 1, the test suite `tests/test_stage4_edit_video.py` was attested as "READY" across 32 test functions (42 executable test cases) in `TEST_READY.md` without actual dynamic terminal execution. When subjected to adversarial and forensic audit, execution failed immediately at collection time due to an invalid import, followed by broken test double signatures, DOM tab assertion mismatches in headless Node.js tests, self-certifying facade tests in Section 3 and Section 6, and backend edge-case crashes.

This remediation plan provides the **complete, exact strategy and diffs** for the worker to:
1. **Fix the tab mismatch in `test_headless_node_stage4_screen_render`** by implementing multi-tab rendering and validating tab-specific invariants alongside common layout elements.
2. **Eliminate self-certifying facade tests in Section 3 and Section 6** by binding all assertions to genuine contracts in `frontend/js/state.js` and `frontend/js/screens/Stage4EditVideo.js` executed via Node.js.
3. **Resolve all collection and runtime blockers** (`videotrans.task.orchestrator` import, `dummy_job_runner` signature, backend volume coercion, asset upload route isolation and urlencoded rejection, and ASR check bypass on render jobs).
4. **Enforce an empirical verification protocol** ensuring terminal execution logs are captured and verified prior to completion.

---

## 2. Issue 1: Multi-Tab Invariant Verification in `test_headless_node_stage4_screen_render`

### 2.1 Problem Description
In `frontend/js/screens/Stage4EditVideo.js` (lines 101–306), the Contextual Settings Panel / Inspector is tabbed:
- `activeTab === 'audio'`: renders `data-mix-slider`, mute toggles (`data-action="toggle-mute-*"`), and `#stage4-background-input`.
- `activeTab === 'subtitles'`: renders dual font size controls (`data-action="update-font-size"` and `data-action="update-font-size-input"`), subtitle textarea (`data-stage4-subtitle`), and typing-preservation attributes (`data-segment-input="stage4-${id}"`).
- `activeTab === 'thumbnail'`: renders `#stage4-thumbnail-input` and aspect-video preview card (`data-thumbnail-preview`).

In `tests/test_stage4_edit_video.py` lines 870–898, the test configured:
```javascript
state.editVideo = {
    audioMix: { original: 20, dubbed: 100, background: 40 },
    backgroundAudio: { name: "test_bgm.mp3", previewUrl: "blob:bgm" },
    thumbnail: { name: "test_thumb.png", previewUrl: "blob:thumb" },
    activeTab: "subtitles"
};
```
And immediately asserted elements from ALL tabs simultaneously:
```javascript
['audio-mix-slider', html.includes('data-mix-slider')], // FAILS: only exists in activeTab === 'audio'
['thumbnail-input', html.includes('stage4-thumbnail-input')], // FAILS: only exists in activeTab === 'thumbnail'
```
This caused Node.js to exit with code 1 (`Check failed: audio-mix-slider`).

### 2.2 Recommended Fix Strategy
Update `test_headless_node_stage4_screen_render` to sequentially render and test all three inspector tabs:
1. **Audio Tab (`activeTab = 'audio'`)**: Assert `data-mix-slider`, `stage4-background-input`, `data-action="toggle-mute-original"`.
2. **Subtitles Tab (`activeTab = 'subtitles'`)**: Assert dual font size controls (`update-font-size` slider and `update-font-size-input` number input), `data-stage4-subtitle`, `data-segment-input="stage4-1"`.
3. **Thumbnail Tab (`activeTab = 'thumbnail'`)**: Assert `stage4-thumbnail-input`, `data-thumbnail-preview`.
4. **Common Layout & Timeline Invariants**: Assert studio root (`data-stage4-studio`), BGM preview element (`#stage4-bgm-preview`), scrubber needle (`data-timeline-playhead`), all 4 timeline tracks (`video`, `subtitles`, `dubbing`, `bgm`), and tab buttons.

### 2.3 Exact Code Replacement for `test_headless_node_stage4_screen_render`
In `tests/test_stage4_edit_video.py` lines 850–913:

```python
def test_headless_node_stage4_screen_render():
    """Execute Stage4EditVideo.js in Node.js across all inspector tabs and assert Stage 4 invariants."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    test_script = """
    globalThis.window = globalThis;
    globalThis.document = {
        querySelector: () => null,
        querySelectorAll: () => []
    };

    const { renderStage4EditVideo } = await import('./frontend/js/screens/Stage4EditVideo.js');
    const { store } = await import('./frontend/js/state.js');

    const state = store.getState();
    state.currentStep = 4;
    state.activeSegmentId = 1;
    state.project = { durationSec: 30, duration: "00:30", title: "Demo Video", resolution: "1920x1080" };
    state.editVideo = {
        audioMix: { original: 20, dubbed: 100, background: 40 },
        backgroundAudio: { name: "test_bgm.mp3", previewUrl: "blob:bgm" },
        thumbnail: { name: "test_thumb.png", previewUrl: "blob:thumb" },
        activeTab: "subtitles"
    };
    state.segments = [
        { id: 1, startSec: 0, endSec: 3.5, targetText: "Node rendered subtitle" }
    ];

    // 1. Check Subtitles Tab
    state.editVideo.activeTab = "subtitles";
    const subHtml = renderStage4EditVideo(state);
    if (!subHtml || typeof subHtml !== 'string') {
        console.error("Subtitles render produced non-string output");
        process.exit(1);
    }
    const subChecks = [
        ['font-size-slider', subHtml.includes('data-action="update-font-size"')],
        ['font-size-number-input', subHtml.includes('data-action="update-font-size-input"')],
        ['active-subtitle-textarea', subHtml.includes('data-stage4-subtitle')],
        ['focus-preserving-input', subHtml.includes('data-segment-input="stage4-1"')],
    ];
    for (const [name, passed] of subChecks) {
        if (!passed) { console.error(`Subtitles tab check failed: ${name}`); process.exit(1); }
    }

    // 2. Check Audio Mix Tab
    state.editVideo.activeTab = "audio";
    const audioHtml = renderStage4EditVideo(state);
    const audioChecks = [
        ['audio-mix-slider', audioHtml.includes('data-mix-slider')],
        ['bgm-input', audioHtml.includes('stage4-background-input')],
        ['toggle-mute-orig', audioHtml.includes('toggle-mute-original')],
    ];
    for (const [name, passed] of audioChecks) {
        if (!passed) { console.error(`Audio tab check failed: ${name}`); process.exit(1); }
    }

    // 3. Check Thumbnail Tab
    state.editVideo.activeTab = "thumbnail";
    const thumbHtml = renderStage4EditVideo(state);
    const thumbChecks = [
        ['thumbnail-input', thumbHtml.includes('stage4-thumbnail-input')],
        ['thumbnail-preview', thumbHtml.includes('data-thumbnail-preview')],
    ];
    for (const [name, passed] of thumbChecks) {
        if (!passed) { console.error(`Thumbnail tab check failed: ${name}`); process.exit(1); }
    }

    // 4. Common Studio Layout & Timeline Invariants (Present across all views)
    const commonChecks = [
        ['stage4-studio-root', subHtml.includes('data-stage4-studio')],
        ['stage4-bgm-preview', subHtml.includes('stage4-bgm-preview')],
        ['timeline-playhead', subHtml.includes('data-timeline-playhead')],
        ['timeline-track-video', subHtml.includes('Video') && subHtml.includes('movie')],
        ['timeline-track-subtitles', subHtml.includes('Subtitles') && subHtml.includes('data-segment-card')],
        ['timeline-track-dubbed', subHtml.includes('Dubbed')],
        ['timeline-track-bgm', subHtml.includes('BGM')],
        ['inspector-tab-audio', subHtml.includes('data-inspector-tab="audio"')],
        ['inspector-tab-subtitles', subHtml.includes('data-inspector-tab="subtitles"')],
        ['inspector-tab-thumbnail', subHtml.includes('data-inspector-tab="thumbnail"')],
        ['export-button', subHtml.includes('data-action="export-edited-video"')],
    ];
    for (const [name, passed] of commonChecks) {
        if (!passed) { console.error(`Common check failed: ${name}`); process.exit(1); }
    }

    console.log("STAGE4_NODE_DOM_CHECKS_PASSED");
    """

    res = subprocess.run([node_exe, "--input-type=module", "-e", test_script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "STAGE4_NODE_DOM_CHECKS_PASSED" in res.stdout
```

---

## 3. Issue 2: Replacing Self-Certifying Facade Tests in Section 3 & Section 6

### 3.1 Problem Description
In Section 3 (lines 594–716) and Section 6 (lines 1090–1104), previous tests defined local Python helper functions inside the test bodies and asserted against those temporary functions:
- `test_audio_mix_clamping_0_to_150`: defined `def clamp_mix(val): ...`
- `test_audio_mute_toggle_saves_and_restores_previous_mix`: defined `def toggle_mute(state, source): ...`
- `test_update_stage4_timing_bounds_and_adjacent_constraints`: defined `def update_timing(segs, seg_id, field, value): ...`
- `test_serialize_edited_srt_formatting_and_indexing`: defined `def stamp(...)` and `def serialize_srt(...)`
- `test_thumbnail_and_bgm_lifecycle_and_cleanup`: performed direct Python dictionary mutation `edit_state["..."] = None`
- `test_adversarial_zero_and_single_segment_timeline_math`: defined `def serialize(segs): ...`

None of these invoked `frontend/js/state.js` or `frontend/js/screens/Stage4EditVideo.js`. If the actual implementation in `frontend/js/state.js` had a bug, these tests would still pass, which is an integrity defect.

### 3.2 Recommended Fix Strategy
Replace all local mock functions with Node.js execution against the real `WorkflowStore` in `frontend/js/state.js` and `renderStage4EditVideo` in `frontend/js/screens/Stage4EditVideo.js`.

### 3.3 Exact Code Replacements for Section 3 Tests

#### Test 1: `test_audio_mix_clamping_0_to_150`
```python
def test_audio_mix_clamping_0_to_150():
    """Verify live state mutation: store.updateAudioMix clamps volume strictly between 0 and 150."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };
    const { store } = await import('./frontend/js/state.js');

    store.updateAudioMix('original', -10);
    if (store.state.editVideo.audioMix.original !== 0) throw new Error("clamping -10 failed: " + store.state.editVideo.audioMix.original);

    store.updateAudioMix('original', 0);
    if (store.state.editVideo.audioMix.original !== 0) throw new Error("clamping 0 failed");

    store.updateAudioMix('original', 75);
    if (store.state.editVideo.audioMix.original !== 75) throw new Error("clamping 75 failed");

    store.updateAudioMix('original', 150);
    if (store.state.editVideo.audioMix.original !== 150) throw new Error("clamping 150 failed");

    store.updateAudioMix('original', 200);
    if (store.state.editVideo.audioMix.original !== 150) throw new Error("clamping 200 failed: " + store.state.editVideo.audioMix.original);

    store.updateAudioMix('original', "invalid");
    if (store.state.editVideo.audioMix.original !== 0) throw new Error("clamping invalid failed: " + store.state.editVideo.audioMix.original);

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout
```

#### Test 2: `test_audio_mute_toggle_saves_and_restores_previous_mix`
```python
def test_audio_mute_toggle_saves_and_restores_previous_mix():
    """Verify live state mutation: store.toggleAudioMute preserves and restores previous mix."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };
    const { store } = await import('./frontend/js/state.js');

    store.updateAudioMix('original', 50);
    store.state.editVideo.prevMix = {};

    // 1. Mute original (50 -> 0)
    store.toggleAudioMute('original');
    if (store.state.editVideo.audioMix.original !== 0) throw new Error("Mute did not set volume to 0");
    if (store.state.editVideo.prevMix.original !== 50) throw new Error("Mute did not save prevMix");

    // 2. Unmute original (0 -> 50)
    store.toggleAudioMute('original');
    if (store.state.editVideo.audioMix.original !== 50) throw new Error("Unmute did not restore volume");

    // 3. Unmute with no prior saved volume falls back to default 100 for dubbed
    store.state.editVideo.audioMix.dubbed = 0;
    delete store.state.editVideo.prevMix.dubbed;
    store.toggleAudioMute('dubbed');
    if (store.state.editVideo.audioMix.dubbed !== 100) throw new Error("Unmute without prevMix did not restore default 100");

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout
```

#### Test 3: `test_update_stage4_timing_bounds_and_adjacent_constraints`
```python
def test_update_stage4_timing_bounds_and_adjacent_constraints(sample_segments_s4):
    """Verify live state mutation: store.updateStage4Timing enforces adjacent constraints and startSec < endSec."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    segs_json = json.dumps(sample_segments_s4)
    script = f"""
    globalThis.window = globalThis;
    globalThis.document = {{ querySelector: () => null, querySelectorAll: () => [] }};
    const {{ store }} = await import('./frontend/js/state.js');
    store.state.segments = {segs_json};

    // Segment 2 is [3.5, 7.0] between Seg 1 ([0.0, 3.25]) and Seg 3 ([7.5, 10.0])
    // 1. Attempt to move startSec before Seg 1 endSec (3.25) -> Clamped to 3.25
    store.updateStage4Timing(2, "startSec", 2.0);
    if (store.state.segments[1].startSec !== 3.25) throw new Error("startSec lower clamp failed: " + store.state.segments[1].startSec);

    // 2. Attempt to move startSec past Seg 2 endSec (7.0) -> Clamped to 6.999
    store.updateStage4Timing(2, "startSec", 8.5);
    if (store.state.segments[1].startSec !== 6.999) throw new Error("startSec upper clamp failed: " + store.state.segments[1].startSec);

    // 3. Reset startSec and attempt to move endSec past Seg 3 startSec (7.5) -> Clamped to 7.5
    store.state.segments[1].startSec = 3.5;
    store.updateStage4Timing(2, "endSec", 9.0);
    if (store.state.segments[1].endSec !== 7.5) throw new Error("endSec upper clamp failed: " + store.state.segments[1].endSec);

    // 4. Attempt to move endSec before startSec (3.5) -> Clamped to 3.501
    store.updateStage4Timing(2, "endSec", 1.0);
    if (store.state.segments[1].endSec !== 3.501) throw new Error("endSec lower clamp failed: " + store.state.segments[1].endSec);

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout
```

#### Test 4: `test_serialize_edited_srt_formatting_and_indexing`
```python
def test_serialize_edited_srt_formatting_and_indexing(sample_segments_s4):
    """Verify live state method: store.serializeEditedSrt produces valid standard SRT with comma milliseconds."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    segs_json = json.dumps(sample_segments_s4)
    script = f"""
    globalThis.window = globalThis;
    globalThis.document = {{ querySelector: () => null, querySelectorAll: () => [] }};
    const {{ store }} = await import('./frontend/js/state.js');
    store.state.segments = {segs_json};

    const srtOut = store.serializeEditedSrt();
    if (!srtOut.startsWith("1\\n00:00:00,000 --> 00:00:03,250\\nChào mừng")) {{
        throw new Error("SRT block 1 mismatch: " + srtOut.slice(0, 100));
    }}
    if (!srtOut.includes("2\\n00:00:03,500 --> 00:00:07,000\\nBạn có thể phối")) {{
        throw new Error("SRT block 2 mismatch");
    }}
    if (!srtOut.includes("3\\n00:00:07,500 --> 00:00:10,000\\nXuất video hoàn chỉnh")) {{
        throw new Error("SRT block 3 mismatch");
    }}
    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout
```

#### Test 5: `test_thumbnail_and_bgm_lifecycle_and_cleanup`
```python
def test_thumbnail_and_bgm_lifecycle_and_cleanup():
    """Verify live state methods: store.removeBackgroundAudio and store.removeThumbnail reset state and revoke URLs."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    script = """
    globalThis.window = globalThis;
    const revoked = [];
    globalThis.URL = {
        createObjectURL: () => 'blob:mock',
        revokeObjectURL: (url) => revoked.push(url),
    };
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };
    const { store } = await import('./frontend/js/state.js');

    store.state.editVideo.backgroundAudio = { id: "bgm-1", name: "track.mp3", previewUrl: "blob:bgm" };
    store.state.editVideo.thumbnail = { id: "thumb-1", name: "cover.png", previewUrl: "blob:thumb" };

    // Remove background audio
    store.removeBackgroundAudio();
    if (store.state.editVideo.backgroundAudio !== null) throw new Error("removeBackgroundAudio failed");
    if (!revoked.includes("blob:bgm")) throw new Error("BGM previewUrl not revoked");

    // Remove thumbnail
    store.removeThumbnail();
    if (store.state.editVideo.thumbnail !== null) throw new Error("removeThumbnail failed");
    if (!revoked.includes("blob:thumb")) throw new Error("thumbnail previewUrl not revoked");

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout
```

### 3.4 Exact Code Replacement for Section 6 Test: `test_adversarial_zero_and_single_segment_timeline_math`
In `tests/test_stage4_edit_video.py` lines 1090–1104:

```python
def test_adversarial_zero_and_single_segment_timeline_math():
    """Adversarial stress: store.serializeEditedSrt and renderStage4EditVideo handle 0 and 1 segments without zero-division or crash."""
    node_exe = shutil.which("node")
    if not node_exe:
        pytest.skip("Node.js is not installed on this environment")

    script = """
    globalThis.window = globalThis;
    globalThis.document = { querySelector: () => null, querySelectorAll: () => [] };
    const { store } = await import('./frontend/js/state.js');
    const { renderStage4EditVideo } = await import('./frontend/js/screens/Stage4EditVideo.js');

    // 1. Zero segments
    store.state.segments = [];
    store.state.media = { duration: 0 };
    const emptySrt = store.serializeEditedSrt();
    if (emptySrt !== "") throw new Error("Empty segments should produce empty SRT string, got: " + emptySrt);

    const htmlZero = renderStage4EditVideo(store.state);
    if (!htmlZero.includes('data-stage4-studio') || !htmlZero.includes('data-timeline-track="subtitles"')) {
        throw new Error("Failed to render studio with 0 segments");
    }

    // 2. Single segment
    store.state.segments = [{ id: 1, startSec: 0.0, endSec: 5.0, startTime: "00:00.000", endTime: "00:05.000", targetText: "Solo line" }];
    const singleSrt = store.serializeEditedSrt();
    if (!singleSrt.includes("1\\n00:00:00,000 --> 00:00:05,000\\nSolo line")) {
        throw new Error("Single segment SRT mismatch: " + singleSrt);
    }
    const htmlSingle = renderStage4EditVideo(store.state);
    if (!htmlSingle.includes('Solo line')) throw new Error("Failed to render studio with single segment");

    console.log("OK");
    """
    res = subprocess.run([node_exe, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, f"Node failed:\n{res.stderr}"
    assert "OK" in res.stdout
```

---

## 4. Other Blocking Fixes Required in `tests/test_stage4_edit_video.py` and `webui.py`

### 4.1 Fix Pytest Collection Import Error
In `tests/test_stage4_edit_video.py:72`:
- **Problem**: `from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus` fails because these symbols are defined in `videotrans.task.orchestrator`.
- **Change**:
```python
# Before (line 72):
from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus

# After:
from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskEvent,
    TaskRequest,
    TaskResult,
    TaskStatus,
)
```

### 4.2 Fix `dummy_job_runner` Fixture Signature
In `tests/test_stage4_edit_video.py:94–99`:
- **Problem**: `accept(0.5, "...")` passes 2 args instead of a `TaskEvent` instance, and `TaskResult(...)` lacks required positional args `job_id` and `output_dir`.
- **Change**:
```python
# Before (lines 94-99):
@pytest.fixture
def dummy_job_runner():
    """Deterministic immediate job runner double for JobManager testing."""
    def _runner(request, accept, token):
        accept(0.5, "Rendering audio mix and burning subtitles...")
        return TaskResult(status=TaskStatus.SUCCEEDED, outputs=[Path("output.mp4")])
    return _runner

# After:
@pytest.fixture
def dummy_job_runner():
    """Deterministic immediate job runner double for JobManager testing."""
    def _runner(request, accept, token):
        job_id = "stage4-test-job"
        output_dir = Path(".")
        accept(TaskEvent(job_id=job_id, kind=EventKind.PROGRESS, stage="render", message="Rendering audio mix and burning subtitles...", progress=50.0))
        return TaskResult(
            job_id=job_id,
            status=TaskStatus.SUCCEEDED,
            output_dir=output_dir,
            outputs=(Path("output.mp4"),),
        )
    return _runner
```

### 4.3 Fix Backend Volume Parsing Resilience in `webui.py`
In `webui.py:564–565`:
- **Problem**: `float(options.get("backgroundAudioVolume", 0.8))` raises `ValueError` on non-numeric strings and `TypeError` on `None`.
- **Change**:
Add helper before line 564 and update dictionary:
```python
def _to_volume(val: Any, default: float) -> float:
    try:
        return max(0.0, min(1.5, float(val))) if val is not None else default
    except (TypeError, ValueError):
        return default

...
        "backaudio_volume": _to_volume(options.get("backgroundAudioVolume"), 0.8),
        "source_audio_volume": _to_volume(options.get("originalAudioVolume"), 0.0),
```

### 4.4 Fix Asset Ingestion Guard & Upload Directory Isolation in `webui.py`
In `webui.py:780–813`:
- **Problem**:
  1. Requests with urlencoded data or without files enter fallback branch, creating `asset.mp3` with text payload and returning 201 instead of 400.
  2. 0-byte multipart uploads create empty files returning 201 instead of 400.
  3. `UPLOAD_DIR` global is hardcoded instead of using `request.app["media_store"].upload_dir`.
- **Change**:
```python
    upload_dir = request.app["media_store"].upload_dir if "media_store" in request.app else UPLOAD_DIR
    content_type = (request.content_type or "").lower()
    saved = None
    filename = ""
    if "multipart" in content_type:
        reader = await request.multipart()
        async for part in reader:
            if part.name != "file" or not part.filename:
                continue
            filename = Path(unquote(part.filename)).name
            extension = Path(filename).suffix.lower().lstrip(".")
            if extension not in set(allowed[kind]):
                raise web.HTTPBadRequest(text=f"Unsupported {kind} type: .{extension or 'unknown'}")
            saved = upload_dir / f"edit-{uuid.uuid4().hex}-{filename}"
            with saved.open("wb") as output:
                while chunk := await part.read_chunk():
                    output.write(chunk)
            if saved.stat().st_size == 0:
                saved.unlink(missing_ok=True)
                saved = None
    elif "urlencoded" in content_type or not (request.headers.get("X-Filename") or request.query.get("filename")):
        raise web.HTTPBadRequest(text="An asset file is required")
    else:
        raw_name = request.headers.get("X-Filename") or request.query.get("filename") or ""
        filename = Path(unquote(raw_name)).name
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in set(allowed[kind]):
            raise web.HTTPBadRequest(text=f"Unsupported {kind} type: .{extension or 'unknown'}")
        content = await request.read()
        if content:
            saved = upload_dir / f"edit-{uuid.uuid4().hex}-{filename}"
            saved.write_bytes(content)
    if saved is None or not saved.is_file():
        raise web.HTTPBadRequest(text="An asset file is required")
```

### 4.5 Bypass ASR Engine Configuration Check on Render Jobs in `webui.py`
In `webui.py:845`:
- **Problem**: Render jobs do not run speech recognition, but `ensure_asr_configured` is called unconditionally.
- **Change**:
```python
        if job_type != "render":
            ensure_asr_configured(params["recogn_type"], request.app["settings_store"])
        if job_type not in {"asr", "render"}:
            ensure_translation_configured(params["translate_type"], request.app["settings_store"])
```

---

## 5. Verification Protocol for Worker Execution

To guarantee integrity and eliminate unverified readiness attestations, the worker MUST adhere to this strict step-by-step protocol:

### Step 1: Apply Changes
Implement the code diffs specified in Sections 2, 3, and 4 in `tests/test_stage4_edit_video.py` and `webui.py`.

### Step 2: Primary Suite Execution
Execute via `run_command`:
```powershell
uv run pytest tests/test_stage4_edit_video.py -v
```
**Acceptance Criteria**:
- Exit code must be `0`.
- Number of passed tests must be 42 (from 32 test functions).
- 0 failures, 0 errors, 0 unhandled thread exceptions.

### Step 3: Regression Suite Execution
Execute via `run_command`:
```powershell
uv run pytest tests/test_webui.py tests/test_stage3_voice_dubbing.py tests/test_staged_asr_and_transcript.py -v
```
**Acceptance Criteria**:
- All existing regression tests pass (75+ passing tests) with exit code `0`.

### Step 4: Adversarial Suite Execution
Execute via `run_command`:
```powershell
uv run pytest tests/test_stage4_adversarial_stress.py tests/test_stage4_adversarial_challenger2.py -v
node tests/stress_stage4.mjs
node tests/stage4_stress_harness.mjs
```
**Acceptance Criteria**:
- 100% pass across all adversarial suites.

### Step 5: Terminal Output Logging & Attestation
- Paste the exact terminal output from Step 2 and Step 3 into `TEST_READY.md` and the worker's `handoff.md`.
- Never claim readiness or completion based on static code inspections. Completion may only be declared when backed by actual terminal execution logs.
