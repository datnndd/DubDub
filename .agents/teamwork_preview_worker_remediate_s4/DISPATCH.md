## 2026-09-20T03:35:41Z
You are the Remediation Worker subagent for DubDub AI Video Dubbing Studio Stage 4 Redesign (Iteration 2).
Your identity: worker_remediate_s4
Your working directory: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_worker_remediate_s4
Original Request path: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md
Forensic Auditor Report path: c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_auditor_1_s4\handoff.md
Remediation Plan 1 (Tests): c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_remediate_audit_s4_1\remediation_plan.md
Remediation Plan 2 (Backend): c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_remediate_audit_s4_2\remediation_plan.md
Remediation Plan 3 (Test Assertions): c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_remediate_audit_s4_3\remediation_plan.md

MANDATORY FIRST STEP: Read c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\ORIGINAL_REQUEST.md (specifically section ## 2026-09-20T03:04:42Z). Do not summarize or skip reading it.
Read the Forensic Auditor Report and the three Remediation Plans.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Scope & Exclusively Owned Files:
- `tests/test_stage4_edit_video.py`
- `webui.py`
- `TEST_READY.md`

Tasks:
1. Apply fixes to `tests/test_stage4_edit_video.py`:
   - Line 72: Change import to:
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
   - Lines 94-99: Update `dummy_job_runner` fixture to pass `TaskEvent` to `accept()` and initialize `TaskResult` with all required positional parameters (`job_id`, `status`, `output_dir`, `outputs`).
   - `test_headless_node_stage4_screen_render`: Update to sequentially render across all 3 inspector tabs (`subtitles`, `audio`, `thumbnail`) and assert tab-specific elements on their respective rendered HTML while asserting common preview and timeline elements.
   - Replace any self-certifying local mock functions in Section 3 and Section 6 with real tests against `webui.py` and `frontend/js/state.js` / `Stage4EditVideo.js` (via Node.js).
2. Apply fixes to `webui.py`:
   - `build_task_params`: Safe volume parsing with clamping to `[0.0, 1.5]` and default fallbacks (`0.8` for `backgroundAudioVolume`, `0.0` for `originalAudioVolume`) when receiving `None`, non-numeric strings, or invalid inputs. Add safe handling for dubbed `volume`.
   - `edit_asset_handler`: Reject `x-www-form-urlencoded` or non-file requests with HTTP 400 Bad Request, require `X-Filename` for raw binary uploads, reject 0-byte files with HTTP 400, and use `request.app["media_store"].upload_dir`.
   - `create_job_handler`: Skip `ensure_asr_configured` when `job_type in {"asr", "render"}` or `job_type == "render"`.
3. Update `TEST_READY.md` with verified test counts and status.
4. MANDATORY EXECUTION:
   Run the test commands:
   `uv run pytest tests/test_stage4_edit_video.py -v`
   `uv run pytest tests/test_stage3_voice_dubbing.py tests/test_webui.py -v`
   Verify 100% of tests pass cleanly. Capture and document the exact terminal outputs in your handoff report.
5. Write your detailed changes to `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_worker_remediate_s4\changes.md`.
6. Write `c:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_worker_remediate_s4\handoff.md` with: Observation, Logic Chain, Caveats, Conclusion, Verification Method (including literal pytest output).
7. Send a completion message to your parent.
