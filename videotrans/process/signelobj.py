# -*- coding: utf-8 -*-
"""Compatibility alias for videotrans.process.process_manager."""

from .process_manager import (
    GlobalProcessManager,
    AsyncResultFutureWrapper,
    WorkerContext,
)

__all__ = [
    "GlobalProcessManager",
    "AsyncResultFutureWrapper",
    "WorkerContext",
]
