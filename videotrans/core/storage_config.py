# -*- coding: utf-8 -*-
"""Storage path configuration, system root guards, metrics, and temp cache cleanup."""
from __future__ import annotations

import logging
import os
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from videotrans.configure._paths import ROOT_DIR
from videotrans.core.db import db_conn

logger = logging.getLogger("videotrans.storage_config")

DEFAULT_STORAGE: dict[str, Path] = {
    "output_dir": Path(ROOT_DIR) / "output",
    "uploads_dir": Path(ROOT_DIR) / "tmp" / "webui_uploads",
    "models_dir": Path(ROOT_DIR) / "models",
    "temp_dir": Path(ROOT_DIR) / "tmp",
}

_SYSTEM_ROOT_PATHS_UNIX = {
    "/",
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/lib",
    "/lib64",
    "/proc",
    "/root",
    "/sbin",
    "/sys",
    "/usr",
    "/var",
}

_SYSTEM_NAMES_WIN = {
    "windows",
    "winnt",
    "program files",
    "program files (x86)",
    "system32",
    "syswow64",
}


def _is_system_root_or_restricted(path: Path) -> bool:
    """Check if the given path is an OS root or protected system directory."""
    resolved = path.resolve()
    
    # Windows checks
    if sys.platform.startswith("win"):
        # Drive root e.g. C:\ or D:\
        if str(resolved).rstrip("\\/") == str(resolved.anchor).rstrip("\\/"):
            return True
        # Check system folders
        for part in resolved.parts:
            if part.lower() in _SYSTEM_NAMES_WIN:
                return True
        win_dir = os.environ.get("WINDIR") or "C:\\Windows"
        if resolved == Path(win_dir).resolve() or Path(win_dir).resolve() in resolved.parents:
            return True
    else:
        # Unix checks
        resolved_str = str(resolved)
        if resolved_str in _SYSTEM_ROOT_PATHS_UNIX:
            return True
        for sys_root in _SYSTEM_ROOT_PATHS_UNIX:
            if resolved_str == sys_root or resolved_str.startswith(sys_root + "/"):
                if sys_root in {"/var", "/tmp"}:
                    continue
                return True
    return False


def validate_storage_path(
    key: str,
    path_str: str,
    other_paths: Optional[dict[str, str]] = None,
) -> tuple[bool, str]:
    """Validate a candidate storage path for security, validity, and writability."""
    raw = (path_str or "").strip()
    if not raw:
        return False, f"Path for '{key}' cannot be empty."

    p = Path(raw)
    if not p.is_absolute():
        return False, f"Path '{raw}' must be an absolute path."

    try:
        resolved = p.resolve()
    except Exception as exc:
        return False, f"Invalid path '{raw}': {exc}"

    if _is_system_root_or_restricted(resolved):
        return False, f"Path '{raw}' is a protected system directory and cannot be used."

    # Prevent assigning storage directory to ROOT_DIR or ancestors of ROOT_DIR
    try:
        root_res = Path(ROOT_DIR).resolve()
        if resolved == root_res or resolved in root_res.parents:
            return False, f"Path '{raw}' cannot be the application root or parent directory."
    except Exception:
        pass

    # Check collisions with other storage directories
    if other_paths:
        for other_k, other_v in other_paths.items():
            if other_k == key:
                continue
            if other_v and other_v.strip():
                try:
                    other_res = Path(other_v.strip()).resolve()
                    if resolved == other_res:
                        return False, f"Path collides with '{other_k}'. Each storage area must use a distinct path."
                except Exception:
                    pass

    # Writability probe
    try:
        resolved.mkdir(parents=True, exist_ok=True)
        probe_file = resolved / f".write_probe_{uuid.uuid4().hex}.tmp"
        probe_file.write_text("ok", encoding="utf-8")
        probe_content = probe_file.read_text(encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        if probe_content != "ok":
            return False, f"Writability verification failed for '{raw}'."
    except Exception as exc:
        return False, f"Directory '{raw}' is not writable: {exc}"

    return True, ""


def get_storage_path(key: str) -> Path:
    """Retrieve configured storage path for key, falling back to default."""
    default_p = DEFAULT_STORAGE.get(key, Path(ROOT_DIR) / key)
    try:
        with db_conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (f"storage.{key}",)).fetchone()
        if row is not None and row[0]:
            p = Path(row[0].strip())
            if p.is_absolute():
                return p
    except Exception as exc:
        logger.debug("Failed to read storage.%s from database: %s", key, exc)
    return default_p


def set_storage_path(key: str, path_str: str) -> None:
    """Validate and persist storage path in database."""
    all_paths = get_all_storage_paths()
    all_paths[key] = path_str
    ok, err = validate_storage_path(key, path_str, all_paths)
    if not ok:
        raise ValueError(err)

    norm_path = str(Path(path_str.strip()).resolve())
    with db_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
            (f"storage.{key}", norm_path, time.time()),
        )

    # Sync with runtime configuration if output_dir
    if key == "output_dir":
        try:
            from videotrans.configure.config import settings
            settings.homedir = norm_path
        except Exception:
            pass


def get_all_storage_paths() -> dict[str, str]:
    """Return dictionary of all active storage paths as string paths."""
    result: dict[str, str] = {}
    for k in DEFAULT_STORAGE.keys():
        result[k] = str(get_storage_path(k).resolve())
    return result


def update_storage_paths(updates: dict[str, str]) -> dict[str, str]:
    """Validate all updated paths atomically and persist them."""
    current = get_all_storage_paths()
    new_set = {**current, **updates}

    # Validate all candidates together to check mutual collisions
    for k in updates.keys():
        if k not in DEFAULT_STORAGE:
            raise ValueError(f"Unknown storage key: {k}")
        ok, err = validate_storage_path(k, new_set[k], new_set)
        if not ok:
            raise ValueError(err)

    for k, v in updates.items():
        set_storage_path(k, v)

    return get_all_storage_paths()


def get_dir_size(path: Path) -> int:
    """Calculate total size of directory contents in bytes, ignoring unreadable files."""
    total = 0
    if not path.is_dir():
        return 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += get_dir_size(Path(entry.path))
            except (PermissionError, FileNotFoundError, OSError):
                continue
    except (PermissionError, FileNotFoundError, OSError):
        pass
    return total


def get_storage_metrics() -> dict[str, Any]:
    """Return storage paths, usage breakdown, and host disk free/total stats."""
    paths = get_all_storage_paths()
    output_dir = Path(paths["output_dir"])
    uploads_dir = Path(paths["uploads_dir"])
    models_dir = Path(paths["models_dir"])
    temp_dir = Path(paths["temp_dir"])

    usage = {
        "output_dir_bytes": get_dir_size(output_dir),
        "uploads_dir_bytes": get_dir_size(uploads_dir),
        "models_dir_bytes": get_dir_size(models_dir),
        "temp_dir_bytes": get_dir_size(temp_dir),
    }

    try:
        disk = shutil.disk_usage(output_dir if output_dir.exists() else Path(ROOT_DIR))
        usage["disk_total_bytes"] = disk.total
        usage["disk_free_bytes"] = disk.free
        usage["disk_used_bytes"] = disk.used
    except Exception:
        usage["disk_total_bytes"] = 0
        usage["disk_free_bytes"] = 0
        usage["disk_used_bytes"] = 0

    return {
        "paths": paths,
        "usage": usage,
    }


def clean_temp_cache() -> dict[str, Any]:
    """Safely clean temporary files excluding active job artifacts and protected storage areas."""
    temp_dir = get_storage_path("temp_dir")
    if not temp_dir.exists():
        return {"ok": True, "cleaned_bytes": 0, "cleaned_files": 0}

    # Gather protected paths that must NEVER be deleted
    protected_paths: set[Path] = set()
    for k in ("uploads_dir", "output_dir", "models_dir"):
        try:
            protected_paths.add(get_storage_path(k).resolve())
        except Exception:
            pass
    try:
        from videotrans.core.db import get_db_path
        protected_paths.add(get_db_path().resolve())
    except Exception:
        pass
    try:
        from videotrans.configure._paths import LOGS_DIR, ROOT_DIR
        protected_paths.add(Path(LOGS_DIR).resolve())
        protected_paths.add(Path(ROOT_DIR).resolve())
    except Exception:
        pass

    def _is_protected(target: Path) -> bool:
        try:
            t_res = target.resolve()
            for p in protected_paths:
                if t_res == p or p in t_res.parents or t_res in p.parents:
                    return True
        except Exception:
            return True
        return False

    # Find active jobs to avoid deleting their files
    active_ids: set[str] = set()
    try:
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT id, project_id FROM jobs WHERE status IN ('queued', 'running')"
            ).fetchall()
        for r in rows:
            if r[0]:
                active_ids.add(str(r[0]))
            if r[1]:
                active_ids.add(str(r[1]))
    except Exception as exc:
        logger.warning("Could not query active jobs for cache cleanup: %s", exc)

    curr_pid_str = str(os.getpid())
    cleaned_bytes = 0
    cleaned_files = 0

    try:
        for item in temp_dir.iterdir():
            # Skip hidden files and gitkeep
            if item.name.startswith(".") or item.name == ".gitkeep":
                continue
            # Skip active job files, current process dir, or protected paths
            if any(active_id in item.name for active_id in active_ids) or item.name == curr_pid_str or _is_protected(item):
                continue

            if item.is_file():
                try:
                    size = item.stat().st_size
                    item.unlink()
                    cleaned_bytes += size
                    cleaned_files += 1
                except (PermissionError, FileNotFoundError, OSError):
                    pass
            elif item.is_dir():
                # Clean subfolder contents while checking each item against protections & active jobs
                all_subs = sorted(item.rglob("*"), key=lambda p: len(p.parts), reverse=True)
                for sub in all_subs:
                    if _is_protected(sub) or any(active_id in sub.name for active_id in active_ids):
                        continue
                    if sub.is_file():
                        try:
                            size = sub.stat().st_size
                            sub.unlink()
                            cleaned_bytes += size
                            cleaned_files += 1
                        except (PermissionError, FileNotFoundError, OSError):
                            pass
                    elif sub.is_dir():
                        try:
                            os.rmdir(sub)
                        except (OSError, PermissionError):
                            pass
                try:
                    os.rmdir(item)
                except (OSError, PermissionError):
                    pass
    except Exception as exc:
        logger.warning("Error during temp cleanup: %s", exc)

    return {
        "ok": True,
        "cleaned_bytes": cleaned_bytes,
        "cleaned_files": cleaned_files,
    }
