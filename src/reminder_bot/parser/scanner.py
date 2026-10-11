import re
from collections.abc import Iterator

_ROLE_RE = re.compile(r"\s*(までに|まで|から|以降)")


class Scanner:
    """解釈済みの文字範囲を記録しながら正規表現を当てる。残りが本文になる。"""

    def __init__(self, text: str):
        self.text = text
        self._used = [False] * len(text)

    def _free(self, start: int, end: int) -> bool:
        return end > start and not any(self._used[start:end])

    def matches(self, pattern: re.Pattern) -> Iterator[re.Match]:
        # 消費済みと重なったら1文字ずらして探し直す(「今夜9時」の「夜9時」→「9時」)
        pos = 0
        while (m := pattern.search(self.text, pos)) is not None:
            if self._free(m.start(), m.end()):
                yield m
                pos = max(m.end(), m.start() + 1)
            else:
                pos = m.start() + 1

    def first(self, pattern: re.Pattern) -> re.Match | None:
        return next(self.matches(pattern), None)

    def consume(self, start: int, end: int) -> None:
        for i in range(start, end):
            self._used[i] = True

    def take(self, m: re.Match) -> None:
        self.consume(m.start(), m.end())

    def take_role(self, end: int) -> str:
        """end 直後の「から」「まで」を消費して役割を返す: main / start / until。"""
        m = _ROLE_RE.match(self.text, end)
        if not m or not self._free(m.start(), m.end()):
            return "main"
        self.take(m)
        word = m.group(1)
        if word == "まで":
            return "until"
        if word == "までに":
            return "main"
        return "start"

    def segments(self) -> list[str]:
        out, buf = [], []
        for ch, used in zip(self.text, self._used):
            if used:
                if buf:
                    out.append("".join(buf))
                    buf = []
            else:
                buf.append(ch)
        if buf:
            out.append("".join(buf))
        return out
