# -*- coding: utf-8 -*-
"""VieNeu-TTS environment and Transformers compatibility setup."""

from __future__ import annotations

import logging

logger = logging.getLogger("videotrans.tts.vieneu_compat")

_setup_done = False


class VieneuWarningFilter(logging.Filter):
    """Filter out benign Transformers warning about custom 'vieneu_v3' model_type."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "vieneu_v3" in msg and "instantiate a model of type" in msg:
            return False
        return True


def setup_vieneu_environment() -> None:
    """
    Ensure VieNeu-TTS v3 model configuration is registered with Hugging Face AutoConfig
    and suppress benign model_type mismatch warnings.
    """
    global _setup_done
    if _setup_done:
        return
    _setup_done = True

    # 1. Register VieNeuV3TurboConfig with AutoConfig if available
    try:
        from transformers import AutoConfig
        from vieneu._v3_turbo_engine.configuration_v3_turbo import VieNeuV3TurboConfig

        AutoConfig.register("vieneu_v3", VieNeuV3TurboConfig)
    except Exception:
        pass

    # 2. Add logger filter to transformers.configuration_utils as defense in depth
    try:
        logging.getLogger("transformers.configuration_utils").addFilter(VieneuWarningFilter())
    except Exception:
        pass
