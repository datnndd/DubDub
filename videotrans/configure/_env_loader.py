# -*- coding: utf-8 -*-
"""Zero-dependency .env loader for early-boot environment variables."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("videotrans.env_loader")

_LINE_REGEX = re.compile(
    r"""
    ^\s*
    (?:export\s+)?
    (?P<key>[A-Za-z_][A-Za-z0-9_]*)
    \s*=\s*
    (?P<val>.*?)
    \s*$
    """,
    re.VERBOSE,
)


def _parse_value(val: str) -> str:
    """Parse and unquote an env value string."""
    val = val.strip()
    if not val:
        return ""
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    # Remove inline comment if present outside quotes
    if " #" in val:
        val = val.split(" #", 1)[0].strip()
    return val


def parse_env_file(path: Path | str) -> dict[str, str]:
    """Parse key-value pairs from a file without modifying os.environ."""
    target = Path(path)
    if not target.is_file():
        return {}
    results: dict[str, str] = {}
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = _LINE_REGEX.match(line)
            if m:
                key = m.group("key")
                val = _parse_value(m.group("val"))
                results[key] = val
    except Exception as exc:
        logger.warning("Failed to parse env file %s: %s", target, exc)
    return results


def find_default_env_paths() -> list[Path]:
    """Return candidates for default .env configuration files."""
    from videotrans.configure._paths import ROOT_DIR

    candidates = [
        Path(ROOT_DIR) / ".env",
        Path.home() / ".config" / "dubdub" / "env",
    ]
    return [p for p in candidates if p.is_file()]


def load_env(env_path: Optional[Path | str] = None, override: bool = False) -> dict[str, str]:
    """Load environment variables from file into os.environ.

    If env_path is None, checks default locations (ROOT_DIR/.env, ~/.config/dubdub/env).
    Returns the dictionary of loaded variables.
    """
    loaded: dict[str, str] = {}
    paths_to_try: list[Path] = []
    if env_path is not None:
        p = Path(env_path)
        if p.is_file():
            paths_to_try.append(p)
    else:
        paths_to_try.extend(find_default_env_paths())

    for p in paths_to_try:
        pairs = parse_env_file(p)
        for k, v in pairs.items():
            if override or k not in os.environ:
                os.environ[k] = v
                loaded[k] = v
            elif k not in loaded and k in os.environ:
                loaded[k] = os.environ[k]
    return loaded
