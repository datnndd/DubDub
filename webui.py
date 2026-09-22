# -*- coding: utf-8 -*-
"""Local WebUI server for the Dubbing Video workflow."""

from __future__ import annotations

from pathlib import Path
from aiohttp import web

from videotrans.configure import config as runtime_config

runtime_config.init_run()

from videotrans import recognition, translator, tts
from videotrans.configure.config import ROOT_DIR, TEMP_DIR, app_cfg, params as app_params
from videotrans.configure.contants import AUDIO_EXITS, VIDEO_EXTS
from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskEvent,
    TaskRequest,
    TaskResult,
    TaskStatus,
    run,
    run_staged_asr,
    run_staged_translation,
)
from videotrans.util.help_role import role_menu
from videotrans.util._ffmpeg_misc import format_video
from videotrans.util.gpus import getset_gpu

# Core job and media services
from videotrans.core.job_manager import (
    ActiveJobError,
    JobRecord,
    JobManager,
    run_prepare_review,
    JOBS,
)
from videotrans.core.media_store import (
    MediaRecord,
    MediaStore,
    MEDIA,
)

# API catalog and helpers
from videotrans.api.catalog import (
    FRONTEND_DIR,
    UPLOAD_DIR,
    OUTPUT_DIR,
    ASR_PROVIDERS,
    ASR_BY_TYPE,
    ASR_BY_ID,
    TIMING_MODES,
    TRANSLATION_MODES,
    TRANSLATION_PROVIDERS,
    TRANSLATION_BY_TYPE,
    TRANSLATION_BY_ID,
    TTS_PROVIDER_ALIASES,
)
from videotrans.api.task_params import (
    _required_index,
    _optional_index,
    _safe_volume,
    _translation_mode,
    build_task_params,
)
from videotrans.api.provider_helpers import (
    ensure_asr_configured,
    ensure_translation_configured,
    _save_asr_settings,
    _translation_models,
    _translation_snapshot,
    _save_translation_settings,
    test_asr_provider,
    test_translation_provider,
)
from videotrans.api.ocr_helpers import (
    NormalizedRoi,
    extract_ocr_segment_text,
)
from videotrans.api.routes.media import (
    EDIT_ASSETS,
    EDIT_ASSETS_LOCK,
)
from videotrans.api.app import (
    create_app,
    main,
    frontend_version,
    dev_reload_handler,
    index_handler,
    no_cache_middleware,
)

__all__ = [
    "create_app",
    "main",
    "frontend_version",
    "dev_reload_handler",
    "index_handler",
    "no_cache_middleware",
    "FRONTEND_DIR",
    "UPLOAD_DIR",
    "OUTPUT_DIR",
    "ASR_PROVIDERS",
    "ASR_BY_TYPE",
    "ASR_BY_ID",
    "TIMING_MODES",
    "TRANSLATION_MODES",
    "TRANSLATION_PROVIDERS",
    "TRANSLATION_BY_TYPE",
    "TRANSLATION_BY_ID",
    "TTS_PROVIDER_ALIASES",
    "JobRecord",
    "JobManager",
    "ActiveJobError",
    "MediaRecord",
    "MediaStore",
    "JOBS",
    "MEDIA",
    "EDIT_ASSETS",
    "EDIT_ASSETS_LOCK",
    "build_task_params",
    "ensure_asr_configured",
    "ensure_translation_configured",
    "test_asr_provider",
    "test_translation_provider",
    "NormalizedRoi",
    "extract_ocr_segment_text",
    "run_prepare_review",
    "role_menu",
    "format_video",
    "getset_gpu",
    "web",
    "recognition",
    "translator",
    "tts",
    "CancellationToken",
    "TaskRequest",
    "TaskResult",
    "TaskStatus",
    "EventKind",
    "TaskEvent",
    "run",
    "run_staged_asr",
    "run_staged_translation",
    "ROOT_DIR",
    "TEMP_DIR",
    "app_cfg",
    "app_params",
    "AUDIO_EXITS",
    "VIDEO_EXTS",
    "_required_index",
    "_optional_index",
    "_safe_volume",
    "_translation_mode",
    "_save_asr_settings",
    "_translation_models",
    "_translation_snapshot",
    "_save_translation_settings",
]

if __name__ == "__main__":
    main()
