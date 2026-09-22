import subprocess
import sys
from pathlib import Path


def test_supported_runtime_imports_without_pyside6():
    root = Path(__file__).parents[1]
    script = r'''
import builtins

real_import = builtins.__import__

class ForbiddenQtImport(RuntimeError):
    pass

def block_qt(name, *args, **kwargs):
    if name == "PySide6" or name.startswith("PySide6."):
        raise ForbiddenQtImport(name)
    return real_import(name, *args, **kwargs)

builtins.__import__ = block_qt

try:
    __import__("PySide6.QtCore")
except ForbiddenQtImport:
    pass
else:
    raise AssertionError("the no-Qt guard did not detect a forbidden import")

# Verify that internal package modules import cleanly in isolation BEFORE webui is loaded
from videotrans import recognition, translator, tts, ocr
from videotrans.task import orchestrator, speech2text, dubbing, trans_create
from videotrans.api import app
from videotrans.core import project_store, job_store, job_manager, media_store
from videotrans.process import process_manager

# Verify that top-level CLI and WebUI entrypoints also import cleanly
import cli
import webui
'''

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
