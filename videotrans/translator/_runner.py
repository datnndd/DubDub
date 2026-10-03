from typing import Union, List, Type

from videotrans.configure.config import app_cfg, logger
from videotrans.translator._base import BaseTrans
from videotrans import get_class
from videotrans.translator._constants import GOOGLE_INDEX, AI_TRANS_CHANNELS
from videotrans.translator._registry import _ID_NAME_DICT
from videotrans.translator._lang_utils import get_source_target_code


def _check_google():
    import requests
    try:
        requests.head(f"https://translate.google.com", timeout=5)
    except Exception as e:
        logger.exception(f'检测google翻译失败{e}', exc_info=True)
        return False

    return True


# Translation: first extract target language code based on translation channel and target language
def run(*, translate_type=0,
        text_list=None,
        is_test=False,
        source_code=None,
        target_code=None,
        uuid=None,
        aisendsrt=None,
        event_sink=None,
        cancellation_token=None) -> Union[List, str, None]:
    translate_type = int(translate_type)
    # Under AI channels, target_language_name is the language name
    # Under other channels, it is the language code
    # source_code is the original language code
    target_language_name = target_code
    if translate_type in AI_TRANS_CHANNELS:
        # For AI channels, return natural language representation of target language
        _, target_language_name = get_source_target_code(show_target=target_code, translate_type=translate_type)
    kwargs = {
        "text_list": text_list,
        "target_language_name": target_language_name,
        "source_code": source_code if source_code and source_code not in ['-', 'No'] else 'auto',
        "target_code": target_code,
        "uuid": uuid,
        "is_test": is_test,
        "translate_type": translate_type,
        "aisendsrt": aisendsrt,
        "event_sink": event_sink,
        "cancellation_token": cancellation_token,
    }

    # Google is an explicit provider choice. Do not silently switch providers.
    if translate_type == GOOGLE_INDEX:
        if not app_cfg.proxy and _check_google() is not True:
            raise ConnectionError("Google Translate is unavailable. Configure a proxy or select another translation provider.")
        from videotrans.translator._google import Google
        return Google(**kwargs).run()

    _cls: Union[Type[BaseTrans], None] = get_class(translate_type,"translator",_ID_NAME_DICT)
    if _cls is None:
        raise RuntimeError(f'No this Translation Channel:{translate_type}')

    return _cls(**kwargs).run()#type:ignore
