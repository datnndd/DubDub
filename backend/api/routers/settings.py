"""Web application settings API."""
from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.logging_utils import log_safe
from api.dependencies import require_admin, require_admin_action

logger = logging.getLogger("omnivoice.api.settings")

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(require_admin)],
)


# ── Performance settings (INST-12) ────────────────────────────────────────
# Threat T-02-04: same admin guard as the hf-token endpoints via the
# router-level `require_admin` dep.


_TORCH_COMPILE_KEY = "perf.torch_compile_disabled"


class _TorchCompileBody(BaseModel):
    enabled: bool = Field(..., description="True to set TORCH_COMPILE_DISABLE=1 on engine subprocesses")


def _torch_compile_state() -> dict:
    import sys
    from services import settings_store

    raw = settings_store.get_text(_TORCH_COMPILE_KEY, "0")
    return {"enabled": raw == "1", "platform": sys.platform}


@router.get("/perf/torch-compile-disabled")
def get_torch_compile_disabled():
    """Return the current torch.compile-disabled toggle + the runtime platform.
    UI uses the platform to render the toggle disabled (with an explainer)
    on non-Windows hosts, since the OOM is Windows-specific (issue #65)."""
    return _torch_compile_state()


@router.put("/perf/torch-compile-disabled")
def set_torch_compile_disabled(body: _TorchCompileBody):
    """Persist the toggle. Honoured by `services.engine_env.build_engine_env()`
    which injects TORCH_COMPILE_DISABLE=1 on Windows when enabled."""
    from services import settings_store

    try:
        settings_store.set_text(_TORCH_COMPILE_KEY, "1" if body.enabled else "0")
    except Exception:
        logger.exception("set_torch_compile_disabled failed")
        raise HTTPException(status_code=500, detail="Failed to persist setting")
    return _torch_compile_state()


# ── Generation-history retention (Studio takes rail) ──────────────────────


class _HistoryRetentionBody(BaseModel):
    cap: int = Field(
        ...,
        ge=0,
        le=100000,
        description="Max takes kept before the oldest UNstarred ones (rows + WAVs) are pruned; 0 = unlimited",
    )


def _history_retention_state() -> dict:
    from api.routers.generation import DEFAULT_HISTORY_CAP, _history_cap

    return {"cap": _history_cap(), "default": DEFAULT_HISTORY_CAP}


@router.get("/history-retention")
def get_history_retention():
    """Current generation-history retention cap (Settings → Storage)."""
    return _history_retention_state()


@router.put("/history-retention")
def set_history_retention(body: _HistoryRetentionBody):
    """Persist the retention cap. Enforced after every generation: the oldest
    unstarred takes over the cap are pruned (rows + their audio files);
    starred takes are never pruned. 0 disables pruning entirely."""
    from core import prefs
    from api.routers.generation import HISTORY_CAP_PREF_KEY

    try:
        prefs.set_(HISTORY_CAP_PREF_KEY, int(body.cap))
    except Exception:
        logger.exception("set_history_retention failed")
        raise HTTPException(status_code=500, detail="Failed to persist setting")
    return _history_retention_state()


# ── LLM endpoint (parity program Wave 2.4 / §R2 rung 4) ───────────────────
# Focused configuration for the OpenAI-compatible LLM endpoint that powers
# cinematic translate, glossary auto-extract, and dictation refinement.
# Persistence rides the existing TRANSLATE_BASE_URL / TRANSLATE_API_KEY /
# TRANSLATE_MODEL env vars (already in system.py PERSISTENT_KEYS, restored
# at startup) so the resolution path in llm_backend/translator is unchanged.


class _LLMEndpointBody(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None  # None = leave unchanged; "" = clear


def _mask(secret: str | None) -> str | None:
    if not secret:
        return None
    return f"…{secret[-4:]}" if len(secret) > 4 else "set"


def _llm_endpoint_state():
    from services.llm_backend import OpenAICompatBackend

    ok, reason = OpenAICompatBackend.is_available()
    return {
        "base_url": os.environ.get("TRANSLATE_BASE_URL", ""),
        "model": os.environ.get("TRANSLATE_MODEL", ""),
        "api_key_masked": _mask(
            os.environ.get("TRANSLATE_API_KEY") or os.environ.get("OPENAI_API_KEY")
        ),
        "available": ok,
        "reason": None if ok else reason,
    }


@router.get("/llm-endpoint")
def get_llm_endpoint():
    """Current OpenAI-compatible LLM endpoint config + live availability."""
    return _llm_endpoint_state()


@router.put("/llm-endpoint")
def set_llm_endpoint(body: _LLMEndpointBody):
    """Persist base URL / model / API key for the OpenAI-compatible endpoint.

    Reuses the env-var persistence path (prefs.json, restored at startup):
    base_url -> TRANSLATE_BASE_URL, model -> TRANSLATE_MODEL,
    api_key -> TRANSLATE_API_KEY. A None field is left unchanged; an empty
    string clears it. Ollama ignores the key; vLLM / LM Studio require it.
    """
    from core.prefs import set_ as prefs_set, delete as prefs_delete

    mapping = {
        "TRANSLATE_BASE_URL": body.base_url,
        "TRANSLATE_MODEL": body.model,
        "TRANSLATE_API_KEY": body.api_key,
    }
    for env_key, val in mapping.items():
        if val is None:
            continue  # untouched
        val = val.strip()
        if val:
            os.environ[env_key] = val
            prefs_set(f"env.{env_key}", val)
        else:
            os.environ.pop(env_key, None)
            prefs_delete(f"env.{env_key}")
    # get_active_llm_backend() builds a fresh backend (and its OpenAI client
    # reads env at construction) on every call, so there's no singleton to
    # invalidate — the next translate/refine picks up the new values.
    return _llm_endpoint_state()


# ── Multi-provider LLM registry (Settings → LLM Providers) ────────────────
# Keys persist ENCRYPTED via settings_store.set_secret (never .env, never
# returned). base_url/model/account overrides are non-secret. Loopback-gated
# by the router dep, so LAN peers can't read masks or write keys.

class _LLMProviderBody(BaseModel):
    api_key: str | None = Field(None, description="API key; '' clears it, None leaves unchanged")
    base_url: str | None = None
    model: str | None = None
    account_id: str | None = Field(None, description="Cloudflare account id")
    make_active: bool = False


class _LLMActiveBody(BaseModel):
    provider: str = Field(..., description="provider id to activate")


@router.get("/llm-providers")
def list_llm_providers():
    """All providers with resolved base_url/model + whether a key is configured.

    Never returns key material — only `has_key`/`key_from_env` booleans.
    """
    from services import llm_providers
    return {
        "active": llm_providers.active_provider_id(),
        "providers": [llm_providers.describe(p) for p in llm_providers.all_providers()],
    }


@router.put("/llm-providers/{provider_id}")
def save_llm_provider(provider_id: str, body: _LLMProviderBody):
    """Save a provider's key (encrypted) + optional base_url/model/account.

    A None field is left unchanged; an empty api_key clears the stored key.
    """
    from services import llm_providers
    p = llm_providers.get_provider(provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider_id!r}")
    if body.api_key is not None:
        llm_providers.save_key(provider_id, body.api_key.strip())
    llm_providers.save_overrides(
        provider_id, base_url=body.base_url, model=body.model,
        account_id=body.account_id,
    )
    # An explicit save also claims the active slot when the user has never
    # chosen a provider (#963). Without this, a saved-and-tested local
    # provider (Ollama/LM Studio) evaporates on restart: active_provider_id()
    # deliberately excludes local providers from auto-select, so the plain
    # "Save" left nothing persisted to resolve. Gated on the STORED selection
    # only — an explicit prior choice is never stolen by a plain save, and an
    # unconfigured provider can't claim the slot.
    if body.make_active or (
        llm_providers.stored_active_provider_id() is None
        and llm_providers.is_configured(p)
    ):
        llm_providers.set_active_provider(provider_id)
    return list_llm_providers()


@router.post("/llm-providers/active")
def set_active_llm_provider(body: _LLMActiveBody):
    from services import llm_providers
    if llm_providers.get_provider(body.provider) is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {body.provider!r}")
    llm_providers.set_active_provider(body.provider)
    return list_llm_providers()


def _scrub_llm_detail(e: Exception, api_key: str | None) -> str:
    """Scrubbed, UI-safe failure text. scrub_text() covers env secrets and
    home paths — but a STORE-persisted key isn't in the env, and some
    providers echo the key in error bodies, so redact the exact resolved key
    explicitly before the generic pass."""
    from core.scrub import scrub_text
    detail = f"{type(e).__name__}: {e}"
    if api_key and api_key != "local" and len(api_key) >= 8:
        detail = detail.replace(api_key, "•••")
    return scrub_text(detail)


def _classify_llm_error(e: Exception) -> str:
    """Map a provider-call failure to an actionable kind the UI can localize.

    Kinds: auth (bad/missing key), not_found (model or endpoint path),
    rate_limit, network (DNS/conn/timeout), error (everything else).
    Status codes win when the OpenAI SDK provides one; exception-family
    names catch the non-HTTP failures (DNS, refused, TLS, timeout).
    """
    status = getattr(e, "status_code", None)
    if status in (401, 403):
        return "auth"
    if status == 404:
        return "not_found"
    if status == 429:
        return "rate_limit"
    name = type(e).__name__
    if name in ("APIConnectionError", "APITimeoutError", "ConnectError",
                "ConnectTimeout", "TimeoutError"):
        return "network"
    if name == "AuthenticationError":
        return "auth"
    if name == "NotFoundError":
        return "not_found"
    if name == "RateLimitError":
        return "rate_limit"
    return "error"


@router.post("/llm-providers/{provider_id}/test")
def test_llm_provider(provider_id: str):
    """One cheap round-trip against a provider to prove the key/URL work.

    Temporarily activates the provider for the probe by resolving its config
    directly (does not change the persisted active selection). Returns
    latency_ms plus, on failure, a classified ``kind`` (config / auth /
    not_found / rate_limit / network / error) so the UI shows an actionable,
    localizable message instead of a raw exception string.
    """
    import time as _time

    from services import llm_providers
    p = llm_providers.get_provider(provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider_id!r}")
    base_url = llm_providers.resolve_base_url(p)
    api_key = llm_providers.resolve_api_key(p)
    if not base_url:
        return {"ok": False, "kind": "config", "detail": "No Base URL set for this provider."}
    if not api_key:
        return {"ok": False, "kind": "config", "detail": "No API key configured for this provider."}
    t0 = _time.monotonic()
    try:
        from openai import OpenAI
        # max_retries=0: this is an interactive probe with a live spinner — the
        # SDK's default 2 automatic retries turn a 429/timeout into a ~34s hang.
        # Surface the first failure immediately instead.
        client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0)
        res = client.chat.completions.create(
            model=llm_providers.resolve_model(p),
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            timeout=20,
        )
        reply = (res.choices[0].message.content or "").strip()
        return {
            "ok": True,
            "model": llm_providers.resolve_model(p),
            "reply": reply[:80],
            "latency_ms": int((_time.monotonic() - t0) * 1000),
        }
    except Exception as e:  # noqa: BLE001 — classify without exposing diagnostics
        kind = _classify_llm_error(e)
        from core.public_errors import provider_failure
        failure = provider_failure(kind)
        # A successful local catalog probe proves the cached model is stale.
        # Invalidate it, but never include catalog or exception text in the
        # response: both are controlled by the provider.
        if kind == "not_found" and p.local:
            available = _local_models(base_url, api_key)
            if available is not None:
                llm_providers.forget_discovered_models(p.id)
        return {
            "ok": False,
            **failure,
            "latency_ms": int((_time.monotonic() - t0) * 1000),
        }


def _local_models(base_url: str, api_key: str):
    """Model ids a local OpenAI-compatible server currently serves.

    ``None`` when the listing itself failed, ``[]`` when it succeeded and the
    server has nothing loaded. The distinction is load-bearing: collapsing both
    to ``[]`` let the caller state "reports no loaded models" on a lookup that
    never happened, which is a confident wrong diagnosis in place of a vague
    right one (CodeRabbit). Only used to sharpen an error message, so it must
    never raise a second error on top of the first.
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0)
        return sorted(m.id for m in client.models.list(timeout=5))
    except Exception:  # noqa: BLE001
        return None


@router.get(
    "/llm-providers/{provider_id}/models",
    dependencies=[Depends(require_admin_action)],
)
def list_llm_provider_models(provider_id: str):
    """List model ids the provider's key can access (OpenAI-compat /models).

    Powers the model-picker datalist in Settings → LLM Providers so users
    don't have to guess model names. Read-only; failures return the same
    classified shape as /test; capped so a huge catalog can't bloat the UI.
    """
    from services import llm_providers
    p = llm_providers.get_provider(provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider_id!r}")
    base_url = llm_providers.resolve_base_url(p)
    api_key = llm_providers.resolve_api_key(p)
    if not base_url or not api_key:
        return {"ok": False, "kind": "config", "models": []}
    try:
        from openai import OpenAI
        # max_retries=0: interactive probe — fail fast, don't burn ~34s on the
        # SDK's default retry ladder when the key/URL is wrong (matches /test).
        client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0)
        ids = sorted(m.id for m in client.models.list(timeout=10))
        # Cap so a huge catalog can't bloat the datalist; flag the cap so the UI
        # can say "first 200 shown" rather than implying it's the full list.
        return {"ok": True, "models": ids[:200], "truncated": len(ids) > 200}
    except Exception as e:  # noqa: BLE001
        from core.public_errors import provider_failure
        return {
            "ok": False,
            **provider_failure(_classify_llm_error(e)),
            "models": [],
        }


# ── LLM Skills (Settings → LLM Skills) ─────────────────────────────────────
# Per-feature enable/route control for every LLM consumption point. Each
# skill can be toggled off (degrades exactly like "no LLM configured") or
# routed to a specific provider (local Ollama/LM Studio vs a remote key)
# instead of the one global active provider. Loopback-gated (router dep).


class _LLMSkillBody(BaseModel):
    enabled: bool | None = Field(None, description="None leaves the toggle unchanged")
    provider_override: str | None = Field(
        None,
        description="provider id to route this skill to; '' or null clears "
                    "it (skill follows the active provider). Omit to leave "
                    "unchanged.",
    )


@router.get("/llm-skills")
def list_llm_skills():
    """Every LLM skill with its toggle, routing, and resolved ready status."""
    from services import llm_skills
    return {"skills": [llm_skills.describe(s.id) for s in llm_skills.all_skills()]}


@router.put("/llm-skills/{skill_id}")
def set_llm_skill(skill_id: str, body: _LLMSkillBody):
    """Toggle a skill and/or set its provider routing.

    Field semantics match the providers PUT: an omitted field is left
    unchanged; ``provider_override: ""``/``null`` clears the override.
    404 for an unknown skill or an unknown provider id.
    """
    from services import llm_skills
    if llm_skills.get_skill(skill_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown LLM skill {skill_id!r}")
    kwargs = {}
    if body.enabled is not None:
        kwargs["enabled"] = body.enabled
    if "provider_override" in body.model_fields_set:
        kwargs["provider_override"] = body.provider_override
    try:
        if kwargs:
            llm_skills.configure_skill(skill_id, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return list_llm_skills()


# ── Storage: configurable models directory (#64) ──────────────────────────
# Where HuggingFace / Torch download model weights. The user's choice is
# persisted durably to the per-user env file as OMNIVOICE_CACHE_DIR, which
# main.py maps to HF_HOME / HF_HUB_CACHE / TORCH_HOME at startup. That env file
# is the *single source of truth*: PUT writes it, GET reads it back — there is
# no second store to diverge from. Takes effect on the next backend restart
# (a storage-location change can't safely move an in-use cache mid-process).
_MODELS_DIR_ENV = "OMNIVOICE_CACHE_DIR"


def _default_models_dir() -> str:
    """huggingface_hub's default cache root, honoring XDG_CACHE_HOME on Linux
    (matches HF so GET reports the *true* default the backend would use)."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "huggingface")


def _effective_models_dir() -> str:
    return (
        os.environ.get("HF_HUB_CACHE")
        or os.environ.get("HUGGINGFACE_HUB_CACHE")
        or os.environ.get("HF_HOME")
        or _default_models_dir()
    )


@router.get("/storage/models-dir")
def get_models_dir():
    """Current models directory: the persisted choice (from the durable env
    file — the same value main.py reads at startup), what's effective in this
    process, and the platform default."""
    from core import user_env

    configured = user_env.get_user_env(_MODELS_DIR_ENV) or None
    return {
        "configured": configured,
        "effective": _effective_models_dir(),
        "default": _default_models_dir(),
        "restart_required": False,
    }


# ── Storage report (Settings → Storage) ────────────────────────────────────
# Per-volume disk totals + du-style sizes for everything the app owns (HF
# model cache, app data subtotals, engine venvs, temp files) with server-side
# warnings. Heavy directory walks run in a worker thread with per-category
# deadlines and a 5-minute in-process cache (services.storage_report), so the
# endpoint stays cheap on repeat Settings visits. Loopback-gated via the
# router-level dep like every sibling.


@router.get("/storage")
async def get_storage_report(refresh: bool = Query(False)):
    """Disk + per-category storage usage for the Settings → Storage panel.

    `refresh=1` bypasses the 5-minute cache and rescans. `min_free_gb`
    reuses the setup wizard's constant so both surfaces warn at the same
    threshold.
    """
    from api.routers.setup.wizard import MIN_FREE_GB
    from core.config import DATA_DIR
    from services import storage_report

    try:
        return await asyncio.to_thread(
            storage_report.get_report,
            data_dir=DATA_DIR,
            hf_cache_dir=_effective_models_dir(),
            app_venv=storage_report.default_app_venv(),
            min_free_gb=MIN_FREE_GB,
            refresh=refresh,
        )
    except Exception:
        logger.exception("storage report failed")
        raise HTTPException(status_code=500, detail="Failed to compute storage report")


@router.post("/storage/temp/clear")
async def clear_temp_files():
    """Delete VoiceStudio-owned temp files (Settings → Storage → Temporary files).

    Removes only the ``omnivoice*`` entries in the OS temp dir — the exact
    population the storage report's "temp" category counts — and invalidates
    the cached report so the next scan reflects the reclaimed space. Partial
    failures (files held open by a running job) are returned per entry.
    """
    from services import storage_report

    try:
        result = await asyncio.to_thread(storage_report.clear_temp)
        storage_report.clear_cache()
        return result
    except Exception:
        logger.exception("clear temp files failed")
        raise HTTPException(status_code=500, detail="Failed to clear temporary files")


# ── HF mirror endpoint (parity program Wave 4.3 / §R4 c) ──────────────────
# Restricted-network users (e.g. behind the Great Firewall) need to point
# huggingface_hub at a mirror. HF reads HF_ENDPOINT at import time, so a
# change takes effect on the next backend start — persisted to the durable
# per-user env so it survives Tauri/Finder launches that don't inherit a
# shell. Loopback-gated via the router dep.

_HF_ENDPOINT_ENV = "HF_ENDPOINT"

# A few well-known mirrors, surfaced as quick-picks in the UI. hf-mirror.com
# is the community mirror most-used in China; the official endpoint clears it.
_HF_MIRROR_PRESETS = [
    {"label": "Hugging Face (official)", "url": ""},
    {"label": "hf-mirror.com (community, China)", "url": "https://hf-mirror.com"},
]


class _HFMirrorBody(BaseModel):
    url: str = Field("", description="HF_ENDPOINT URL; empty string clears it (official endpoint)")
    mode: str | None = Field(
        None,
        description=(
            "'auto' switches to automatic endpoint selection (clears any "
            "explicit endpoint); 'manual' (or omitted — back-compat with older "
            "clients) pins the given url as an explicit choice."
        ),
    )


def _hf_mirror_state() -> dict:
    """The full GET /hf-mirror payload. Auto info comes from the CACHED race
    decision only — reading settings never probes the network."""
    from core import user_env
    from services import endpoint_race

    configured = user_env.get_user_env(_HF_ENDPOINT_ENV) or ""
    try:
        mode = "manual" if configured else endpoint_race.mode()
        auto = endpoint_race.cached_decision() if mode == "auto" else None
        opt_out = endpoint_race.env_opt_out()
    except Exception:  # a broken prefs file must never 500 the settings page
        logger.exception("hf-mirror auto state unavailable")
        mode, auto, opt_out = "manual", None, False
    return {
        # The value that will apply after restart (persisted), and what's
        # live in this process (env may differ until then).
        "configured": configured,
        "effective": os.environ.get(_HF_ENDPOINT_ENV, ""),
        "presets": _HF_MIRROR_PRESETS,
        # Automatic endpoint selection (services.endpoint_race): "auto" only
        # when nothing explicit is configured anywhere. `auto` is the cached
        # race decision ({endpoint, reachable, latency_ms, checked_at,
        # results}) or null when never raced / in manual mode.
        "mode": mode,
        "auto": auto,
        "auto_opt_out": opt_out,
    }


@router.get("/hf-mirror")
def get_hf_mirror():
    return _hf_mirror_state()


@router.put("/hf-mirror")
def set_hf_mirror(body: _HFMirrorBody):
    from core import user_env
    from services import endpoint_race

    mode = (body.mode or "manual").strip().lower()
    if mode not in {"auto", "manual"}:
        raise HTTPException(status_code=400, detail="mode must be 'auto' or 'manual'")
    # Auto mode = no explicit endpoint anywhere; a persisted endpoint would
    # read as an explicit choice, so switching to Auto clears it (plus the
    # `hf_endpoint` pref fallback the download paths resolve).
    url = "" if mode == "auto" else (body.url or "").strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Mirror URL must start with http(s)://")
    # Compare against the currently-persisted value (normalised the same way) so
    # a no-op save doesn't nag the user to restart. Only a real change to the
    # persisted endpoint can require a restart.
    previous = (user_env.get_user_env(_HF_ENDPOINT_ENV) or "").strip().rstrip("/")
    changed = url != previous
    try:
        if url:
            user_env.set_user_env(_HF_ENDPOINT_ENV, url)
            os.environ[_HF_ENDPOINT_ENV] = url  # best-effort for new downloads this session
        else:
            user_env.unset_user_env(_HF_ENDPOINT_ENV)
            os.environ.pop(_HF_ENDPOINT_ENV, None)
        from core import prefs
        if not url:
            # No endpoint anywhere: clearing to official (manual) or switching
            # to auto must also drop the legacy `hf_endpoint` pref fallback —
            # otherwise it silently keeps resolving as an explicit mirror and
            # "switch to official" doesn't actually switch.
            prefs.delete("hf_endpoint")
        endpoint_race.set_mode_pref(mode)
    except Exception:
        logger.exception("set_hf_mirror failed")
        raise HTTPException(status_code=500, detail="Failed to persist mirror setting")
    # An endpoint change invalidates the failed-recently install cooldowns: the
    # user's next action is "retry that download on the new endpoint", and a
    # 429 would dead-end the wizard's switch-and-retry flow.
    try:
        from api.routers.setup.download import clear_install_cooldowns

        clear_install_cooldowns()
    except Exception:  # pragma: no cover — cooldown reset must never fail the save
        logger.warning("could not clear install cooldowns after mirror change", exc_info=True)
    if mode == "auto":
        # Freshly chosen Auto should show a real pick immediately — race now
        # unless a fresh cached decision already exists (probes are ≤3 s and
        # this is an explicit user action, not a hot path).
        try:
            endpoint_race.ensure_decision()
        except Exception:
            logger.exception("endpoint race after switching to auto failed")
    # Model Store downloads pick up the new mirror immediately — the download
    # path resolves the endpoint per-call and we updated os.environ above. Only
    # transformers-side model *loads* (which read HF_ENDPOINT at import time)
    # need a restart, so restart_required is True ONLY when the value actually
    # changed — a no-op re-save never asks for a restart.
    return {**_hf_mirror_state(), "restart_required": changed}


@router.post("/hf-mirror/test")
def test_hf_mirror():
    """Re-run the endpoint race now (the Auto panel's "Test again").

    Forces fresh probes and re-caches the decision. In manual mode this is a
    no-op (an explicit endpoint is never auto-switched) — the response simply
    reflects the current state."""
    from services import endpoint_race

    try:
        endpoint_race.ensure_decision(force=True)
    except Exception:
        logger.exception("hf-mirror endpoint test failed")
        raise HTTPException(status_code=500, detail="Endpoint test failed")
    return _hf_mirror_state()


# ── Deepgram Cloud ASR ────────────────────────────────────────────────────────


class _ASRDeepgramBody(BaseModel):
    model: str | None = None
    api_key: str | None = Field(None, description="'' clears it, None leaves unchanged")


@router.get("/asr-deepgram")
def get_asr_deepgram():
    from services import asr_backend

    return {
        "model": asr_backend.resolve_deepgram_model(),
        "has_key": asr_backend.deepgram_has_key(),
    }


@router.put("/asr-deepgram")
def set_asr_deepgram(body: _ASRDeepgramBody):
    from services import asr_backend, settings_store

    if body.model is not None:
        settings_store.set_text(
            asr_backend._ASR_DEEPGRAM_MODEL_KEY, body.model.strip() or "nova-2"
        )
    if body.api_key is not None:
        settings_store.set_secret(
            asr_backend._ASR_DEEPGRAM_SECRET_NAME, body.api_key.strip()
        )
    return get_asr_deepgram()


@router.post("/asr-deepgram/test")
def test_asr_deepgram():
    """Cheap connectivity and auth probe for Deepgram Cloud ASR."""
    from services import asr_backend

    return asr_backend.probe_deepgram_server()


# ── Updates panel: shipped changelog + pre-migration DB backup state ────────
# (feat/safe-updates). Both are read-only, local-first surfaces for
# Settings → Updates: the "What's new" viewer reads the CHANGELOG.md that
# ships with the app, and the backup line shows the newest pre-migration
# snapshot written by core.db_backup before `alembic upgrade head` runs.


@router.get("/changelog")
def get_changelog(limit_versions: int = Query(5, ge=1, le=50)):
    """Structured release notes from the shipped CHANGELOG.md (newest first).

    Bullets are raw markdown-lite (bold leads, `code`, (#NNN) refs) — the
    frontend renders them safely without HTML. `available: false` when this
    install has no changelog (never an error: the viewer just hides)."""
    from core import changelog

    path = changelog.changelog_path()
    if not path:
        return {"available": False, "releases": []}
    try:
        with open(path, encoding="utf-8") as fh:
            releases = changelog.parse_changelog(fh.read(), limit_versions)
    except Exception:
        logger.exception("changelog parse failed")
        return {"available": False, "releases": []}
    return {"available": bool(releases), "releases": releases}


@router.get("/db-backup")
def get_db_backup_state():
    """Newest pre-migration database backup (or none yet). Feeds the
    "your data is backed up before every update" line in Settings → Updates."""
    from core import db_backup
    from core.config import DB_PATH

    latest = db_backup.latest_backup(DB_PATH)
    return {
        "available": latest is not None,
        "latest": latest,
        "count": len(db_backup.list_backups(DB_PATH)),
        "keep": db_backup.KEEP_BACKUPS,
    }


# ── Opt-in product analytics (hardened; default OFF) ───────────────────────
# Local-first means silence is not consent: analytics runs only when the user
# explicitly turns it on AND the build ships a destination token. See
# core/analytics.py for the three rules (opt-in, no exception autocapture,
# allowlisted metadata only).

class _AnalyticsBody(BaseModel):
    enabled: bool = Field(..., description="User's explicit choice. Default is OFF.")


@router.get("/analytics")
def get_analytics():
    from core import analytics

    return {
        "enabled": analytics.enabled(),
        "opted_in": analytics.user_opted_in(),
        # True for source builds too since #1193 (in-repo default token; env/baked
        # overrides). False only for a destination-less build, where the UI can
        # say so instead of offering a toggle that does nothing.
        "available": analytics.token_configured(),
        # Whether the user has ever been explicitly asked (first-run consent step
        # or the one-time banner). The UI uses this to ask exactly once — it never
        # enables anything by itself.
        "prompted": analytics.user_prompted(),
    }


@router.put("/analytics")
def set_analytics(body: _AnalyticsBody):
    from core import analytics

    analytics.set_opted_in(body.enabled)
    return get_analytics()
