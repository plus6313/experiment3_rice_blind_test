"""答案 sanitization（與 experiment2 相同邏輯，獨立專案故保留一份小副本）。"""

import re

MASK = "[身分用語已移除]"


def _build_pattern(keywords):
    escaped = [re.escape(k) for k in keywords if k]
    escaped.sort(key=len, reverse=True)
    pattern = "(" + "|".join(escaped) + ")"
    return re.compile(pattern, re.IGNORECASE)


def sanitize_answer(text, keywords, mask=MASK):
    text = text if text is not None else ""
    pattern = _build_pattern(keywords)
    matches = pattern.findall(text)
    if not matches:
        return text.strip(), False, []

    cleaned = pattern.sub(mask, text)
    hits = sorted(set(m.lower() for m in matches))
    return cleaned.strip(), True, hits
