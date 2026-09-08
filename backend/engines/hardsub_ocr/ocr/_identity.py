"""Local package/model identity for checkpoint compatibility; never downloads."""
import hashlib
from importlib import metadata, util
import os
from pathlib import Path


def fingerprint_files(paths):
    result = {}
    for path in sorted(set(Path(p).resolve() for p in paths)):
        with path.open('rb') as stream:
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        result[str(path)] = digest.hexdigest()
    return result


def model_identity(provider):
    packages = ('rapidocr', 'onnxruntime') if provider == 'rapidocr' else ('paddleocr', 'paddlepaddle')
    versions = {package: metadata.version(package) for package in packages}
    spec = util.find_spec(packages[0])
    package_root = Path(spec.origin).parent
    if provider == 'rapidocr':
        roots = [package_root / 'models']
        configs = [package_root / 'config.yaml', package_root / 'default_models.yaml']
    elif versions['paddleocr'].startswith('2.'):
        roots = [Path(os.environ.get('PADDLE_OCR_BASE_DIR', Path.home() / '.paddleocr')) / 'whl']
        configs = []
    else:
        roots = [Path(os.environ.get('PADDLE_PDX_CACHE_HOME', Path.home() / '.paddlex')) / 'official_models']
        configs = []
    # Conservative invalidation includes other installed OCR weights in these
    # caches, avoiding dependence on private inference-runtime path attributes.
    extensions = {'.onnx', '.pdmodel', '.pdiparams', '.json', '.yaml', '.yml', '.txt'}
    files = [p for root in roots if root.is_dir() for p in root.rglob('*')
             if p.is_file() and p.suffix in extensions]
    files.extend(p for p in configs if p.is_file())
    return dict(provider=provider, versions=versions, files=fingerprint_files(files))
