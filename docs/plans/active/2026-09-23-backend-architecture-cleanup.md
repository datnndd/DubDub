# Backend Architecture Cleanup

Date: 2026-09-23

## Status

Active

## Outcome

Finish the web-only migration with React as the product frontend and a backend
whose HTTP, workflow, provider, persistence, media, and configuration
responsibilities have explicit owners. Preserve working processing behavior and
user assets while removing desktop-only compatibility and generated files.

## Baseline findings

- The Python suite and React production build pass, but most frontend behavior
  tests still exercise the retired vanilla JavaScript implementation.
- React Stage 4 submitted a payload that the render endpoint rejected and lost
  uploaded asset identifiers and per-segment voice overrides.
- `webui.py` is a broad test compatibility facade; backend modules reach back
  into it through `sys.modules`, reversing the intended dependency direction.
- `JobManager` owns execution, persistence, project updates, event fan-out, and
  cancellation, so it remains the main application-service split point.
- Generated `frontend/node_modules/` content was committed.
- Legal files and configured OmniVoice reference audio were deleted without
  authority; the audio deletion contradicted the earlier migration scope.
- A deleted Qt signal module was imported behind a swallowed exception.
- A clean deployment did not build the React bundle.

## Phases

### Phase 0: restore a truthful baseline

- [x] Restore legal files, user documentation, and configured reference audio.
- [x] Remove tracked `node_modules` and ignore generated frontend dependencies.
- [x] Repair the React Stage 4 request contract and remove demo transcript data.
- [x] Build React and run focused API tests plus the full Python suite.

### Phase 1: establish backend ownership

- [x] Move edit-asset state out of HTTP route modules into an injected service.
- [x] Replace `sys.modules['webui']` test hooks with constructor/app dependencies.
- [x] Reduce `webui.py` to runtime initialization and application startup.
- [x] Split job registration/cancellation from execution and persistence without
  changing the public API.

### Phase 2: retire the legacy frontend

- [x] Add React behavior tests for all four stages and API request contracts.
- [x] Remove `frontend/js`, `frontend/css`, fallback serving, and legacy tests
  only after equivalent React proof exists.
- [x] Make CI and Docker build the React production bundle from the lockfile.

Phase 2 implementation and automated validation are complete. The user reports
that the configured Stage 1-through-Stage 4 browser workflow smoke test passed.
The deployment context was not specified, so the clean-checkout/Docker portion
of the verification gate is not independently confirmed here.

### Phase 3: documentation and dependency closure

- [x] Rewrite architecture and FAQ material as current web-only documentation.
- [x] Remove stale desktop names/comments and verify no supported import reaches
  PySide6 or deleted desktop modules.
- [x] Audit Python dependencies against runtime imports and remove only those
  proved unused by supported providers and workflows. No dependency was
  removed: PySide6/PyQt are not declared, and the broad pinned runtime set
  supports lazily imported provider/model integrations, so static absence from
  a direct import scan is not sufficient proof of safe removal.

Phase 3 documentation and code cleanup is implemented. The no-Qt guard, full
Python suite, React production build, lockfile check, and diff check passed.
Phase 3 dependency review found no safely removable package without weakening
provider coverage. The user reports a passing configured browser workflow;
clean-checkout/Docker execution context is the remaining unverified completion
gate. During follow-up inspection, removed the
unreferenced Whisper.NET setup guide and configuration helper: Whisper.NET is
not in the active recognition registry, `pythonnet` is not declared, and the
guide's `webui`/`dotnet` extras do not exist. A dry run confirmed
`uv sync --extra webui` fails because that extra is undefined.

## Verification gates

Each phase requires a clean React build, focused API/workflow tests, the full
Python suite, no-Qt import proof, and `git diff --check`. Phase 2 also requires
a clean-checkout/Docker smoke test that loads React and a configured Stage
1-through-Stage 4 browser workflow. Browser workflow success is user-reported;
clean-checkout/Docker execution remains unverified unless that was the context
of the reported run.

## Recovery

Keep changes in small behavior-preserving commits. Restore reference assets and
legal material from `f588fe62` if cleanup removes them accidentally. Do not
delete legacy frontend code until React-specific tests cover its behavior.
