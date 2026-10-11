import re

_PARTICLES = r"(?:には|では|から|まで|に|で|の|は|を|って|と|が|へ)"
_LEAD_RE = re.compile(rf"^(?:\s|[,.~]|{_PARTICLES})+")
_TRAIL_RE = re.compile(rf"(?:\s|[,.~]|{_PARTICLES})+$")
_REQUEST_RE = re.compile(
    r"(?:\s|を|って|と|の)*"
    r"(?:リマインド|リマインダー|リマインダ|お知らせ|知らせて|教えて|通知|連絡|お願い|おねがい|よろしく|"
    r"言って|思い出させて|起こして|呼んで|アラーム)"
    r"(?:して|する|を)?(?:ください|下さい|くれ|ね|よ|な|ー)*\s*$"
)
_LEAD_REQUEST_RE = re.compile(r"^(?:リマインド|リマインダー|通知)(?:して)?\s*[:]?\s*")

DEFAULT_CONTENT = "リマインダー"


def _strip(s: str) -> str:
    return _TRAIL_RE.sub("", _LEAD_RE.sub("", s))


def extract_content(segments: list[str]) -> str:
    parts = [p for p in (_strip(s) for s in segments) if p]
    text = " ".join(parts)
    while True:
        new = _strip(_LEAD_REQUEST_RE.sub("", _REQUEST_RE.sub("", text)))
        if new == text:
            return text
        text = new
