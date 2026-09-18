# Execution Plan: Prune TTS Providers

Date: 2026-09-18

## Status

Completed

## Outcome

The application exposes and ships only ElevenLabs, OmniVoice, VieNeu-TTS, and
Gemini TTS. VieNeu-TTS is the default provider.

## Authority

The repository owner's provider list and default selection in the current
conversation.

## Scope

- Reduce the shared TTS registry and every UI backed by it.
- Migrate saved legacy numeric selections to the compact catalog.
- Remove repository-owned provider implementations, dialogs, model catalogs,
  and exclusive dependencies for providers outside the retained set.
- Preserve user-downloaded model directories and voice/reference audio.
- Validate the four retained provider routes, defaults, and absence of removed
  registrations.

## Risks And Recovery

- TTS IDs are persisted; both main and standalone-dubbing selections migrate
  before using the compact catalog.
- Gemini and ElevenLabs configuration remains because it is shared with
  retained translation and ASR features.
- OmniVoice still reuses reference-audio configuration historically named
  `f5tts_role`; that data path remains until a separate storage migration.
- User-downloaded model caches and reference audio were not deleted.

## Progress

- [x] Inventory the registry, consumers, provider UI, settings, and dependencies.
- [x] Reduce the catalog and migrate saved IDs.
- [x] Remove unsupported implementation and configuration.
- [x] Validate retained providers and user-visible defaults.

## Result

- Compact TTS IDs are ElevenLabs `0`, OmniVoice `1`, VieNeu-TTS `2`, and
  Gemini TTS `3`; the default is `2`.
- Catalog migration version 3 preserves the four retained legacy selections and
  maps removed or unknown providers to VieNeu-TTS.
- WebUI, CLI, PySide6, task routing, role discovery, provider dialogs, and
  standalone dubbing now consume the same four-provider registry.
- Removed providers' implementation modules, dialogs, bundled model catalogs,
  exclusive dependencies, and lockfile packages were removed.

## Validation

- Task-focused pytest suite: `129 passed`.
- All four retained classes imported through the public provider registry:
  `ElevenLabsC`, `OmniVoice`, `VieNeuTTS`, and `GEMINITTS`.
- `uv lock --check` resolved the frozen lock successfully.
- `python -m compileall` passed for `cli.py`, `webui.py`, and `videotrans`.
- `node --check` passed for Prepare-stage state and screen modules.
- `git diff --check` passed; Git emitted only the repository's CRLF conversion
  warnings.
- A broader focused run reached `179 passed` and four unrelated existing stale
  assertions: three pitch expectations and one integer-versus-boolean default.
