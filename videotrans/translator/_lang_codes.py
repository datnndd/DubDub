from pathlib import Path

from videotrans.configure.config import tr, ROOT_DIR, logger

# subtitles language code  https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes
#  MP4 video uses 3-letter T format (ISO-639-2/T), MKV uses 3-letter B format (ISO 639-2/B)
# Tencent translation https://cloud.tencent.com/document/api/551/15619
# Google translation https://translate.google.com/
# Baidu translation https://fanyi.baidu.com/
# deepl  https://deepl.com/
# microsoft https://www.bing.com/translator?mkt=zh-CN
# Alibaba machine translation
# https://help.aliyun.com/zh/machine-translation/developer-reference/machine-translation-language-code-list?spm=a2c4g.11186623.help-menu-30396.d_4_4.4bda2b009oye8y
# qwen-mt https://help.aliyun.com/zh/model-studio/machine-translation?spm=5176.30275541.J_ZGek9Blx07Hclc3Ddt9dg.1.69bf2f3dfuEVHs&scm=20140722.S_help@@%E6%96%87%E6%A1%A3@@2860790._.ID_help@@%E6%96%87%E6%A1%A3@@2860790-RL_qwen~DAS~mt-LOC_2024SPHelpResult-OR_ser-PAR1_0bc3b4ad17766086921897050e02b4-V_4-PAR3_o-RE_new5-P0_0-P1_0#038d2865bbydc
# m2m100  https://github.com/ymoslem/DesktopTranslator/blob/main/utils/m2m_languages.json
LANGNAME_DICT = {
    "en": tr("English"),
    "zh-cn": tr("Simplified Chinese"),
    "zh-tw": tr("Traditional Chinese"),
    "fr": tr("French"),
    "de": tr("German"),
    "ja": tr("Japanese"),
    "ko": tr("Korean"),
    "ru": tr("Russian"),
    "es": tr("Spanish"),
    "th": tr("Thai"),
    "it": tr("Italian"),
    "el": tr("Greek"),
    "pt": tr("Portuguese"),
    "vi": tr("Vietnamese"),
    "ar": tr("Arabic"),
    "tr": tr("Turkish"),
    "hi": tr("Hindi"),
    "hu": tr("Hungarian"),
    "uk": tr("Ukrainian"),
    "id": tr("Indonesian"),
    "ms": tr("Malay"),
    "kk": tr("Kazakh"),
    "cs": tr("Czech"),
    "pl": tr("Polish"),
    "nl": tr("Dutch"),
    "sv": tr("Swedish"),
    "he": tr("Hebrew"),
    "bn": tr("Bengali"),
    "fa": tr("Persian"),
    "fil": tr("Filipino"),
    "ur": tr("Urdu"),
    "nb": tr("Norway"),  # Norwegian Bokmål
    "yue": tr("Cantonese"),
    "km": tr("Khmer"),  # Khmer
    "ro": tr("Romanian"),  # Romanian
}

# If new entries exist
try:
    if Path(ROOT_DIR + f'/videotrans/newlang.txt').exists():
        _new_lang = Path(ROOT_DIR + f'/videotrans/newlang.txt').read_text().strip().split("\n")
        for nl in _new_lang:
            LANGNAME_DICT[nl] = nl
except Exception as e:
    logger.exception(f'读取自定义新增语言代码 newlang.txt 时出错 {e}', exc_info=True)

# Reverse lookup language code by display name
LANGNAME_DICT_REV = {v: k for k, v in LANGNAME_DICT.items()}

# Look up corresponding code list for each translation channel by language code
# Subtitle embedded code defaults to ISO 639-2/T (required for mp4), MKV video needs ISO 639-2/B format
LANG_CODE = {
    "zh-cn": [
        "zh-cn",  # Google channel
        "zho",  # Subtitle embedded language
        "zh",  # Baidu channel
        "ZH-HANS",  # DeepL/DeepLX channel
        "zh",  # Tencent channel
        "zh",  # OTT channel
        "zh-Hans",  # Microsoft Translator
        "Simplified Chinese",  # AI translation
        "zh",  # Alibaba
        "Chinese",  # qwen-mt qwen-tts qwen-asr
        "zh"  # m2m100
    ],
    "zh-tw": [
        "zh-tw",
        "zho",
        "cht",
        "ZH-HANT",
        "zh-TW",
        "zt",
        "zh-Hant",
        "Traditional Chinese",
        "zh-tw",
        "Traditional Chinese",
        "zh"  # m2m100
    ],
    "ur": [
        "ur",  # Google channel
        "urd",  # Subtitle embedded language
        "ur",  # Baidu channel
        "No",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "No",  # OTT channel
        "ur",  # Microsoft Translator
        "Urdu",  # AI translation
        "ur",  # Alibaba
        "Urdu",
        "ur"  # m2m100
    ],
    "ro": [
        "ro",  # Google channel
        "ron",  # Subtitle embedded language
        "rom",  # Baidu channel
        "RO",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "No",  # OTT channel
        "ro",  # Microsoft Translator
        "Romanian",  # AI translation
        "ro",  # Alibaba
        "Romanian",# qwen-mt
        "ro"  # m2m100
    ],
    "km": [
        "km",  # Google channel
        "khm",  # Subtitle embedded language
        "km",  # Baidu channel
        "No",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "No",  # OTT channel
        "km",  # Microsoft Translator
        "Khmer",  # AI translation
        "km",  # Alibaba
        "Khmer",
        "km"  # m2m100
    ],
    "yue": [
        "yue",  # Google channel
        "chi",  # Subtitle embedded language
        "yue",  # Baidu channel
        "No",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "No",  # OTT channel
        "yue",  # Microsoft Translator
        "Cantonese",  # AI translation
        "yue",  # Alibaba
        "Cantonese",
        "zh"  # m2m100
    ],

    "fil": [
        "tl",  # Google channel
        "fil",  # Subtitle embedded language
        "fil",  # Baidu channel
        "No",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "No",  # OTT channel
        "fil",  # Microsoft Translator
        "Filipino",  # AI translation
        "fil",  # Alibaba
        "Filipino",
        "No"
    ],

    "en": [
        "en",
        "eng",
        "en",
        "EN-US",
        "en",
        "en",
        "en",
        "English",
        "en",
        "English",
        "en"  # m2m100
    ],
    "fr": [
        "fr",
        "fra",
        "fra",
        "FR",
        "fr",
        "fr",
        "fr",
        "French",
        "fr",
        "French",
        "fr"  # m2m100
    ],
    "de": [
        "de",
        "deu",
        "de",
        "DE",
        "de",
        "de",
        "de",
        "German",
        "de",
        "German",
        "de"  # m2m100
    ],
    "ja": [
        "ja",
        "jpn",
        "jp",
        "JA",
        "ja",
        "ja",
        "ja",
        "Japanese",
        "ja",
        "Japanese",
        "ja"  # m2m100
    ],
    "ko": [
        "ko",
        "kor",
        "kor",
        "KO",
        "ko",
        "ko",
        "ko",
        "Korean",
        "ko",
        "Korean",
        "ko"  # m2m100
    ],
    "ru": [
        "ru",
        "rus",
        "ru",
        "RU",
        "ru",
        "ru",
        "ru",
        "Russian",
        "ru",
        "Russian",
        "ru"  # m2m100
    ],
    "es": [
        "es",
        "spa",
        "spa",
        "ES",
        "es",
        "es",
        "es",
        "Spanish",
        "es",
        "Spanish",
        "es"  # m2m100
    ],
    "th": [
        "th",
        "tha",
        "th",
        "No",
        "th",
        "th",
        "th",
        "Thai",
        "th",
        "Thai",
        "th"  # m2m100
    ],
    "it": [
        "it",
        "ita",
        "it",
        "IT",
        "it",
        "it",
        "it",
        "Italian",
        "it",
        "Italian",
        "it"  # m2m100
    ],
    "el": [
        "el",  # google
        "ell",  # subtitle embed (ISO 639-2/T)
        "el",  # baidu
        "EL",  # deepl / deeplx
        "el",  # tencent
        "el",  # OTT
        "el",  # microsoft / bing
        "Greek",  # AI (LLM)
        "el",  # alibaba
        "Greek",  # qwen-mt / qwen-tts / qwen-asr
        "el"  # m2m100
    ],
    "nb": [
        "no",  # google
        "nob",  # subtitle embed (ISO 639-2/B)
        "nob",  # baidu
        "NB",  # deepl / deeplx
        "No",  # Tencent not supported
        "No",  # OTT not supported
        "nb",  # microsoft / bing
        "Norwegian Bokmål",  # AI (LLM) Norwegian Bokmål
        "no",  # alibaba
        "Norwegian Bokmål",  # qwen-mt / qwen-tts / qwen-asr
        "no"  # m2m100
    ],
    "pt": [
        "pt",  # pt-PT
        "por",
        "pt",
        "PT-PT",
        "PT-PT",
        "pt",
        "pt",
        "Portuguese",
        "pt",
        "Portuguese",
        "pt"  # m2m100
    ],
    "vi": [
        "vi",
        "vie",
        "vie",
        "vi",
        "vi",
        "vi",
        "vi",
        "Vietnamese",
        "vi",
        "Vietnamese",
        "vi"  # m2m100
    ],
    "ar": [
        "ar",
        "are",
        "ara",
        "AR",
        "ar",
        "ar",
        "ar",
        "Arabic",
        "ar",
        "Arabic",
        "ar"  # m2m100
    ],
    "tr": [
        "tr",
        "tur",
        "tr",
        "TR",
        "tr",
        "tr",
        "tr",
        "Turkish",
        "tr",
        "Turkish",
        "tr"  # m2m100
    ],
    "hi": [
        "hi",
        "hin",
        "hi",
        "No",
        "hi",
        "hi",
        "hi",
        "Hindi",
        "hi",
        "Hindi",
        "hi"  # m2m100
    ],
    "hu": [
        "hu",
        "hun",
        "hu",
        "HU",
        "No",
        "hu",
        "hu",
        "Hungarian",
        "hu",
        "Hungarian",
        "hu"  # m2m100
    ],
    "uk": [
        "uk",
        "ukr",
        "ukr",  # Baidu
        "UK",  # deepl
        "No",  # Tencent
        "uk",  # ott
        "uk",  # Microsoft
        "Ukrainian",
        "No",
        "Ukrainian",
        "uk"  # m2m100
    ],
    "id": [
        "id",
        "ind",
        "id",
        "ID",
        "id",
        "id",
        "id",
        "Indonesian",
        "id",
        "Indonesian",
        "id"  # m2m100
    ],
    "ms": [
        "ms",
        "msa",
        "may",
        "No",
        "ms",
        "ms",
        "ms",
        "Malay",
        "ms",
        "Malay",
        "ms"  # m2m100
    ],
    "kk": [
        "kk",
        "kaz",
        "No",
        "No",
        "No",
        "No",
        "kk",
        "Kazakh",
        "kk",
        "Kazakh",
        "kk"  # m2m100
    ],
    "cs": [
        "cs",
        "ces",
        "cs",
        "CS",
        "No",
        "cs",
        "cs",
        "Czech",
        "cs",
        "Czech",
        "cs"  # m2m100
    ],
    "pl": [
        "pl",
        "pol",
        "pl",
        "PL",
        "No",
        "pl",
        "pl",
        "Polish",
        "pl",
        "Polish",
        "pl"  # m2m100
    ],
    "nl": [
        "nl",  # Google channel
        "nld",  # Subtitle embedded language
        "nl",  # Baidu channel
        "NL",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "nl",  # OTT channel
        "nl",  # Microsoft Translator
        "Dutch",  # AI translation
        "nl",
        "Dutch",
        "nl"  # m2m100
    ],
    "sv": [
        "sv",  # Google channel
        "swe",  # Subtitle embedded language
        "swe",  # Baidu channel
        "SV",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "sv",  # OTT channel
        "sv",  # Microsoft Translator
        "Swedish",  # AI translation
        "sv",
        "Swedish",
        "sv"  # m2m100
    ],
    "he": [
        "he",  # Google channel
        "heb",  # Subtitle embedded language
        "heb",  # Baidu channel
        "HE",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "No",  # OTT channel
        "he",  # Microsoft Translator
        "Hebrew",  # AI translation
        "he",
        "Hebrew",
        "he"  # m2m100
    ],
    "bn": [
        "bn",  # Google channel
        "ben",  # Subtitle embedded language
        "ben",  # Baidu channel
        "No",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "No",  # OTT channel
        "bn",  # Microsoft Translator
        "Bengali",  # AI translation
        "bn",
        "Bengali",
        "bn"  # m2m100
    ],
    "fa": [
        "fa",  # Google channel
        "fas",  # Subtitle embedded language
        "per",  # Baidu channel
        "No",  # DeepL/DeepLX channel
        "No",  # Tencent channel
        "No",  # OTT channel
        "fa",  # Microsoft Translator
        "Persian",  # AI translation
        "fa",  # Alibaba
        "Western Persian",
        "fa"  # m2m100
    ],
    "auto": [
        "auto",
        "auto",
        "auto",
        "auto",
        "auto",
        "auto",
        "auto",
        "auto",
        "auto",
        "auto",
        "auto"
    ]
}
