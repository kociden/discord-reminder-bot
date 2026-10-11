import re
import unicodedata

_KANJI_DIGITS = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
                 "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

# 単位の直前にある漢数字だけを変換する(「一緒」などを壊さないため)
_KANJI_NUM_RE = re.compile(
    r"[〇零一二三四五六七八九十]+(?=\s*(?:時|分|秒|日|週|ヶ月|か月|カ月|ヵ月|ケ月|月|回))"
)
_PUNCT_RE = re.compile(r"[、。!?！？]")


def kanji_to_int(s: str) -> int | None:
    try:
        if "十" in s:
            tens, _, ones = s.partition("十")
            t = _KANJI_DIGITS[tens] if tens else 1
            o = _KANJI_DIGITS[ones] if ones else 0
            return t * 10 + o
        return int("".join(str(_KANJI_DIGITS[c]) for c in s))
    except KeyError:
        return None


def _replace_kanji(m: re.Match) -> str:
    n = kanji_to_int(m.group(0))
    return m.group(0) if n is None else str(n)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _KANJI_NUM_RE.sub(_replace_kanji, text)
    text = _PUNCT_RE.sub(" ", text)
    return text.strip()
