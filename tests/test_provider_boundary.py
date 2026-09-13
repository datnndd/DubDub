"""Executable invariant for the web-only seven-provider boundary."""
from __future__ import annotations

import json
import inspect
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def _boundary_errors(root: Path) -> list[str]:
    errors: list[str] = []
    models = yaml.safe_load((root / "backend/config/models.yaml").read_text(encoding="utf-8"))
    repos = {row["repo_id"] for row in models.get("models", [])}
    if repos != {"k2-fsa/OmniVoice"}:
        errors.append(f"models.yaml must contain only k2-fsa/OmniVoice; found {sorted(repos)}")
    forbidden_paths = [
        "frontend/src-tauri", "backend.spec", "bin/omnivoice-tts-windows-x86_64.exe",
        "Cargo.toml", "Cargo.lock", "frontend/Cargo.toml", "frontend/Cargo.lock",
        "backend/engines/omnivoice_gguf", "backend/engines/omnivoice_subprocess",
        "omnivoice/cli/infer.py", "omnivoice/data/dataset.py",
        "omnivoice/eval/utils.py", "omnivoice/scripts/denoise_audio.py",
        "omnivoice/training/trainer.py",
    ]
    for rel in forbidden_paths:
        if (root / rel).exists():
            errors.append(f"removed provider/delivery artifact returned: {rel}")
    package = (root / "frontend/package.json").read_text(encoding="utf-8")
    lock = (root / "bun.lock").read_text(encoding="utf-8")
    if "@tauri-apps" in package + lock:
        errors.append("Tauri dependency returned to frontend manifests")
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / ".github" / "workflows").glob("*.y*ml")
    ) if (root / ".github" / "workflows").exists() else ""
    if "@tauri-apps" in workflow_text or "tauri-action" in workflow_text:
        errors.append("Tauri build dependency returned to CI workflows")
    pyproject_path = root / "pyproject.toml"
    pyproject = pyproject_path.read_text(encoding="utf-8") if pyproject_path.exists() else ""
    forbidden_dependencies = (
        "accelerate", "gradio", "tensorboardX", "webdataset", "torchvision",
        "en-core-web-sm",
    )
    for dependency in forbidden_dependencies:
        if f'"{dependency}' in pyproject:
            errors.append(f"removed dependency returned to pyproject: {dependency}")
    return errors


def test_boundary_validator_accepts_repository():
    assert _boundary_errors(ROOT) == []


def test_boundary_validator_rejects_extra_hf_repo(tmp_path):
    target = tmp_path / "backend/config"
    target.mkdir(parents=True)
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend/package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "bun.lock").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (target / "models.yaml").write_text(
        "models:\n  - repo_id: k2-fsa/OmniVoice\n  - repo_id: Systran/faster-whisper-large-v3\n",
        encoding="utf-8",
    )
    assert _boundary_errors(tmp_path) == [
        "models.yaml must contain only k2-fsa/OmniVoice; found "
        "['Systran/faster-whisper-large-v3', 'k2-fsa/OmniVoice']"
    ]


def test_runtime_registries_are_exact_allowlists():
    from services import asr_backend, tts_backend
    assert set(tts_backend._REGISTRY) == {"omnivoice", "vienue"}
    assert set(asr_backend._REGISTRY) == {"deepgram-asr"}


def test_ocr_and_translation_registries_are_exact_allowlists():
    from services.hardsub_ocr import run_ocr_client
    from core.provider_boundary import sanitize_translate_provider

    assert inspect.signature(run_ocr_client).parameters["model_id"].default == "rapidocr"
    assert sanitize_translate_provider("google") == "google"
    assert sanitize_translate_provider("openai") == "openai"
    assert sanitize_translate_provider("argos") == "google"


def test_worker_capabilities_never_advertise_a_removed_provider():
    from worker.capabilities import repo_ids_for
    assert repo_ids_for({"id": "omnivoice"}) == ["k2-fsa/OmniVoice"]
    assert repo_ids_for({"id": "vienue"}) == []
    assert repo_ids_for({"id": "whisperx"}) == []


def test_provider_and_hf_allowlists_are_exact():
    from core.provider_boundary import (
        ALLOWED_ASR_PROVIDERS, ALLOWED_HF_MODELS, ALLOWED_OCR_PROVIDERS,
        ALLOWED_TRANSLATE_PROVIDERS, ALLOWED_TTS_PROVIDERS, enforce_hf_model_boundary,
    )
    assert ALLOWED_TTS_PROVIDERS == {"omnivoice", "vienue"}
    assert ALLOWED_ASR_PROVIDERS == {"deepgram-asr", "deepgram"}
    assert ALLOWED_TRANSLATE_PROVIDERS == {"google", "openai"}
    assert ALLOWED_OCR_PROVIDERS == {"rapidocr", "paddleocr"}
    assert ALLOWED_HF_MODELS == {"k2-fsa/OmniVoice"}
    with pytest.raises(ValueError, match="Model download blocked"):
        enforce_hf_model_boundary("Systran/faster-whisper-large-v3")


def test_pref_migration_preserves_unrelated_user_data(tmp_path, monkeypatch):
    from core import prefs
    path = tmp_path / "prefs.json"
    original = {
        "tts_backend": "cosyvoice", "asr_backend": "whisperx",
        "translation_engine": "nllb", "project.last": "keep-me",
        "voice.default": "voice-123", "dictation.shortcut": "Ctrl+Shift+D",
        "env.OMNIVOICE_INDEXTTS_DIR": "old-engine",
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(prefs, "_PREFS_PATH", str(path))
    assert prefs.migrate_provider_boundary() is True
    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert migrated["tts_backend"] == "omnivoice"
    assert migrated["asr_backend"] == "deepgram-asr"
    assert migrated["translation_engine"] == "google"
    assert migrated["project.last"] == "keep-me"
    assert migrated["voice.default"] == "voice-123"
    assert "dictation.shortcut" not in migrated
    assert "env.OMNIVOICE_INDEXTTS_DIR" not in migrated


def test_removed_routes_are_not_registered(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    from main import app
    routes = {route.path for route in app.routes}
    forbidden = {
        "/api/settings/hf-token", "/api/settings/hf-token/state",
        "/api/settings/asr-openai-compat", "/system/hf-token/state",
        "/system/logs/tauri", "/system/logs/tauri/clear",
        "/capture/ws", "/dictation/refine",
    }
    assert routes.isdisjoint(forbidden), sorted(routes & forbidden)
