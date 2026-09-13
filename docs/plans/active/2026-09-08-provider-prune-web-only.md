# Execution Plan: Web-Only Seven-Provider Runtime Consolidation

Date: 2026-09-08

## Status

Active — implementation and verification in progress (2026-09-09)

## Outcome

Target state: VoiceStudio operates strictly as a local-first web application with seven authorized providers:
1. **TTS**: `OmniVoice` (Python in-process only) and `VieNeuTTS` (`vienue`).
2. **ASR**: `Deepgram` (`deepgram-asr`, explicit opt-in only).
3. **Translation**: `Google Translate` (`google`) and `OpenAI-compatible LLMs` (`openai`).
4. **LLM**: `OpenAI-compatible LLMs` (`openai-compat`).
5. **OCR**: `RapidOCR` and `PaddleOCR` (via `hardsub_ocr`).

The implementation is not complete until the runtime, frontend, dependencies,
delivery workflows, and live documentation contain no removed-provider or Tauri
paths, and the verification gates below pass from an empty offline HF cache.

## Scope

- **In scope**: Provider allowlists, boundary validation, database preferences migration, model catalogue, engine directories & binaries, dependency declarations (`pyproject.toml`, `package.json`), lockfiles (`uv.lock`, `bun.lock`), web delivery conversion, regression test suites, documentation.
- **Out of scope**: Modifying user projects, user voice profiles, or existing model weight directories (`omnivoice_data/`).

## Decisions

- **2026-09-08**: Hugging Face access remains solely for `k2-fsa/OmniVoice`.
- **2026-09-08**: Deepgram is explicit opt-in; migration sanitizes preferences without initiating audio upload.
- **2026-09-08**: OmniVoice runs via in-process Python backend only; subprocess and GGUF wrappers deleted.
- **2026-09-08**: Tauri desktop shell eliminated in favor of clean browser runtime; `bun.lock` remains `--frozen-lockfile` compliant.

## Progress

- [x] Establish allowlists and migration.
  - Added `backend/core/provider_boundary.py` with strict allowlists and validation helpers.
  - Added Alembic migration `backend/migrations/versions/0011_provider_boundary_migration.py`.
  - Wired boundary sanitization into `backend/core/prefs.py`.
- [~] Remove unused provider implementations and dependencies.
  - Pruned `backend/config/models.yaml` to `k2-fsa/OmniVoice`.
  - Pruned `backend/services/tts_backend.py` to `omnivoice` and `vienue`.
  - Pruned `backend/services/asr_backend.py` to `deepgram-asr`.
  - Removed the translation engine installer/API; the dubbing UI has fixed `google` and `openai` choices.
  - Removed unused engine directories (`confucius4`, `dots_tts`, `indextts`, `moss_tts_v15`, `omnivoice_gguf`, `omnivoice_subprocess`, `pockettts`, `supertonic3`, `_asr_sidecar`, `subprocess_asr.py`) and C++ binaries (`bin/omnivoice-tts-*`).
  - Remaining: remove stale runtime helpers, obsolete dependency/CLI declarations, and their tests.
- [~] Convert frontend and delivery to web-only.
  - Removed `frontend/src-tauri` and `@tauri-apps/*` dependencies from `frontend/package.json`.
  - Removed desktop capture and Tauri IPC components.
  - Replaced Tauri shell open with browser `window.open` in `external.ts`.
  - Configured Vite virtual resolver stub in `frontend/vite.config.js`.
  - Remaining: remove stale web runtime branches, workflow/template references, and validate the lockfile again.
- [~] Update documentation and prove the boundary.
  - Updated `CHANGELOG.md` under `## [Unreleased]`.
  - Added the initial boundary test suite; expand it to prevent obsolete source dependencies from returning.

## Validation

Run the following only after all pruning is complete; do not carry forward
historical counts as proof of the final state:

- `HF_HUB_OFFLINE=1` with an empty `HF_HUB_CACHE`: targeted provider tests,
  then the complete backend suite.
- Frontend locale parity, typecheck, Vitest, and production Vite build.
- `uv sync --locked`, `bun install --frozen-lockfile`, and Docker build/run.
