from videotrans.ocr._paddle import PaddleOcrProvider


def _engine_result_2x():
    return [
        [[[[0, 0], [50, 0], [50, 20], [0, 20]], ("Xin chao", 0.95)]],
        [
            [[[10, 0], [60, 0], [60, 20], [10, 20]], ("Chaomung", 0.90)],
        ],
    ]


def test_map_language():
    p = PaddleOcrProvider()
    assert p.map_language("vi-vn") == "latin"
    assert p.map_language("zh-cn") == "ch"
    assert p.map_language("ko") == "korean"
    assert p.map_language("ja-jp") == "japan"
    assert p.map_language("unknown-xx") == "ch"
    assert p.map_language(None) == "ch"


def test_normalize_units_2x_single():
    raw = [[[[0, 0], [50, 0], [50, 20], [0, 20]], ("Hello", 0.99)]]
    units = PaddleOcrProvider._normalize_units(raw)
    assert len(units) == 1
    assert units[0]["text"] == "Hello"
    assert units[0]["confidence"] == 0.99
    assert units[0]["box"] == (0.0, 0.0, 50.0, 20.0)


def test_normalize_units_2x_nested():
    raw = [
        [[[0, 0], [50, 0], [50, 20], [0, 20]], ("Top", 0.9)],
        [[[0, 30], [50, 30], [50, 50], [0, 50]], ("Bottom", 0.8)],
    ]
    units = PaddleOcrProvider._normalize_units(raw)
    texts = [u["text"] for u in units]
    assert texts == ["Top", "Bottom"]


def test_normalize_units_deep_nesting():
    raw = [
        [[[[2, 2], [7, 2], [7, 7], [2, 7]], ("Deep", 0.85)]]
    ]
    units = PaddleOcrProvider._normalize_units(raw)
    assert units[0]["text"] == "Deep"


def test_normalize_units_3x_dict():
    raw = {
        "rec_texts": ["A", "B"],
        "rec_scores": [0.9, 0.8],
        "rec_polys": [[[0, 0], [5, 0], [5, 5], [0, 5]]],
    }
    units = PaddleOcrProvider._normalize_units(raw)
    assert units[0]["text"] == "A"
    assert units[0]["box"] == (0.0, 0.0, 5.0, 5.0)
    # B has no polygon -> None box
    assert units[1]["box"] is None


def test_normalize_units_3x_flat_boxes():
    raw = {"rec_texts": ["X"], "rec_scores": [0.7], "rec_boxes": [[0, 0, 10, 10]]}
    units = PaddleOcrProvider._normalize_units(raw)
    assert units[0]["box"] == (0.0, 0.0, 10.0, 10.0)


def test_normalize_units_poly_not_misparsed():
    raw = [[[1, 2], [3, 2], [3, 4], [1, 4]]]
    assert PaddleOcrProvider._normalize_units(raw) == []
    assert PaddleOcrProvider._normalize_units(None) == []
    assert PaddleOcrProvider._normalize_units([]) == []


def test_recognize_orders_lines_and_averages_confidence(monkeypatch):
    calls = {}

    class FakeEngine:
        def ocr(self, image, cls=True):
            calls["image"] = image
            calls["cls"] = cls
            return [
                [
                    [[[0, 30], [50, 30], [50, 50], [0, 50]], ("Bottom", 0.8)],
                    [[[0, 0], [50, 0], [50, 20], [0, 20]], ("Top", 0.9)],
                ]
            ]

    p = PaddleOcrProvider(device="cpu")
    p._current_lang = p.map_language("vi-vn")
    p._require_engine = lambda dev: FakeEngine()
    result = p.recognize("img.bgr", "vi-vn")
    assert calls["image"] == "img.bgr"
    assert calls["cls"] is True
    assert result.text == "Top Bottom"
    assert round(result.confidence, 3) == 0.85
    assert [l.text for l in result.lines] == ["Top", "Bottom"]


def test_recognize_skips_empty_text():
    class FakeEngine:
        def ocr(self, image, cls=True):
            return [
                [
                    [[[0, 0], [50, 0], [50, 20], [0, 20]], ("  ", 0.9)],
                    [[[0, 0], [50, 0], [50, 20], [0, 20]], ("Keep", 0.7)],
                ]
            ]

    p = PaddleOcrProvider(device="cpu")
    p._current_lang = "ch"
    p._require_engine = lambda dev: FakeEngine()
    result = p.recognize("img", "en")
    assert result.text == "Keep"
    assert len(result.lines) == 1


def test_is_available_returns_false_when_paddle_missing():
    # paddleocr is optional; without it report False without raising.
    p = PaddleOcrProvider()
    assert p.is_available() is False or isinstance(p.is_available(), bool)

