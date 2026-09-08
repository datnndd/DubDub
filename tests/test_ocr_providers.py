import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engines.hardsub_ocr.ocr._providers import normalize_result


def test_provider_shapes_share_order_confidence_and_text():
    boxes = np.array([[[0, 20], [20, 20], [20, 30], [0, 30]],
                      [[0, 0], [20, 0], [20, 10], [0, 10]]])
    results = [
        SimpleNamespace(txts=['second', 'first'], scores=np.array([.8, .9]), boxes=boxes),
        {'rec_texts': ['second', 'first'], 'rec_scores': np.array([.8, .9]), 'rec_polys': boxes},
        [[boxes[0], ('second', .8)], [boxes[1], ('first', .9)]],
        ([[boxes[0], 'second', .8], [boxes[1], 'first', .9]], [0.1, 0.2]),
    ]
    for raw in results:
        result = normalize_result(raw)
        assert result.text == 'first second'
        assert result.confidence == pytest.approx(.85)


def test_empty_and_low_confidence_do_not_reuse_previous_text():
    for raw in [None, [], {'rec_texts': ['noise'], 'rec_scores': [.1]},
                {'rec_texts': ['bad'], 'rec_scores': [float('nan')]}]:
        assert normalize_result(raw).text == ''
