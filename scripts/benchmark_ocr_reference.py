"""Benchmark an explicitly supplied pyVideoTrans checkout, without editing it.

Run this with the reference project's Python interpreter. This is a validation
tool only; the application never imports from the reference checkout.
"""
import argparse
from dataclasses import asdict
import importlib.metadata
import json
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', required=True)
    parser.add_argument('--video', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.repository).resolve()))
    from videotrans.ocr._paddle import PaddleOcrProvider
    from videotrans.ocr._scanner import OcrScanner
    from videotrans.ocr._types import OcrConfig
    from videotrans.ocr._frame_source import sampled_frame_iter, probe_duration

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = OcrConfig(roi=(0, .8, 1, .2), language='zh', device='cpu')
    provider = PaddleOcrProvider(device='cpu')
    duration = probe_duration('ffmpeg', args.video)
    started = time.monotonic()
    with (output / 'events.jsonl').open('w', encoding='utf-8') as log:
        def progress(event):
            event = dict(event, elapsed_seconds=time.monotonic() - started)
            log.write(json.dumps(event, ensure_ascii=False) + '\n')
            log.flush()
            print(json.dumps(event, ensure_ascii=True), flush=True)
        scanner = OcrScanner(provider, config, on_progress=progress)
        segments = scanner.scan(sampled_frame_iter('ffmpeg', args.video, duration_ms=duration),
                                duration_ms=duration, resume=False)
    result = dict(elapsed_seconds=time.monotonic() - started, segments=[asdict(s) for s in segments],
                  versions={name: importlib.metadata.version(name) for name in ('paddleocr', 'paddlepaddle')})
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(elapsed_seconds=result['elapsed_seconds'], segments=len(segments))), flush=True)


if __name__ == '__main__':
    main()
