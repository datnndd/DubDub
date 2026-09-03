# Releasing — VoiceStudio (web-first)

VoiceStudio ships as a source checkout / Docker image — there is no signed
desktop bundle anymore (the Tauri shell was removed on 2026-09-02; the old
updater signing notes are history).

## Versioning

- `frontend/package.json` is the single source of truth; `pyproject.toml` and
  `backend/core/version.py::_FALLBACK_VERSION` mirror it and are checked by
  `tests/test_app_version.py`.
- Bump the version, update `CHANGELOG.md` [Unreleased] → release notes, tag.

## Release checklist

1. CI green (backend + frontend tests, lint, typecheck, docker build).
2. `CHANGELOG.md` release section filled.
3. Tag + push; the Docker workflow publishes the image.
