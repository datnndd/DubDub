from videotrans import ChannelProvider
from videotrans.configure.config import tr
from videotrans.translator._constants import (
    CHATGPT_INDEX,
    DEEPSEEK_INDEX,
    GEMINI_INDEX,
    GOOGLE_INDEX,
)

_ID_NAME_DICT = {
    GOOGLE_INDEX: ChannelProvider(tr("Google"), imp="._google"),
    CHATGPT_INDEX: ChannelProvider(tr("OpenAI ChatGPT"), key_name="chatgpt_key", imp="._chatgpt"),
    GEMINI_INDEX: ChannelProvider("Gemini AI", key_name="gemini_key", imp="._gemini"),
    DEEPSEEK_INDEX: ChannelProvider("DeepSeek", key_name="deepseek_key", imp="._deepseek"),
}
TRANSLASTE_NAME_LIST = [provider.name for provider in _ID_NAME_DICT.values()]
