# Backend Remediation Plan: DubDub AI Video Dubbing Studio (Stage 4)

**Document Type**: Technical Investigation & Remediation Architecture  
**Author**: `explorer_remediate_2` (Explorer Subagent)  
**Target Component**: Backend API & Request Handlers (`webui.py`)  
**Associated Verification Suite**: `tests/test_stage4_edit_video.py`  
**Date**: 2026-09-20  
**Status**: Ready for Implementation  

---

## 1. Executive Summary

During the Stage 4 Redesign ("Edit Video") audit and review cycle, multiple backend vulnerabilities and structural defects were identified across `webui.py`. These defects break automated test execution, create production reliability risks (unhandled HTTP 500 crashes upon invalid or edge-case client input), bypass dependency injection / filesystem isolation, and allow malformed form submissions to register as pseudo-assets.

This remediation plan provides an exhaustive forensic analysis, exact architectural solutions, behavioral matrices, and precise drop-in code diffs for all four core issues identified in the user mission, as well as necessary complementary safeguards.

### Summary of Targeted Issues
1. **Issue 1: Unsafe Volume Coercion in `build_task_params` (`webui.py:564-565`)**  
   Calling `float(options.get(...))` directly causes uncaught `TypeError` when values are `None` and `ValueError` when values are non-numeric strings (`"not-a-number"`), empty strings, or booleans. Infinite values also trigger `OverflowError` in dubbed volume calculation.
2. **Issue 2: URL-Encoded Form Ingestion Vulnerability in `edit_asset_handler` (`webui.py:781-808`)**  
   Non-multipart requests (such as standard `application/x-www-form-urlencoded` POSTs with no file) default to inventing a filename (`asset.mp3` or `asset.png`), save arbitrary text body bytes to disk, and return HTTP 201 Created instead of HTTP 400 Bad Request. Furthermore, 0-byte multipart files are registered into `EDIT_ASSETS`.
3. **Issue 3: Erroneous ASR Credential Enforcement on Render Tasks (`webui.py:845`)**  
   `create_job_handler` unconditionally executes `ensure_asr_configured` for all job submissions. Because Stage 4 render jobs only mix audio and burn subtitles without performing speech recognition, requiring third-party ASR credentials (e.g. Deepgram API keys) causes render jobs to fail unnecessarily.
4. **Issue 4: Upload Directory Encapsulation & Test Isolation Leakage (`webui.py:790, 806`)**  
   `edit_asset_handler` hardcodes the module-global `UPLOAD_DIR` (`TEMP_DIR / "webui_uploads"`), bypassing `request.app["media_store"].upload_dir`. This pollutes global temporary storage and defeats filesystem isolation when tests inject temporary directories via `create_app(upload_dir=...)`.

---

## 2. Deep Dive: Issue 1 — Safe Volume Parameter Parsing

### 2.1 Vulnerability Mechanism & Root Cause
In `webui.py:564-565`:
```python
"backaudio_volume": max(0.0, min(1.5, float(options.get("backgroundAudioVolume", 0.8)))),
"source_audio_volume": max(0.0, min(1.5, float(options.get("originalAudioVolume", 0.0)))),
```
The python dictionary method `options.get(key, default)` returns the dictionary's value when the key exists. Therefore:
1. **`None` Value**: When a client payload contains `"originalAudioVolume": null` (or `None` in Python), `options.get("originalAudioVolume", 0.0)` evaluates to `None`. Then `float(None)` raises:
   ```text
   TypeError: float() argument must be a string or a real number, not 'NoneType'
   ```
2. **Non-numeric String**: When a client payload contains `"backgroundAudioVolume": "not-a-number"` or `""` (empty string), `options.get(...)` returns the string. Calling `float("not-a-number")` raises:
   ```text
   ValueError: could not convert string to float: 'not-a-number'
   ```
3. **Boolean Values**: In Python, `isinstance(True, int)` is `True` and `float(True)` is `1.0`. Booleans in JSON should not inadvertently set volume to 100% or 0% without validation.
4. **`NaN` Floating Point**: If a client sends `"NaN"` or `float('nan')`, `min(1.5, float('nan'))` evaluates to `nan`, contaminating downstream audio mixing filters.
5. **Dubbed Volume Infinite Overflow**: In `webui.py:528-530`:
   ```python
   raw_vol = options.get("volume")
   if isinstance(raw_vol, (int, float)) and not isinstance(raw_vol, bool):
       diff = int(round((float(raw_vol) - 1.0) * 100))
   ```
   If `raw_vol` is `float('inf')` or `1e309`, `round(...)` raises `OverflowError: cannot convert float infinity to integer`.

Because `create_job_handler` only catches `ActiveJobError` and `ValueError`, uncaught `TypeError` and `OverflowError` bubble up to `aiohttp` as unhandled HTTP 500 Internal Server Errors.

### 2.2 Architectural Solution: Dedicated `_safe_volume` Helper
Define a robust, type-safe helper function in `webui.py` that coerces any incoming volume parameter into a validated float within `[0.0, 1.5]`, gracefully falling back to a caller-specified default:

```python
def _safe_volume(value: Any, default: float) -> float:
    """Safely coerce a volume parameter to a float clamped within [0.0, 1.5].
    
    Falls back to `default` if the value is None, boolean, non-numeric, NaN,
    or cannot be converted. Clamps finite values strictly to 0.0 <= v <= 1.5.
    """
    if value is None or isinstance(value, bool):
        return default
    try:
        val = float(value)
        if math.isnan(val):
            return default
        return max(0.0, min(1.5, val))
    except (TypeError, ValueError, OverflowError):
        return default
```

### 2.3 Input-Output Specification Matrix

| Raw Input (`value`) | Default | Parsed Output | Rationale |
|---|---|---|---|
| `None` | `0.8` | `0.8` | Fallback to default on null |
| `None` | `0.0` | `0.0` | Fallback to default on null |
| `""` (empty string) | `0.8` | `0.8` | Fallback on empty string |
| `"not-a-number"` | `0.8` | `0.8` | Fallback on unparseable string |
| `True` / `False` | `0.8` | `0.8` | Reject boolean types |
| `float('nan')` / `"NaN"` | `0.8` | `0.8` | Reject NaN |
| `0.35` (float) | `0.8` | `0.35` | Normal in-range float preserved |
| `"0.35"` (string) | `0.8` | `0.35` | Valid string float coerced |
| `-50` / `-0.01` | `0.8` | `0.0` | Clamped to lower boundary `0.0` |
| `200` / `99999` | `0.8` | `1.5` | Clamped to upper boundary `1.5` |
| `float('inf')` / `1e309` | `0.8` | `1.5` | Infinity clamped to max `1.5` |
| `float('-inf')` | `0.8` | `0.0` | Negative infinity clamped to min `0.0` |

### 2.4 Hardening Dubbed Voice Volume (`volume`)
In `webui.py:528-538`, wrap the round operation in a `try...except (OverflowError, ValueError)` guard:
```python
    raw_vol = options.get("volume")
    if isinstance(raw_vol, (int, float)) and not isinstance(raw_vol, bool):
        try:
            diff = int(round((float(raw_vol) - 1.0) * 100))
            norm_volume = f"{diff:+d}%"
        except (OverflowError, ValueError):
            norm_volume = "+0%"
    elif raw_vol is not None and str(raw_vol).strip():
        s = str(raw_vol).strip()
        if re.match(r'^[+-]?\d+(\.\d+)?%$', s):
            norm_volume = s if s.startswith(("+", "-")) else f"+{s}"
        else:
            norm_volume = s
    else:
        norm_volume = "+0%"
```

---

## 3. Deep Dive: Issue 2 — Strict Form & Binary Ingestion Validation

### 3.1 Vulnerability Mechanism & Root Cause
In `webui.py:781-808`:
```python
    if request.content_type and "multipart" in request.content_type.lower():
        reader = await request.multipart()
        ...
    else:
        raw_name = request.headers.get("X-Filename") or request.query.get("filename") or ""
        if raw_name:
            filename = Path(unquote(raw_name)).name
        else:
            default_ext = "mp3" if kind == "background-audio" else "png"
            filename = f"asset.{default_ext}"
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in set(allowed[kind]):
            raise web.HTTPBadRequest(text=f"Unsupported {kind} type: .{extension or 'unknown'}")
        content = await request.read()
        if content:
            saved = UPLOAD_DIR / f"edit-{uuid.uuid4().hex}-{filename}"
            saved.write_bytes(content)
    if saved is None or not saved.is_file():
        raise web.HTTPBadRequest(text="An asset file is required")
```

When an automated client or malicious user sends:
```python
form = aiohttp.FormData()
form.add_field("otherField", "test")
res = await client.post("/api/assets/background-audio", data=form)
```
1. `aiohttp.FormData` encodes requests without file fields as `Content-Type: application/x-www-form-urlencoded`.
2. The condition `"multipart" in request.content_type.lower()` evaluates to `False`.
3. Execution drops into the `else:` branch.
4. Because `raw_name` is empty, the code executes `filename = "asset.mp3"`.
5. `extension = "mp3"`, which passes `allowed["background-audio"]`.
6. `content = await request.read()` reads `b"otherField=test"`.
7. `if content:` is `True`. The handler writes the urlencoded string bytes into `asset.mp3`, registers the fake asset in `EDIT_ASSETS`, and returns **HTTP 201 Created**!
8. Furthermore, in multipart uploads, uploading an empty 0-byte file (`b""`) writes a 0-byte file to disk. `saved.is_file()` returns `True`, registering corrupt 0-byte files that break downstream FFmpeg invocations.

### 3.2 Architectural Solution: Strict Validation Architecture
To completely resolve this vulnerability:
1. **Explicitly Reject URL-Encoded Forms**: Check `content_type`. If `application/x-www-form-urlencoded` is present, immediately reject with `HTTP 400 Bad Request`.
2. **Require Filename Identifier for Raw Binary Uploads**: For non-multipart requests, mandate either an `X-Filename` header or a `?filename=` query parameter. Do NOT fabricate default filenames like `asset.mp3`.
3. **Validate Non-Empty Content**: Verify that `content` contains at least 1 byte of data.
4. **Post-Write Size Verification**: Ensure `saved.stat().st_size > 0`. If a 0-byte file is created (e.g. from a 0-byte multipart file part), unlink the empty file from disk and raise `HTTP 400 Bad Request`.

### 3.3 Target Handler Logic
```python
async def edit_asset_handler(request: web.Request) -> web.Response:
    kind = request.match_info["kind"]
    allowed = {
        "background-audio": AUDIO_EXITS,
        "thumbnail": {"png", "jpg", "jpeg", "webp"},
    }
    if kind not in allowed:
        raise web.HTTPNotFound(text="Unknown edit asset type")
    saved: Path | None = None
    filename = ""
    store: MediaStore = request.app["media_store"]

    content_type = (request.content_type or "").lower()
    if "x-www-form-urlencoded" in content_type:
        raise web.HTTPBadRequest(text="An asset file is required")

    if "multipart" in content_type:
        reader = await request.multipart()
        async for part in reader:
            if part.name != "file" or not part.filename:
                continue
            filename = Path(unquote(part.filename)).name
            extension = Path(filename).suffix.lower().lstrip(".")
            if extension not in set(allowed[kind]):
                raise web.HTTPBadRequest(text=f"Unsupported {kind} type: .{extension or 'unknown'}")
            saved = store.upload_dir / f"edit-{uuid.uuid4().hex}-{filename}"
            with saved.open("wb") as output:
                while chunk := await part.read_chunk():
                    output.write(chunk)
    else:
        raw_name = request.headers.get("X-Filename") or request.query.get("filename") or ""
        if not raw_name:
            raise web.HTTPBadRequest(text="An asset file is required")
        filename = Path(unquote(raw_name)).name
        if not filename:
            raise web.HTTPBadRequest(text="A valid filename is required")
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in set(allowed[kind]):
            raise web.HTTPBadRequest(text=f"Unsupported {kind} type: .{extension or 'unknown'}")
        content = await request.read()
        if not content:
            raise web.HTTPBadRequest(text="An asset file is required")
        saved = store.upload_dir / f"edit-{uuid.uuid4().hex}-{filename}"
        saved.write_bytes(content)

    if saved is None or not saved.is_file() or saved.stat().st_size == 0:
        if saved and saved.is_file():
            saved.unlink(missing_ok=True)
        raise web.HTTPBadRequest(text="An asset file is required")

    asset_id = uuid.uuid4().hex
    with EDIT_ASSETS_LOCK:
        EDIT_ASSETS[asset_id] = saved
    return web.json_response({"id": asset_id, "name": filename}, status=201)
```

---

## 4. Deep Dive: Issue 3 — Decoupling ASR & Translation Configuration from Render Tasks

### 4.1 Vulnerability Mechanism & Architectural Conflict
In `webui.py:844-847`:
```python
params = build_task_params(media.path, options, job_type=job_type)
ensure_asr_configured(params["recogn_type"], request.app["settings_store"])
if job_type not in {"asr", "render"}:
    ensure_translation_configured(params["translate_type"], request.app["settings_store"])
```
And in `orchestrator.py:169-180`:
```python
if task.cfg.subtitles:
    task.source_srt_list = get_subtitle_from_srt(task.cfg.source_sub, is_file=True) or []
    task.target_srt_list = get_subtitle_from_srt(task.cfg.target_sub, is_file=True) or []
    task.should_recogn = False
    task.should_trans = False
```

1. **ASR is Never Executed During Render**: When a user reaches Stage 4 (or directly calls `/api/render` or `/api/export`), the dialog subtitles are already edited and authoritative (`task.should_recogn = False`). The job is an offline assembly operation: mixing audio tracks and burning subtitles.
2. **False Configuration Blocking**: If the user selected a third-party ASR provider in Stage 1 that requires API keys (such as Deepgram or ElevenLabs Scribe), `ensure_asr_configured` verifies `settings_store.get("deepgram_apikey")`. If the user rendered with a different profile, or if API keys expired, the video render task is blocked with:
   ```text
   ValueError: Configure Deepgram API settings before starting
   ```
3. **Asymmetry in `create_job_handler`**: Notice that line 846 explicitly checks `if job_type not in {"asr", "render"}:` before checking translation configuration. The author intentionally bypassed translation checks for render jobs, but omitted the bypass for ASR checks on line 845.
4. **Resilience for Pure Render Payloads in `build_task_params`**: In `build_task_params:484-512`, `recogn_type` and `translate_type` call `_required_index(options.get(...))`. For pure render requests that omit `recognType` or `translateType`, `build_task_params` should provide safe defaults (`0`) rather than rejecting the payload.

### 4.2 Architectural Solution
1. In `create_job_handler`, guard `ensure_asr_configured` with `if job_type != "render":`.
2. In `build_task_params`, when `job_type == "render"`:
   - Allow `recogn_type` to default via `_optional_index(options.get("recognType"), ..., 0)`.
   - Treat `job_type == "render"` like `job_type == "asr"` regarding translation options: bypass mandatory translation engine validation and use safe fallback defaults.
3. In `create_job_handler`, catch `(ValueError, TypeError, OverflowError)` and convert them to `HTTP 400 Bad Request`, preventing internal server error leaks.

---

## 5. Deep Dive: Issue 4 — Upload Directory Encapsulation & Test Isolation

### 5.1 Vulnerability Mechanism & Root Cause
In `webui.py`:
- Line 43: `UPLOAD_DIR = Path(TEMP_DIR) / "webui_uploads"`
- Line 790 & 806: `saved = UPLOAD_DIR / f"edit-{uuid.uuid4().hex}-{filename}"`
- Line 1167:
  ```python
  app["media_store"] = MEDIA if upload_dir is None and media_probe is get_video_info else MediaStore(upload_dir or UPLOAD_DIR, media_probe)
  ```

In `media_handler` (lines 749, 756):
```python
store: MediaStore = request.app["media_store"]
upload_path = store.upload_dir / f"{uuid.uuid4().hex}-{filename}"
```
`media_handler` properly accesses the injected `request.app["media_store"].upload_dir`.  
In contrast, `edit_asset_handler` hardcodes `UPLOAD_DIR`. When `create_app(upload_dir=tmp_path / "uploads")` is initialized in test environments:
- Video media is correctly isolated in `tmp_path / "uploads"`.
- Edit assets (BGM tracks, cover art thumbnails) are written into the host machine's global temp directory (`TEMP_DIR/webui_uploads`).
- If permissions or concurrent test runs clean up temp directories, assets can collide or fail isolation assertions.

### 5.2 Architectural Solution
In `edit_asset_handler`:
```python
store: MediaStore = request.app["media_store"]
...
saved = store.upload_dir / f"edit-{uuid.uuid4().hex}-{filename}"
```
This guarantees consistent encapsulation across the entire application lifecycle.

---

## 6. Exact Unified Diffs for `webui.py`

Here are the precise unified diffs to be applied by the implementer:

```diff
--- a/webui.py
+++ b/webui.py
@@ -6,4 +6,5 @@
 import argparse
 import asyncio
+import math
 import re
 import threading
@@ -345,4 +346,17 @@
     return index if 0 <= index < size else default
 
+def _safe_volume(value: Any, default: float) -> float:
+    """Safely coerce volume float value clamped to [0.0, 1.5], with fallback default."""
+    if value is None or isinstance(value, bool):
+        return default
+    try:
+        val = float(value)
+        if math.isnan(val):
+            return default
+        return max(0.0, min(1.5, val))
+    except (TypeError, ValueError, OverflowError):
+        return default
+
 
 def _translation_mode(value: Any = None) -> tuple[str, bool]:
@@ -483,9 +497,14 @@
     cache_dir = Path(TEMP_DIR) / file_info.uuid
 
-    recogn_type = _required_index(options.get("recognType"), len(recognition.RECOGN_NAME_LIST), "ASR engine")
-    asr_provider = ASR_BY_TYPE.get(recogn_type)
-    if asr_provider is None:
-        raise ValueError(f"Unsupported ASR engine: {recogn_type}")
-    model_name = str(options.get("modelName") or asr_provider["models"][0])
-    if model_name not in asr_provider["models"]:
-        raise ValueError(f"Model {model_name} is not supported by {asr_provider['label']}")
+    if job_type == "render":
+        recogn_type = _optional_index(options.get("recognType"), len(recognition.RECOGN_NAME_LIST), 0)
+        asr_provider = ASR_BY_TYPE.get(recogn_type) or ASR_PROVIDERS[0]
+        model_name = str(options.get("modelName") or asr_provider["models"][0])
+    else:
+        recogn_type = _required_index(options.get("recognType"), len(recognition.RECOGN_NAME_LIST), "ASR engine")
+        asr_provider = ASR_BY_TYPE.get(recogn_type)
+        if asr_provider is None:
+            raise ValueError(f"Unsupported ASR engine: {recogn_type}")
+        model_name = str(options.get("modelName") or asr_provider["models"][0])
+        if model_name not in asr_provider["models"]:
+            raise ValueError(f"Model {model_name} is not supported by {asr_provider['label']}")
 
     source_language = str(options.get("sourceLanguage") or "zh-cn")
@@ -495,3 +514,3 @@
 
-    is_asr_only = (job_type == "asr")
-    if is_asr_only:
+    is_asr_only = (job_type == "asr")
+    if is_asr_only or job_type == "render":
         translate_type = int(options.get("translateType") or 0)
         aisendsrt = False
         tts_type = int(options.get("ttsType") or 0)
         target_language = str(options.get("targetLanguage") or source_language)
+        if target_language not in translator.LANGNAME_DICT:
+            target_language = source_language
         timing_mode = str(options.get("timingMode") or "voice")
         timing_flags = TIMING_MODES.get(timing_mode, TIMING_MODES["voice"])
-        voice_role = "No"
+        voice_role = str(options.get("voiceRole") or "No")
     else:
@@ -528,4 +547,7 @@
     if isinstance(raw_vol, (int, float)) and not isinstance(raw_vol, bool):
-        diff = int(round((float(raw_vol) - 1.0) * 100))
-        norm_volume = f"{diff:+d}%"
+        try:
+            diff = int(round((float(raw_vol) - 1.0) * 100))
+            norm_volume = f"{diff:+d}%"
+        except (OverflowError, ValueError):
+            norm_volume = "+0%"
     elif raw_vol is not None and str(raw_vol).strip():
@@ -563,4 +585,4 @@
         "background_music": options.get("backgroundMusicPath"),
-        "backaudio_volume": max(0.0, min(1.5, float(options.get("backgroundAudioVolume", 0.8)))),
-        "source_audio_volume": max(0.0, min(1.5, float(options.get("originalAudioVolume", 0.0)))),
+        "backaudio_volume": _safe_volume(options.get("backgroundAudioVolume"), 0.8),
+        "source_audio_volume": _safe_volume(options.get("originalAudioVolume"), 0.0),
         "thumbnail": options.get("thumbnailPath"),
@@ -779,29 +801,39 @@
     saved: Path | None = None
     filename = ""
-    if request.content_type and "multipart" in request.content_type.lower():
+    store: MediaStore = request.app["media_store"]
+
+    content_type = (request.content_type or "").lower()
+    if "x-www-form-urlencoded" in content_type:
+        raise web.HTTPBadRequest(text="An asset file is required")
+
+    if "multipart" in content_type:
         reader = await request.multipart()
         async for part in reader:
             if part.name != "file" or not part.filename:
                 continue
             filename = Path(unquote(part.filename)).name
             extension = Path(filename).suffix.lower().lstrip(".")
             if extension not in set(allowed[kind]):
                 raise web.HTTPBadRequest(text=f"Unsupported {kind} type: .{extension or 'unknown'}")
-            saved = UPLOAD_DIR / f"edit-{uuid.uuid4().hex}-{filename}"
+            saved = store.upload_dir / f"edit-{uuid.uuid4().hex}-{filename}"
             with saved.open("wb") as output:
                 while chunk := await part.read_chunk():
                     output.write(chunk)
     else:
         raw_name = request.headers.get("X-Filename") or request.query.get("filename") or ""
-        if raw_name:
-            filename = Path(unquote(raw_name)).name
-        else:
-            default_ext = "mp3" if kind == "background-audio" else "png"
-            filename = f"asset.{default_ext}"
+        if not raw_name:
+            raise web.HTTPBadRequest(text="An asset file is required")
+        filename = Path(unquote(raw_name)).name
+        if not filename:
+            raise web.HTTPBadRequest(text="A valid filename is required")
         extension = Path(filename).suffix.lower().lstrip(".")
         if extension not in set(allowed[kind]):
             raise web.HTTPBadRequest(text=f"Unsupported {kind} type: .{extension or 'unknown'}")
         content = await request.read()
-        if content:
-            saved = UPLOAD_DIR / f"edit-{uuid.uuid4().hex}-{filename}"
-            saved.write_bytes(content)
-    if saved is None or not saved.is_file():
+        if not content:
+            raise web.HTTPBadRequest(text="An asset file is required")
+        saved = store.upload_dir / f"edit-{uuid.uuid4().hex}-{filename}"
+        saved.write_bytes(content)
+    if saved is None or not saved.is_file() or saved.stat().st_size == 0:
+        if saved and saved.is_file():
+            saved.unlink(missing_ok=True)
         raise web.HTTPBadRequest(text="An asset file is required")
     asset_id = uuid.uuid4().hex
@@ -844,4 +876,5 @@
         params = build_task_params(media.path, options, job_type=job_type)
-        ensure_asr_configured(params["recogn_type"], request.app["settings_store"])
+        if job_type != "render":
+            ensure_asr_configured(params["recogn_type"], request.app["settings_store"])
         if job_type not in {"asr", "render"}:
             ensure_translation_configured(params["translate_type"], request.app["settings_store"])
         getset_gpu()
@@ -852,3 +885,3 @@
     except ActiveJobError as exc:
         raise web.HTTPConflict(text=str(exc)) from exc
-    except ValueError as exc:
+    except (ValueError, TypeError, OverflowError) as exc:
         raise web.HTTPBadRequest(text=str(exc)) from exc
```

---

## 7. Associated Test Suite Fixes (`tests/test_stage4_edit_video.py`)

For completeness, the Forensic Auditor and Reviewers documented three defects in `tests/test_stage4_edit_video.py` that must be resolved alongside the backend fixes:

### 7.1 Import Location Fix (Line 72)
```diff
--- a/tests/test_stage4_edit_video.py
+++ b/tests/test_stage4_edit_video.py
@@ -71,3 +71,9 @@
-from videotrans.task.job import CancellationToken, TaskRequest, TaskResult, TaskStatus
+from videotrans.task.orchestrator import (
+    CancellationToken,
+    EventKind,
+    TaskEvent,
+    TaskRequest,
+    TaskResult,
+    TaskStatus,
+)
```

### 7.2 Fixture Signature Fix (`dummy_job_runner`, Lines 94-99)
```diff
--- a/tests/test_stage4_edit_video.py
+++ b/tests/test_stage4_edit_video.py
@@ -94,6 +94,11 @@
 @pytest.fixture
 def dummy_job_runner():
     """Deterministic immediate job runner double for JobManager testing."""
     def _runner(request, accept, token):
-        accept(0.5, "Rendering audio mix and burning subtitles...")
-        return TaskResult(status=TaskStatus.SUCCEEDED, outputs=[Path("output.mp4")])
+        job_id = getattr(request, "uuid", getattr(request, "job_id", "job-test"))
+        output_dir = getattr(request, "output_dir", Path("."))
+        accept(TaskEvent(job_id, EventKind.PROGRESS, "render", progress=50.0, message="Rendering audio mix..."))
+        return TaskResult(
+            job_id=job_id,
+            status=TaskStatus.SUCCEEDED,
+            output_dir=output_dir,
+            outputs=(Path("output.mp4"),),
+        )
     return _runner
```

### 7.3 Headless Node Tab Check (`test_headless_node_stage4_screen_render`, Line 890)
In `tests/test_stage4_edit_video.py:890`, ensure `state.editVideo.activeTab` aligns with the asserted DOM elements (e.g. `activeTab: "audio"` when asserting `data-mix-slider`).

---

## 8. Step-by-Step Remediation Instructions for the Implementer

1. **Step 1 — Edit `webui.py` Imports**:
   - Add `import math` to the standard library imports at the top of `webui.py`.
2. **Step 2 — Add `_safe_volume` Function**:
   - Place `_safe_volume(value: Any, default: float) -> float` right after `_optional_index` around line 346.
3. **Step 3 — Update `build_task_params`**:
   - Condition `recogn_type` requirement on `job_type != "render"`.
   - Include `job_type == "render"` in the translation bypass branch (`if is_asr_only or job_type == "render":`).
   - Wrap `volume` float diff rounding in `try...except (OverflowError, ValueError): norm_volume = "+0%"`.
   - Replace lines 564-565 with `_safe_volume(options.get("backgroundAudioVolume"), 0.8)` and `_safe_volume(options.get("originalAudioVolume"), 0.0)`.
4. **Step 4 — Update `edit_asset_handler`**:
   - Retrieve `store: MediaStore = request.app["media_store"]`.
   - Reject `x-www-form-urlencoded` immediately with `HTTPBadRequest`.
   - Require `X-Filename` header or query param for raw binary uploads.
   - Save files to `store.upload_dir / ...`.
   - Verify `saved.stat().st_size > 0`; unlink and reject empty 0-byte files with `HTTPBadRequest`.
5. **Step 5 — Update `create_job_handler`**:
   - Guard `ensure_asr_configured` with `if job_type != "render":`.
   - Expand exception handler to catch `(ValueError, TypeError, OverflowError)`.
6. **Step 6 — Update `tests/test_stage4_edit_video.py`**:
   - Fix import on line 72 (`from videotrans.task.orchestrator import ...`).
   - Fix `dummy_job_runner` fixture to pass `TaskEvent` and construct `TaskResult` with `job_id` and `output_dir`.
   - Fix `activeTab` in `test_headless_node_stage4_screen_render`.
7. **Step 7 — Validate Verification Commands**:
   - Run `uv run pytest tests/test_stage4_edit_video.py -v`.
   - Run `uv run pytest tests/test_webui.py tests/test_stage3_voice_dubbing.py -v`.
   - Confirm 100% pass rate.

---

## 9. Independent Verification Method

Execute the following commands to confirm that all four backend issues and all test suite defects are resolved:

```bash
# 1. Primary Stage 4 Test Suite Verification
uv run pytest tests/test_stage4_edit_video.py -v

# 2. Existing Regression Test Suites Verification
uv run pytest tests/test_webui.py tests/test_stage3_voice_dubbing.py -v

# 3. Challenger Adversarial Suites (if present)
uv run pytest tests/test_stage4_adversarial_stress.py -v
uv run pytest tests/test_stage4_adversarial_challenger2.py -v
node tests/stage4_stress_harness.mjs
```

**Success Criteria**:
- Pytest collects 32 test functions without `ImportError`.
- `test_asset_upload_requires_file_or_content` passes (returns HTTP 400 for form-urlencoded without files and empty payloads).
- `test_adversarial_invalid_audio_mix_inputs` passes (non-numeric, None, NaN volume inputs default safely without exception).
- Daemon threads execute cleanly without `TypeError: JobRecord.accept()`.
- All tests pass with zero errors, zero failures, and zero regressions.
