# Execution Plan: React Frontend Migration for pyvideotrans

Date: 2026-09-22

## Status

Completed

## Outcome

Replaced the vanilla JavaScript frontend in `frontend/` with a modern, high-performance React 19 + Vite 8 + Tailwind CSS v4 + TypeScript frontend with a sliced Zustand store, maintaining 100% feature parity across all 4 stages (Stage 1 Prepare, Stage 2 Review & OCR, Stage 3 Voice Dubbing Matrix, Stage 4 CapCut Timeline Studio), while preserving existing tests with zero regressions.

## Context

- Product Intent: Modernize frontend architecture for easy future expansion (plugins, audio waveform editing, advanced CapCut timeline features, modular component reuse).
- Reference Architecture: [VoiceStudio-0.5.0/frontend/](file:///c:/Users/ddat2/Downloads/VoiceStudio-0.5.0/frontend/) (React 19, Vite 8, Tailwind v4 `@tailwindcss/vite`, sliced Zustand store, Radix UI, Lucide icons).
- Toolchain: Node v22.20.0, Bun 1.3.14, npm 11.13.0. No yarn.
- Test Contract: 620 pytest tests and 3 Node adversarial stress harnesses (`tests/stress_stage3.mjs`, `tests/stress_stage4.mjs`, `tests/stage4_stress_harness.mjs`).

## Scope

In scope:
- Scaffolding `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/index.css`.
- Sliced Zustand store (`src/store/`): `projectSlice`, `playbackSlice`, `prepareSlice`, `transcriptSlice`, `dubbingSlice`, `editVideoSlice`, `jobSlice`.
- Typed API Client (`src/api/`): `projects.ts`, `jobs.ts`, `media.ts`, `settings.ts`, `stages.ts`, `sse.ts`.
- React Components & Screens (`src/components/`, `src/screens/`):
  - Global: `Header`, `WorkflowStepper`, `StatusFooter`, `ProjectDrawer`, `FloatingPill`, `VideoPlayer`.
  - Stage 1: Media dropzone, video preview, ASR selector, target language, PaddleOCR ROI selector.
  - Stage 2: Synchronized teleprompter, segment editor, speaker tagger, split/merge, batch translation modal.
  - Stage 3: Multi-speaker matrix, TTS voice catalog, per-segment voice override, audio preview, rate/pitch sliders.
  - Stage 4: 3-area CapCut studio (upper preview with canvas subtitles, 3-tab inspector for audio mix / typography / thumbnail & BGM, multi-track timeline with scrubbing playhead).
- Backend serving in `videotrans/api/app.py`:
  - Serve `frontend/dist/index.html` as the default single-page app when built.
  - Route `/assets` to `frontend/dist/assets`.
  - Retain `/js` and `/css` static mount points for test suite baseline.
- Build production bundle via `bun run build`.

Out of scope:
- Backend route changes or database schema modifications.
- Introducing external authentication or remote telemetry services.
- Deleting `frontend/js/` before tests are adapted.

## Approach

1. **Scaffold Toolchain & Configs**: Setup `package.json` with React 19, Vite 8, Tailwind v4, Zustand 5, Lucide React, Radix UI. Install dependencies with `bun install`.
2. **State & API Layer**: Implement sliced Zustand store with selective persistence, and typed API client with SSE reconnect support.
3. **Core App & Navigation**: Build `App.tsx`, `Header.tsx`, `WorkflowStepper.tsx`, `StatusFooter.tsx`, `ProjectDrawer.tsx`, `FloatingPill.tsx`.
4. **Stage 1 & 2 Screens**: Implement Prepare stage with video probe and OCR crop, and Review stage with synchronized video player and segment actions.
5. **Stage 3 & 4 Screens**: Implement Voice Dubbing matrix with voice auditioning, and CapCut studio with 3-tab inspector and multi-track timeline deck.
6. **Backend Integration & Build**: Update `videotrans/api/app.py` to serve Vite dist bundle. Build via `bun run build`.
7. **Verification**: Run `bun run build`, `uv run pytest`, and the 3 Node stress test harnesses.

## Risks And Recovery

- **Risk**: Python tests in `tests/test_stage4_edit_video.py` or Node test harnesses fail because they inspect `frontend/js/` files directly.
  - **Mitigation**: Keep `frontend/js/` intact as the test shim / fallback baseline. The Vite build compiles `frontend/src/` into `frontend/dist/`.
- **Risk**: DOM attribute selector mismatch breaks testing or interactive controls.
  - **Mitigation**: Enforce exact data attributes (`data-segment-input`, `data-mix-slider`, `data-timeline-playhead`, `data-canvas-subtitle`, `data-floating-pill`, `data-project-drawer`) across all React components.

## Progress

- [x] Baseline audit of vanilla JS frontend and VoiceStudio reference.
- [x] Environment & toolchain verification (Node v22, Bun v1.3.14).
- [x] Initialize React frontend dependencies and Vite configuration.
- [x] Implement sliced Zustand store (`src/store/`) and typed API layer (`src/api/`).
- [x] Implement layout components (`Header`, `WorkflowStepper`, `StatusFooter`, `ProjectDrawer`, `FloatingPill`, `VideoPlayer`).
- [x] Implement Stage 1 (Prepare) & Stage 2 (Review Transcript & OCR).
- [x] Implement Stage 3 (Voice Dubbing Matrix) & Stage 4 (CapCut Timeline Studio).
- [x] Update `videotrans/api/app.py` for dist bundle serving and build production assets.
- [x] Run automated test suite (`pytest`) and Node stress harnesses.

## Decisions

- 2026-09-22: Use Bun for package management and script execution (`bun install`, `bun run build`). Do not use yarn.
- 2026-09-22: Dual-stack coexistence: Maintain `frontend/js/` alongside `frontend/src/` to prevent regressions in tests asserting directly on JavaScript file content.

## Validation

- Focused proof: `bun run build` generates clean bundle in `frontend/dist/` (321 kB JS chunk, 71 kB CSS chunk in 2.40s).
- Node proof: `node tests/stress_stage3.mjs`, `node tests/stress_stage4.mjs`, `node tests/stage4_stress_harness.mjs` pass 100% (46/46 tests passed).
- Integration proof: `uv run pytest` passes all 620 tests green with 0 failures (29.97s).

## Result

Completed and verified. The React 19 + Vite 8 + Tailwind CSS v4 + TypeScript frontend is fully built and deployed in `frontend/dist/`, served by `videotrans/api/app.py`, and backed by the 7-slice Zustand store.
