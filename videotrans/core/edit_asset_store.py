"""In-memory ownership of uploaded assets used by final renders."""

from __future__ import annotations

import threading
from pathlib import Path


class EditAssetStore:
    def __init__(self) -> None:
        self._items: dict[str, Path] = {}
        self._lock = threading.Lock()

    def put(self, asset_id: str, path: Path) -> None:
        with self._lock:
            self._items[asset_id] = path

    def get(self, asset_id: str) -> Path | None:
        with self._lock:
            return self._items.get(asset_id)

    @property
    def items(self) -> dict[str, Path]:
        """Compatibility view for callers that only inspect the registry."""
        return self._items

    @property
    def lock(self) -> threading.Lock:
        return self._lock


EDIT_ASSET_STORE = EditAssetStore()
