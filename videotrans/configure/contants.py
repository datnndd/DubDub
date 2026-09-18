#-------------标点 空格语言-----------
# 中日韩 泰国语 高棉语 粤语 不使用空格
CJK_LANG = ["zh", "ja", "ko", "yu", "th", "km", "yue"]
# 常见标点
PUNC_FLAGS = [",", ".", "?", "!", ";", "，", "。", "？", "；", "！"]
# 逗号等软性标点
PUNC_FLAGS_HALF = [",", "，", "-", "、", ":", "："]
# 句子终止标点
PUNC_FLAGS_END = [".", "。", "?", "？", "!", "！"]
NON_WORD = r"""^[,.?!;'"_，。？；‘’“”！~@#￥%…&*（【】）｛｝《、》$()\[\]{}=+<>\s-]+$"""

#------------跳过使用代理的域名---------------
# 不使用代理的域名
_no_proxy_list = [
    # --- 腾讯云 ---
    "tencentcloudapi.com", ".tencentcloudapi.com",

    # --- HuggingFace ---
    "hf-mirror.com", ".hf-mirror.com",

    # --- 百度 (包含 fanyi.baidu 等所有子域) ---
    "baidu.com", ".baidu.com",

    # --- 字节跳动 (包含 openspeech 等所有子域) ---
    "bytedance.com", ".bytedance.com", ".volces.com", "volces.com",

    # --- MiniMax ---
    "api.minimaxi.com", ".minimaxi.com",

    # --- DeepSeek ---
    "api.deepseek.com", ".deepseek.com",

    # --- ModelScope ---
    "modelscope.cn", ".modelscope.cn",

    # --- 阿里云 (包含 dashscope, aliyuncs 等) ---
    "aliyuncs.com", ".aliyuncs.com",

    # --- SiliconFlow ---
    "siliconflow.cn", ".siliconflow.cn",

    "ms.show", ".ms.show",
    "bigmodel.cn", ".bigmodel.cn",

    "api.gradio.app", ".api.gradio.app",
    # "microsoft.com", ".microsoft.com", # 涵盖 tts.speech.microsoft.com

    # --- 本地回环 (涵盖所有端口：7860, 8000, 9880, 5051等) ---
    "localhost",
    "127.0.0.1",
    "127.0.0.2",
    "0.0.0.0",
]
no_proxy = ",".join(_no_proxy_list)

#----------------支持的音视频格式---------------
# 支持的视频格式
VIDEO_EXTS = ["mp4", "mkv", "mpeg", "avi", "mov", "mts", "webm", "ogg", "ts", "flv", "wmv"]
# 支持的音频格式
AUDIO_EXITS = ["mp3", "wav", "aac", "flac", "m4a", "ogg", "wma"]

#-----------默认模型名字-----------------
FASTER_MODELS_DICT = {"large-v3": "Systran/faster-whisper-large-v3"}
# deepgram 支持的语音识别模型
DEEPGRAM_MODEL = [
    "nova-3",
    "whisper-large",
    "whisper-medium",
    "whisper-small",
    "whisper-base",
    "whisper-tiny",
    "nova-2",
    "enhanced",
    "base",
]

# 缺省 gemini 模型
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash,gemini-3.5-flash,gemini-pro-latest,gemini-flash-latest,gemini-2.5-pro,gemini-2.5-flash"
# gemini-tts 音色
GEMINITTS_ROLES = "Zephyr,Puck,Charon,Kore,Fenrir,Leda,Orus,Aoede,Callirrhoe,Autonoe,Enceladus,Iapetus,Umbriel,Algieba,Despina,Erinome,Algenib,Rasalgethi,Laomedeia,Achernar,Alnilam,Schedar,Gacrux,Pulcherrima,Achird,Zubenelgenubi,Vindemiatrix,Sadachbia,Sadaltager,Sulafat"

GEMINI_TTS_MODELS = "gemini-3.1-flash-tts-preview,gemini-2.5-flash-preview-tts,gemini-2.5-pro-preview-tts"

Chatgpt_Model = "gpt-5.5,gpt-5.5-pro,gpt-5.4-pro,gpt-5.4,gpt-5.4-mini,gpt-5,gpt-5-mini,gpt-4.1"
Deepseek_Model = "deepseek-v4-pro,deepseek-v4-flash"
Whisper_Models = "large-v3"
ELEVENLABS_TTS_MODELS = "eleven_v3,eleven_flash_v2_5,eleven_flash_v2,eleven_multilingual_v2,eleven_multilingual_v1"


#--------------模型下载地址-------------------
# 内置说话人下载地址
BUILTINT_URL_MS = [
    "https://www.modelscope.cn/models/himyworld/videotrans/resolve/master/onnx/seg_model.onnx",
    "https://www.modelscope.cn/models/himyworld/videotrans/resolve/master/onnx/nemo_en_titanet_small.onnx",
    "https://www.modelscope.cn/models/himyworld/videotrans/resolve/master/onnx/3dspeaker_speech_eres2net_large_sv_zh-cn_3dspeaker_16k.onnx"
]
BUILTINT_URL_HF = [
    "https://huggingface.co/mortimerme/repocollect/resolve/main/onnx/seg_model.onnx?download=true",
    "https://huggingface.co/mortimerme/repocollect/resolve/main/onnx/nemo_en_titanet_small.onnx?download=true",
    "https://huggingface.co/mortimerme/repocollect/resolve/main/onnx/3dspeaker_speech_eres2net_large_sv_zh-cn_3dspeaker_16k.onnx?download=true"
]

# 内置标点恢复模型下载地址
PUNC_RESTORE_MS = [
    "https://www.modelscope.cn/models/himyworld/videotrans/resolve/master/puntc/model.onnx",
    "https://www.modelscope.cn/models/himyworld/videotrans/resolve/master/puntc/config.yaml",
    "https://www.modelscope.cn/models/himyworld/videotrans/resolve/master/puntc/tokens.json",
]
PUNC_RESTORE_HF = [
    "https://huggingface.co/mortimerme/repocollect/resolve/main/puntc/model.onnx?download=true",
    "https://huggingface.co/mortimerme/repocollect/resolve/main/puntc/config.yaml?download=true",
    "https://huggingface.co/mortimerme/repocollect/resolve/main/puntc/tokens.json?download=true",
]
# 降噪模型下载地址
DENOISE_URL_MS = [
    'https://modelscope.cn/models/himyworld/videotrans/resolve/master/onnx/dpdfnet8.onnx'
]
DENOISE_URL_HF = [
    'https://huggingface.co/mortimerme/repocollect/resolve/main/onnx/dpdfnet8.onnx?download=true'
]
# 背景音频分离地址前缀
UVR_URL_MS = 'https://www.modelscope.cn/models/himyworld/videotrans/resolve/master/onnx/{}'
UVR_URL_HF = 'https://huggingface.co/mortimerme/repocollect/resolve/main/onnx/{}?download=true'
# realtime stt
REALTIME_URL_MS='https://modelscope.cn/models/himyworld/videotrans/resolve/master/realtimestt.zip'
REALTIME_URL_HF='https://huggingface.co/mortimerme/repocollect/resolve/main/realtimestt.zip?download=true'

#----------Rubberband 库安装提示------------------
INSTALL_RUBBERBAND_TIPS = """Windows: For Windows systems, please download the file, extract it, and place it in the ffmpeg folder in the current directory. Use a better audio acceleration algorithm\nhttps://breakfastquay.com/files/releases/rubberband-4.0.0-gpl-executable-windows.zip
Darwin: `brew install rubberband`  and  `uv add pyrubberband` Use a better audio acceleration algorithm
Linux: `sudo apt install rubberband-cli libsndfile1-dev` and `uv add pyrubberband`  Use a better audio acceleration algorithm"""

#--------进度状态提示文字-----------------------
END_STATUS = "end"
ERROR_STATUS = "error"
SUCCEED_STATUS = "succeed"
STOP_STATUS = "stop"
ING_STATUS = "ing"

#------------配音试听词---------------
LISTEN_TEXT = {
    "zh": "你好啊，我亲爱的朋友，希望你的每一天都是美好愉快的！",
    "zh-cn": "你好啊，我亲爱的朋友，希望你的每一天都是美好愉快的！",
    "zh-tw": "你好啊，我親愛的朋友，希望你的每一天都是美好愉快的！",
    "ro": "Bună, draga mea prietenă, sper ca fiecare zi a ta să fie minunată și plină de bucurie!",
    "km": "សួស្តីមិត្តជាទីស្រឡាញ់របស់ខ្ញុំ ខ្ញុំសង្ឃឹមថារាល់ថ្ងៃរបស់អ្នកគឺអស្ចារ្យ និងរីករាយ។!",
    "nb": "Hallo, min kjære venn, jeg håper hver dag din er fantastisk og gledelig.",
    "en": "Hello, my dear friend. I hope your every day is beautiful and enjoyable!",
    "fr": "Bonjour mon cher ami. J'espère que votre quotidien est beau et agréable !",
    "de": "Hallo mein lieber Freund. Ich hoffe, dass Ihr Tag schön und angenehm ist!",
    "ja": "こんにちは私の親愛なる友人。 あなたの毎日が美しく楽しいものでありますように！",
    "ko": "안녕, 내 사랑하는 친구. 당신의 매일이 아름답고 즐겁기를 바랍니다!",
    "ru": "Привет, мой дорогой друг. Желаю, чтобы каждый твой день был прекрасен и приятен!",
    "es": "Hola mi querido amigo. ¡Espero que cada día sea hermoso y agradable!",
    "th": "สวัสดีเพื่อนรัก. ฉันหวังว่าทุกวันของคุณจะสวยงามและสนุกสนาน!",
    "it": "Ciao caro amico mio. Spero che ogni tuo giorno sia bello e divertente!",
    "el": "Γεια σου, αγαπητέ μου φίλε. Εύχομαι κάθε σου μέρα να είναι όμορφη και ευχάριστη!",
    "pt": "Olá meu querido amigo. Espero que todos os seus dias sejam lindos e agradáveis!",
    "vi": "Xin chào người bạn thân yêu của tôi. Tôi hy vọng mỗi ngày của bạn đều đẹp và thú vị!",
    "ar": "مرحبا صديقي العزيز. أتمنى أن يكون كل يوم جميلاً وممتعًا!",
    "tr": "Merhaba sevgili arkadaşım. Umarım her gününüz güzel ve keyifli geçer!",
    "hi": "नमस्ते मेरे प्यारे दोस्त। मुझे आशा है कि आपका हर दिन सुंदर और आनंददायक हो!!",
    "hu": "Helló kedves barátom. Remélem minden napod szép és kellemes!",
    "uk": "Привіт, мій дорогий друже, сподіваюся, ти щодня прекрасна!",
    "id": "Halo, temanku, semoga kamu cantik setiap hari!",
    "ms": "Helo, sahabat saya, saya harap anda cantik setiap hari!",
    "kk": "Сәлеметсіз бе, менің қымбатты досым, сендер күн сайын әдемісің деп үміттенемін!",
    "cs": "Ahoj, můj drahý příteli, doufám, že jsi každý den krásná!",
    "pl": "Witam, mój drogi przyjacielu, mam nadzieję, że jesteś piękna każdego dnia!",
    "nl": "Hallo mijn lieve vriend, ik hoop dat elke dag goed en fijn voor je is!!",
    "sv": "Hej min kära vän, jag hoppas att varje dag är en bra och trevlig dag för dig!",
    "he": "שלום, ידידי היקר, אני מקווה שכל יום בחייך יהיה נפלא ומאושר!",
    "bn": "হ্যালো, আমার প্রিয় বন্ধু, আমি আশা করি আপনার জীবনের প্রতিটি দিন চমৎকার এবং সুখী হোক!",
    "fil": "Hello, kaibigan ko",
    "fa": "سلام دوستای گلم امیدوارم هر روز از زندگیتون عالی و شاد باشه.",
    "ur": "ہیلو پیارے دوست، مجھے امید ہے کہ آپ آج خوش ہوں گے۔",
    "yue": "你好啊親愛嘅朋友，希望你今日好開心",

}
