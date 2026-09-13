"""Lifecycle inventory for the web-only provider boundary."""
from __future__ import annotations

import logging
import services.model_manager as mm
from services.model_manager import get_best_device

logger = logging.getLogger("omnivoice.model_lifecycle")


def _active_tts_id() -> str | None:
    try:
        from services.tts_backend import active_backend_id
        return active_backend_id()
    except Exception:
        return None


def _tts_vram_mb() -> float:
    try:
        torch = mm._lazy_torch()
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024 ** 2)
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            allocated = getattr(torch.mps, "driver_allocated_memory", None)
            if allocated:
                return allocated() / (1024 ** 2)
    except Exception:
        pass
    return 0.0


def list_loaded() -> dict:
    models: list[dict] = []
    active = _active_tts_id()
    if mm.model is not None:
        try:
            device = str(next(mm.model.parameters()).device)
        except Exception:
            device = get_best_device()
        models.append({
            "id": "tts", "name": "OmniVoice TTS",
            "checkpoint": mm.resolve_omnivoice_checkpoint(), "device": device,
            "vram_mb": round(_tts_vram_mb(), 1), "unloadable": True,
            "engine_id": "omnivoice",
            "is_active_engine": active == "omnivoice" if active else None,
        })
    degraded_sources: list[str] = []
    try:
        from services.subprocess_backend import list_live_sidecars
        for sidecar in list_live_sidecars():
            if sidecar.get("id") != "vienue":
                continue
            models.append({
                "id": "sidecar:vienue", "name": "VieNeuTTS",
                "checkpoint": "vienue", "device": get_best_device(),
                "vram_mb": round(float(sidecar.get("vram_mb") or 0), 1),
                "unloadable": True, "engine_id": "vienue",
                "is_active_engine": active == "vienue" if active else None,
            })
    except Exception:
        logger.warning("Loaded-model inventory unavailable for subprocess sidecars")
        degraded_sources.append("sidecars")
    system: dict = {}
    try:
        from services.memory_budget import available_memory, low_memory_warning
        system = available_memory()
        warning = low_memory_warning()
        if warning:
            system["warning"] = warning
    except Exception:
        pass
    return {"models": models, "count": len(models), "system": system,
            "degraded_sources": degraded_sources}


async def unload(model_id: str) -> dict:
    if model_id == "tts":
        async with mm._model_lock:
            success = mm.unload_shared_model()
        return {"unloaded": "tts", "success": success,
                **({} if success else {"reason": "not loaded"})}
    if model_id in {"sidecars", "sidecar:vienue"}:
        from services.subprocess_backend import unload_all_sidecars, unload_sidecar
        count = unload_all_sidecars() if model_id == "sidecars" else unload_sidecar("vienue")
        return {"unloaded": model_id, "success": count > 0, "count": count,
                **({} if count else {"reason": "not running or busy"})}
    raise ValueError(f"Unknown model id: {model_id}")


async def unload_all() -> dict:
    unloaded: list[str] = []
    if mm.unload_shared_model():
        unloaded.append("tts")
    try:
        from services.subprocess_backend import unload_sidecar
        if unload_sidecar("vienue"):
            unloaded.append("sidecar:vienue")
    except Exception:
        logger.debug("VieNeuTTS unload unavailable", exc_info=True)
    mm.free_vram()
    return {"unloaded": unloaded, "success": True, "count": len(unloaded)}


def free_vram() -> None:
    mm.free_vram()
