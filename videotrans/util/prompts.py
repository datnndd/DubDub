# -*- coding: utf-8 -*-
from functools import lru_cache
from pathlib import Path

from videotrans.configure.config import ROOT_DIR


# 获取 prompt提示词
def get_prompt(ainame, aisendsrt=True):
    prompt_file = get_prompt_file(ainame=ainame, aisendsrt=aisendsrt)
    content = Path(prompt_file).read_text(encoding='utf-8-sig', errors="ignore")
    glossary = ''
    glossary_path = Path(ROOT_DIR + '/videotrans/glossary.txt')
    if glossary_path.exists():
        glossary = glossary_path.read_text(encoding='utf-8-sig', errors="ignore").strip()
        if glossary:
            glossary = "\n".join(["|" + it.replace("=", '|') + "|" for it in glossary.split('\n')])
            glossary = f"\n\n# Glossary of terms\nTranslations are made strictly according to the following glossary. If a term appears in a sentence, the corresponding translation must be used, not a free translation:\n| Glossary | Translation |\n| --------- | ----- |\n{glossary}\n\n"
    content = content.replace('{GLOSSARY_DICT}', glossary)
    return content


def qwenmt_glossary():
    glossary_path = Path(ROOT_DIR + '/videotrans/glossary.txt')
    if glossary_path.exists():
        glossary = glossary_path.read_text(encoding='utf-8-sig', errors="ignore").strip()
        if glossary:
            term = []
            for it in glossary.split('\n'):
                tmp = it.split("=")
                if len(tmp) == 2:
                    term.append({"source": tmp[0], "target": tmp[1]})
            return term if len(term) > 0 else None
    return None


# 获取当前需要操作的prompt txt文件
@lru_cache
def get_prompt_file(ainame, aisendsrt=True):
    prompt_path = f'{ROOT_DIR}/videotrans/'
    prompt_name = f'{ainame}.txt'
    if aisendsrt:
        prompt_path += 'prompts/srt/'
    else:
        prompt_path += 'prompts/text/'
    return f'{prompt_path}{prompt_name}'
