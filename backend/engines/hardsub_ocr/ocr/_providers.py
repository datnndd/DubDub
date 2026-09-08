"""RapidOCR/PaddleOCR adapters for the shared pyVideoTrans result contract."""
import math

from ._provider_base import BaseOcrProvider
from ._types import OcrLine, OcrResult
from ._text import order_lines


def normalize_result(raw, threshold=0.5):
    lines = []

    def add(text, score, polygon=None):
        confidence = float(score)
        if not math.isfinite(confidence) or confidence < threshold or not str(text or '').strip():
            return
        box = None
        if polygon is not None:
            points = polygon.tolist() if hasattr(polygon, 'tolist') else polygon
            if len(points) == 4 and isinstance(points[0], (int, float)):
                x, y, right, bottom = points
                box = (x, y, right - x, bottom - y)
            elif len(points):
                xs, ys = zip(*points)
                box = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        lines.append(OcrLine(str(text).strip(), confidence, box))

    def walk(value):
        if value is None:
            return
        if isinstance(value, OcrResult):
            for line in value.lines:
                if math.isfinite(line.confidence) and line.confidence >= threshold and line.text.strip():
                    lines.append(line)
            return
        if isinstance(value, dict) or hasattr(value, 'txts'):
            if isinstance(value, dict):
                texts, scores = value.get('rec_texts'), value.get('rec_scores')
                boxes = value.get('rec_polys')
                if boxes is None:
                    boxes = value.get('rec_boxes')
            else:
                texts, scores, boxes = value.txts, value.scores, value.boxes
            if texts is not None and scores is not None:
                for index, (text, score) in enumerate(zip(texts, scores)):
                    add(text, score, boxes[index] if boxes is not None and index < len(boxes) else None)
        elif isinstance(value, (list, tuple)):
            if len(value) == 3 and isinstance(value[1], str):
                add(value[1], value[2], value[0])
            elif len(value) == 2 and isinstance(value[1], (list, tuple)) and len(value[1]) == 2 and isinstance(value[1][0], str):
                add(value[1][0], value[1][1], value[0])
            else:
                for item in value:
                    walk(item)

    walk(raw)
    lines = order_lines(lines)
    return OcrResult(text=' '.join(line.text for line in lines),
                     confidence=sum(line.confidence for line in lines) / len(lines) if lines else 0.0,
                     lines=lines)


class EngineProvider(BaseOcrProvider):
    def __init__(self, engine, threshold=0.5):
        self.engine = engine
        self.threshold = threshold

    def recognize(self, image, language=None):
        return normalize_result(self.engine(image), self.threshold)
