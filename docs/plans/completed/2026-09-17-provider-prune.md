# Execution Plan: Prune Unsupported ASR And Translation Providers

Date: 2026-09-17

## Status

Completed

## Outcome

The application exposes and ships only these ASR providers: Qwen-ASR,
Deepgram, Gemini STT, Google STT API, ElevenLabs, and Whisper Large-v3; and only
these translation providers: Google Translate, OpenAI ChatGPT, Gemini, and
DeepSeek.

## Context

- Authority: the repository owner's provider lists in the current conversation.
- Registries: `videotrans/recognition/__init__.py` and
  `videotrans/translator/_registry.py`.
- Web adapter: `webui.py` and `frontend/js/`.
- Desktop adapters: `videotrans/mainwin/`, `videotrans/component/`, and
  `videotrans/winform/`.

## Scope

In scope:

- Remove repository-owned implementation and UI registration for other ASR and
  translation providers.
- Remove provider-specific model catalogs and dependencies when exclusive use is
  proven.
- Keep provider identifiers contiguous and migrate old persisted numeric values.
- Add repository-native tests that reject reintroduction into the registries.

Out of scope:

- TTS, OCR, separation, and unrelated model providers.
- User-downloaded model weights and caches.
- Automatic deletion from an existing Python environment.

## Approach

Inventory references and exclusive dependencies, reduce the two authoritative
registries, update desktop and Web adapters, delete orphaned source files, then
run focused and broader tests.

## Risks And Recovery

- Stored numeric provider selections can point to a different provider after
  compaction; legacy values are migrated once with provider catalog version 2.
- Shared provider settings also used by TTS were retained while their removed
  translation/ASR paths were disabled.
- Recovery is the working-tree diff; no user caches or model directories were
  modified.

## Progress

- [x] Confirm global ASR and translation pruning scope.
- [x] Inventory references, files, model catalogs, and exclusive dependencies.
- [x] Reduce registries and adapters.
- [x] Delete orphaned provider code and UI handlers.
- [x] Validate allowed and forbidden provider cases.

## Decisions

- 2026-09-17: Preserve the six ASR and four translation providers previously
  selected by the owner; prune all others globally.
- 2026-09-17: Do not delete downloaded model caches because they are user data,
  not repository-owned provider implementation.
- 2026-09-17: Retain shared TTS settings for 302.AI, Xiaomi, Zhipu, CAMB,
  ElevenLabs, and Gemini while removing their unsupported ASR/translation roles.
- 2026-09-17: Google Translate no longer silently falls back to the removed
  Microsoft provider; an unavailable Google connection is reported explicitly.

## Validation

- `183 passed`: CLI, constants, provider catalog, WebUI, configuration, base
  recognition, main-window action, and desktop UI tests.
- `56 passed`: focused provider catalog, WebUI, and configuration suite.
- Desktop UI offscreen smoke test showed only retained translation and ASR API
  settings.
- `uv lock --check`, Python compileall, JavaScript syntax checks, stale provider
  reference scans, and `git diff --check` passed.
- The full suite is not currently a green repository gate: collection is
  blocked by the pre-existing `tests/test_job_helpers.py` import of a missing
  `_get_type_name` symbol from `videotrans.task.job`.

## Result

Provider registries, implementation modules, desktop provider dialogs, model
catalogs, CLI defaults, WebUI defaults, parameter migration, dependencies, and
lock data now match the accepted six-ASR/four-translation policy. The lockfile
removed the obsolete Alibaba, DeepL, Tencent, FunASR, OpenAI-Whisper, OSS, and
related transitive packages.
