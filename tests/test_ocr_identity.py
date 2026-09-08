import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engines.hardsub_ocr.ocr._identity import fingerprint_files


def test_weight_replacement_invalidates_identity_even_with_same_size_and_mtime(tmp_path):
    weight = tmp_path / 'weights.onnx'
    weight.write_bytes(b'original')
    stat = weight.stat()
    original = fingerprint_files([weight])
    assert fingerprint_files([weight]) == original
    weight.write_bytes(b'modified')
    os.utime(weight, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert weight.stat().st_size == stat.st_size
    assert fingerprint_files([weight]) != original
