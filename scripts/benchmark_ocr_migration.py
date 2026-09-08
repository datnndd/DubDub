"""Run the installed sidecar on a local video; retain measurements and cues."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from services.hardsub_ocr import run_ocr_client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('video')
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', choices=['rapidocr', 'paddleocr'], default='rapidocr')
    parser.add_argument('--refine', action='store_true')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'backend/engines/hardsub_ocr'
    manifest = dict(video=str(Path(args.video).resolve()), model=args.model, refine=args.refine,
                    source_sha256={str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
                                   for path in [source / 'main.py', *sorted((source / 'ocr').glob('*.py'))]})
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    started = time.monotonic()
    events = output / 'events.jsonl'
    with events.open('w', encoding='utf-8') as log:
        def progress(event):
            log.write(json.dumps(event, ensure_ascii=False) + '\n')
            log.flush()
            if event.get('frames_done', 0) % 100 == 0:
                print(json.dumps(event, ensure_ascii=True), flush=True)
        cues = run_ocr_client(args.video, crop=dict(left=0, top=.8, right=1, bottom=1),
                              model_id=args.model, refine=args.refine,
                              progress_cb=progress,
                              checkpoint_path=str(output / 'checkpoint.json'))
    result = dict(elapsed_seconds=time.monotonic() - started, cues=cues)
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(elapsed_seconds=result['elapsed_seconds'], cues=len(cues))), flush=True)


if __name__ == '__main__':
    main()
