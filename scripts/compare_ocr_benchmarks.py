"""Compare retained reference/migration OCR artifacts without rerunning models."""
import argparse
import difflib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True)
    parser.add_argument('--migration', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    reference = json.loads(Path(args.reference).read_text(encoding='utf-8'))
    migration = json.loads(Path(args.migration).read_text(encoding='utf-8'))
    old = reference.get('segments', reference.get('cues', []))
    new = migration.get('cues', migration.get('segments', []))
    old_text = [cue['text'] for cue in old]
    new_text = [cue['text'] for cue in new]
    matcher = difflib.SequenceMatcher(None, old_text, new_text, autojunk=False)
    differences = []
    exact = 0
    start_offsets = []
    for operation, a, b, c, d in matcher.get_opcodes():
        if operation == 'equal':
            exact += b - a
            for left, right in zip(old[a:b], new[c:d]):
                left_start = left.get('start_ms', left.get('start', 0) * 1000)
                right_start = right.get('start_ms', right.get('start', 0) * 1000)
                start_offsets.append(right_start - left_start)
        else:
            differences.append(dict(operation=operation, reference=old[a:b], migration=new[c:d]))
    report = dict(
        reference_elapsed_seconds=reference.get('elapsed_seconds'),
        migration_elapsed_seconds=migration.get('elapsed_seconds'),
        reference_cues=len(old), migration_cues=len(new), exact_text_matches=exact,
        sequence_similarity=matcher.ratio(), text_differences=differences,
        matched_start_offset_min_ms=min(start_offsets) if start_offsets else None,
        matched_start_offset_max_ms=max(start_offsets) if start_offsets else None,
        migration_overlaps=sum(a.get('end', a.get('end_ms', 0) / 1000) >
                               b.get('start', b.get('start_ms', 0) / 1000)
                               for a, b in zip(new, new[1:])),
    )
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
