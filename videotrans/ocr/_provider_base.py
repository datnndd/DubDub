"""Abstract provider contract for OCR backends.

Pure interface only; no heavy imports. Concrete providers (e.g. the PaddleOCR
adapter, added in a later task) subclass ``BaseOcrProvider`` and implement
``recognize``.
"""
from videotrans.ocr._types import OcrResult


class BaseOcrProvider:
    """Minimal OCR provider interface.

    A provider owns model/component availability, source-language mapping,
    device selection, inference, and ordered line results.
    """

    def recognize(self, image, language) -> OcrResult:
        """Run OCR on ``image`` for the given ``language`` and return OcrResult."""
        raise NotImplementedError

    # Optional hooks -----------------------------------------------------
    def is_available(self) -> bool:
        """Return True when the provider and its models are ready to use."""
        return False

    def map_language(self, source_language_code):
        """Map a pyVideoTrans source language code to the provider's code."""
        return source_language_code

    def select_device(self, prefer):
        """Resolve the actual device to use given a preference (e.g. 'auto')."""
        return prefer
