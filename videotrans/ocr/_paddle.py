"""PaddleOCR local provider.

Defensive, optional-dependency adapter. Importing this module must NOT import
paddleocr/paddle/cv2/numpy/torch. All heavy imports happen lazily inside
``_ensure_engine`` so the rest of the repository can import ``videotrans.ocr``
without pulling Paddle. The provider implements the ``BaseOcrProvider`` contract
and is registered lazily from ``videotrans.ocr``.
"""
from typing import Optional

from videotrans.ocr._provider_base import BaseOcrProvider
from videotrans.ocr._types import OcrLine, OcrResult

# pyVideoTrans language code -> PaddleOCR rec model language.
_LANG_MAP = {
    "zh": "ch",
    "zh-cn": "ch",
    "zh-hans": "ch",
    "zh-tw": "chinese_cht",
    "zh-hant": "chinese_cht",
    "cht": "chinese_cht",
    "en": "en",
    "ja": "japan",
    "ja-jp": "japan",
    "ko": "korean",
    "ko-kr": "korean",
    "fr": "french",
    "de": "german",
    "ru": "cyrillic",
    "ar": "arabic",
    "es": "latin",
    "pt": "latin",
    "it": "latin",
    "vi": "latin",
    "vi-vn": "latin",
    "yue": "ch",
    "auto": "ch",
}

# PaddleOCR 2.x keys that appear in old-style result boxes can be ignored; we
# only read text + score. Key order within a text unit differs by version.
_PADDLE_MIN_CONF = 0.0


class PaddleOcrProvider(BaseOcrProvider):
    """Local PaddleOCR adapter with GPU-preference and CPU fallback."""

    def __init__(self, device: str = "auto", **kwargs) -> None:
        # store the normalized storage-mode engine key, init lazily
        self._prefer_device = device or "auto"
        self._engine = None
        self._active_device = None
        self._model_version = None
        self._init_error = None

    # -- availability -----------------------------------------------------
    def is_available(self) -> bool:
        try:
            self._ensure_win_dlls()
            import paddleocr  # noqa: F401
            return True
        except Exception:
            return False

    @staticmethod
    def _ensure_win_dlls():
        import sys
        if sys.platform == "win32":
            import os, site
            for s in site.getsitepackages():
                tlib = os.path.join(s, "torch", "lib")
                if os.path.exists(tlib):
                    try:
                        os.add_dll_directory(tlib)
                    except Exception:
                        pass

    def _require_engine(self, device: str):
        """Lazily import paddle and build a PaddleOCR engine.

        Prefers GPU when requested and possible, otherwise falls back to CPU.
        Disables OneDNN (mkldnn) operator fusion and IR optimization passes to prevent fused_conv2d crashes.
        """
        import os
        os.environ["FLAGS_use_onednn"] = "0"
        os.environ["FLAGS_use_mkldnn"] = "0"

        if self._engine is not None and self._active_device == device:
            return self._engine

        self._ensure_win_dlls()

        try:
            try:
                import torch  # noqa: F401
            except Exception:
                pass
            import paddle
            from paddleocr import PaddleOCR

            try:
                paddle.set_flags({"FLAGS_use_onednn": False, "FLAGS_use_mkldnn": False})
            except Exception:
                pass

            try:
                import paddle.inference as inference
                if not getattr(inference, "_videotrans_patched", False):
                    orig_cp = inference.create_predictor
                    def safe_create_predictor(config):
                        try:
                            config.disable_mkldnn()
                        except Exception:
                            pass
                        try:
                            config.disable_onednn()
                        except Exception:
                            pass
                        try:
                            config.switch_ir_optim(False)
                        except Exception:
                            pass
                        return orig_cp(config)
                    inference.create_predictor = safe_create_predictor
                    inference._videotrans_patched = True
            except Exception:
                pass
        except Exception as exc:
            self._init_error = str(exc)
            raise RuntimeError(
                "PaddleOCR optional component is not installed. Install "
                "paddleocr and paddlepaddle to use the Hard-Subtitle OCR source."
            ) from exc

        use_gpu = self._resolve_use_gpu(device)
        def _make_engine(gpu_mode: bool):
            kwargs = {
                "use_angle_cls": True,
                "lang": self._current_lang or "ch",
                "use_gpu": gpu_mode,
                "enable_mkldnn": False,
                "ir_optim": False,
                "show_log": False,
            }
            try:
                return PaddleOCR(**kwargs)
            except TypeError:
                kwargs.pop("enable_mkldnn", None)
                kwargs.pop("ir_optim", None)
                return PaddleOCR(**kwargs)

        try:
            engine = _make_engine(use_gpu)
            self._engine = engine
            self._active_device = "gpu" if use_gpu else "cpu"
            self._model_version = getattr(engine, "rec_model_version", None)
        except Exception as exc:
            if use_gpu:
                # GPU init/VRAM failure: retry on CPU once, keep notifying via
                # the returned error in _notice if caller inspects it.
                self._active_device = None
                try:
                    engine = _make_engine(False)
                    self._engine = engine
                    self._active_device = "cpu"
                    self._model_version = getattr(engine, "rec_model_version", None)
                except Exception as exc2:
                    self._init_error = str(exc2)
                    raise RuntimeError(f"PaddleOCR init failed: {exc2}") from exc2
            else:
                self._init_error = str(exc)
                raise RuntimeError(f"PaddleOCR init failed: {exc}") from exc
        return self._engine

    def _resolve_use_gpu(self, device) -> bool:
        if device in ("cpu", "cpu_only"):
            return False
        try:
            import paddle
            if paddle.is_compiled_with_cuda():
                return True
        except Exception:
            pass
        try:
            import torch
            if torch.cuda.is_available():
                return True
        except Exception:
            pass
        return False

    # -- device -----------------------------------------------------------
    def select_device(self, prefer: Optional[str] = None) -> str:
        """Resolve the actual device (\"gpu\"/\"cpu\") for a device preference."""
        if (prefer or self._prefer_device) in ("gpu", "cuda", "auto"):
            try:
                import paddle
                if paddle.is_compiled_with_cuda():
                    return "gpu"
            except Exception:
                pass
            try:
                import torch
                if torch.cuda.is_available():
                    return "gpu"
            except Exception:
                pass
        return "cpu"

    # -- language ---------------------------------------------------------
    def map_language(self, source_language_code):
        return _LANG_MAP.get(str(source_language_code or "").lower(), "ch")

    # -- recognition ------------------------------------------------------
    def recognize(self, image, language=None) -> OcrResult:
        """Run OCR on ``image`` (BGR ndarray or file path) and return OcrResult."""
        device = self.select_device(self._prefer_device)
        self._current_lang = self.map_language(language)
        engine = self._require_engine(device)

        try:
            raw = engine.ocr(image, cls=True)
        except Exception as exc:
            err_str = str(exc)
            if "OneDnnContext" in err_str or "onednn" in err_str.lower() or "fused_conv2d" in err_str:
                import os
                os.environ["FLAGS_use_onednn"] = "0"
                os.environ["FLAGS_use_mkldnn"] = "0"
                self._engine = None
                engine = self._require_engine("cpu")
                try:
                    raw = engine.ocr(image, cls=True)
                except Exception as exc2:
                    raise RuntimeError(f"PaddleOCR recognition failed: {exc2}") from exc2
            else:
                raise RuntimeError(f"PaddleOCR recognition failed: {exc}") from exc

        units = self._normalize_units(raw)
        ordered = sorted(units, key=self._unit_order_key)
        lines = []
        combined = []
        total_conf = 0.0
        rated = 0
        for unit in ordered:
            text = (unit.get("text") or "").strip()
            conf = float(unit.get("confidence") or 0.0)
            box = unit.get("box")
            if not text:
                continue
            combined.append(text)
            total_conf += conf
            rated += 1
            lines.append(OcrLine(text=text, confidence=conf, box=box))

        return OcrResult(
            text=" ".join(combined),
            confidence=(total_conf / rated) if rated else 0.0,
            lines=lines,
            timestamp_ms=0,
        )

    @staticmethod
    def _normalize_units(raw):
        """Normalize PaddleOCR 2.x list/3.x dict output to unit dicts.

        Each unit has keys text, confidence, box. box is the 4-element
        (x, y, w, h) when a 4-point polygon is available, else None.
        """
        if not raw:
            return []

        # 3.x dict form.
        if isinstance(raw, dict):
            texts = raw.get("rec_texts") or []
            scores = raw.get("rec_scores") or []
            polys = raw.get("rec_polys") or raw.get("rec_boxes") or []
            units = []
            for i, text in enumerate(texts):
                score = scores[i] if i < len(scores) else 0.0
                poly = polys[i] if i < len(polys) else None
                units.append(
                    {"text": text, "confidence": score, "box": _poly_to_xywh(poly)}
                )
            return units

        # 2.x form: nested lists keyed by image then per-line. Use a recursive
        # walk so page nesting depth does not matter; a line unit is any
        # [poly, (text, conf)] pair.
        if isinstance(raw, list):
            units = []
            _walk_paddle_lines(raw, units)
            return units

        return []

    @staticmethod
    def _unit_order_key(unit):
        """Return (y, x) sort key from a normalized box for line ordering."""
        box = unit.get("box")
        if not box:
            return (0.0, 0.0)
        try:
            return (float(box[1]), float(box[0]))
        except (TypeError, IndexError):
            return (0.0, 0.0)


def _poly_to_xywh(poly):
    """Convert a 4-point polygon (list of [x, y]) to (x, y, w, h) or None."""
    if not poly:
        return None
    try:
        if len(poly) == 4 and all(
            isinstance(p, (list, tuple)) and len(p) >= 2 for p in poly
        ):
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            x, y = min(xs), min(ys)
            return (x, y, max(xs) - x, max(ys) - y)
        if len(poly) >= 4:
            # flat [x0,y0,x1,y1,x2,y2,x3,y3]
            xs = [float(poly[i]) for i in range(0, len(poly), 2)]
            ys = [float(poly[i + 1]) for i in range(0, len(poly) - 1, 2)]
            x, y = min(xs), min(ys)
            return (x, y, max(xs) - x, max(ys) - y)
    except (TypeError, IndexError, ValueError):
        return None
    return None


def _walk_paddle_lines(node, out):
    """Recursively collect [poly, (text, conf)] line units from Paddle 2.x."""
    if not isinstance(node, (list, tuple)):
        return
    if len(node) == 2 and _looks_like_text_pair(node[1]):
        out.append(
            {"text": node[1][0], "confidence": node[1][1], "box": _poly_to_xywh(node[0])}
        )
        return
    for child in node:
        _walk_paddle_lines(child, out)


def _looks_like_text_pair(pair):
    """True when pair is (text_str, numeric_confidence)."""
    if not isinstance(pair, (list, tuple)) or len(pair) < 2:
        return False
    return isinstance(pair[0], str) and isinstance(pair[1], (int, float)) and not isinstance(pair[1], bool)
