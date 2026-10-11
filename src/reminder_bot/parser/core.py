"""アバウトな日本語からリマインダーの日時・繰り返し・内容を読み取る。

流れ: 正規化 → 繰り返し → 相対時間(N分後) → 日付 → 時刻 → 曖昧語 → 組み立て。
読み取った部分は Scanner が消費し、残りが本文になる。
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from ..models import DAILY, INTERVAL, MONTH_END, MONTHLY, WEEKDAYS, WEEKLY, ParseResult, Recurrence
from ..recurrence import first_occurrence
from ..timeutil import combine
from .content import DEFAULT_CONTENT, extract_content
from .normalize import normalize
from .scanner import Scanner

DEFAULT_MINUTE = 9 * 60
MIN_INTERVAL = timedelta(minutes=5)
WD = "月火水木金土日"

# 曖昧語 → 0:00 からの分。1440 以上は翌日。
DEFAULT_FUZZY_TIMES: dict[str, int] = {
    "朝イチ": 9 * 60, "朝一番": 9 * 60, "朝一": 9 * 60,
    "早朝": 6 * 60, "朝": 8 * 60, "午前中": 10 * 60,
    "お昼": 12 * 60, "昼過ぎ": 13 * 60, "昼": 12 * 60, "正午": 12 * 60,
    "おやつ": 15 * 60, "午後": 14 * 60, "夕方": 17 * 60, "夕暮れ": 17 * 60,
    "夜": 20 * 60, "晩": 20 * 60, "寝る前": 23 * 60, "夜中": 24 * 60, "深夜": 24 * 60,
}


@dataclass
class _DateHit:
    day: date
    role: str = "main"
    roll_days: int = 0  # 時刻が過ぎていたら何日ずらすか(曜日指定)
    default_minute: int | None = None
    hint: str | None = None  # "am" / "pm"
    vague: str | None = None  # 要確認の理由


@dataclass
class _TimeHit:
    minute: int
    role: str = "main"
    ambiguous: bool = False


# ---------------- 繰り返し ----------------

_INTERVAL_RE = re.compile(r"(?P<n>\d+)\s*(?P<unit>分|時間|日)(?P<half>半)?\s*(?:おき|置き|ごと|毎|間隔)")
_HOURLY_RE = re.compile(r"毎時(?:間)?")
_ITEM = r"(?:土日|[月火水木金土日](?:曜日|曜)?)"
_ITEM_STRICT = r"[月火水木金土日](?:曜日|曜)"
_WEEKLY_RE = re.compile(
    rf"(?P<prefix>毎週|隔週)\s*の?\s*(?P<list>{_ITEM}(?:\s*[・,と&/]\s*{_ITEM}|\s*{_ITEM_STRICT})*)"
)
_WEEKEND_RE = re.compile(r"毎週末")
_MAI_WD_RE = re.compile(r"毎(?P<wd>[月火水木金土日])曜日?")
_MULTI_WD_RE = re.compile(rf"{_ITEM_STRICT}(?:\s*[・,と&/]\s*{_ITEM_STRICT})+")
_MONTHLY_RE = re.compile(r"毎月\s*の?\s*(?:(?P<day>\d{1,2})\s*日|(?P<end>末日?|最終日))")
_WEEKDAYS_RE = re.compile(r"平日(?:\s*の)?(?:\s*毎日)?")
_DAILY_RE = re.compile(r"毎(?P<w>日|朝|晩|夜)")
_COUNT_RE = re.compile(r"(?:全部で|計|合計)?\s*(?P<n>\d+)\s*回(?:だけ|分)?")

# ---------------- 相対時間 ----------------

_REL_RE = re.compile(
    r"(?:(?P<h>\d+)\s*時間(?P<half>半)?(?:\s*(?P<hm>\d+)\s*分)?|(?P<m>\d+)\s*分|(?P<s>\d+)\s*秒)"
    r"\s*(?:後|経ったら|たったら)"
)
_ATO_RE = re.compile(r"あと\s*(?:(?P<h>\d+)\s*時間(?P<half>半)?|(?P<m>\d+)\s*分)\s*(?:で|したら)?")
_DAY_OFFSET_RE = re.compile(r"(?P<n>\d+)\s*(?P<u>日|週間|週|ヶ月|か月|カ月|ヵ月|ケ月)\s*後")

# ---------------- 時刻 ----------------

_TIME_RE = re.compile(
    r"(?P<pre>午前|午後|朝|昼|夕方|夜中|夜|晩|深夜|am|pm)?\s*(?:の\s*)?"
    r"(?P<h>\d{1,2})\s*(?::\s*(?P<mm>\d{2})|時(?!間)(?:\s*(?P<m>\d{1,2})\s*分|\s*(?P<half>半))?)"
    r"\s*(?P<suf>am|pm)?\s*(?:ごろ|頃|くらい|ぐらい|ちょうど)?",
    re.IGNORECASE,
)
_FUZZY_SUFFIX = r"(?:ごろ|頃|くらい|ぐらい)?(?!ご?飯|ごはん|食|休み|寝|練|活|勤)"


def _add_months(d: date, n: int) -> tuple[int, int]:
    m = d.month - 1 + n
    return d.year + m // 12, m % 12 + 1


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


# ---------------- 日付パターン ----------------

def _date_patterns(today: date):
    """(正規表現, match -> _DateHit | None) のリスト。上から順に試す。"""

    def ymd(m):
        return _hit(_safe_date(int(m["y"]), int(m["mo"]), int(m["d"])))

    def md(m):
        d = _safe_date(today.year, int(m["mo"]), int(m["d"]))
        if d and d < today:
            d = _safe_date(today.year + 1, int(m["mo"]), int(m["d"]))
        return _hit(d)

    def week_wd(m):
        weeks = {"今週": 0, "来週": 1, "再来週": 2}[m["w"]]
        return _hit(_monday(today) + timedelta(days=7 * weeks + WD.index(m["wd"])))

    def weekend(m):
        if m["w"] == "来週":
            return _hit(_monday(today) + timedelta(days=12))
        d = _monday(today) + timedelta(days=5)
        if d < today:
            d += timedelta(days=7)
        return _hit(d)

    def next_monday(m):
        return _hit(_monday(today) + timedelta(days=7))

    def month_end(m):
        y, mo = _add_months(today, 1 if m["m"] == "来月" else 0)
        return _hit(date(y, mo, calendar.monthrange(y, mo)[1]))

    def next_month_day(m):
        y, mo = _add_months(today, 1)
        return _hit(_safe_date(y, mo, int(m["d"])))

    def next_month_first(m):
        y, mo = _add_months(today, 1)
        return _hit(date(y, mo, 1))

    def offset(days, **kw):
        return lambda m: _hit(today + timedelta(days=days), **kw)

    def weekday(m):
        delta = (WD.index(m["wd"]) - today.weekday()) % 7
        return _hit(today + timedelta(days=delta), roll_days=7 if delta == 0 else 0)

    def vague_week(m):
        weeks = 2 if m.group(0) == "再来週" else 1
        return _hit(_monday(today) + timedelta(days=7 * weeks), vague="曜日の指定がないので月曜にしました")

    def vague_month(m):
        y, mo = _add_months(today, 1)
        return _hit(date(y, mo, 1), vague="日の指定がないので1日にしました")

    def day_of_month(m):
        d = int(m["d"])
        cand = _safe_date(today.year, today.month, d)
        if cand is None or cand < today:
            y, mo = _add_months(today, 1)
            cand = _safe_date(y, mo, d)
        return _hit(cand)

    return [
        (r"(?P<y>\d{4})\s*[/\-.年]\s*(?P<mo>\d{1,2})\s*[/\-.月]\s*(?P<d>\d{1,2})\s*日?", ymd),
        (r"(?P<mo>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日", md),
        (r"(?<![\d:])(?P<mo>\d{1,2})\s*/\s*(?P<d>\d{1,2})(?![\d:])", md),
        (r"(?P<w>再来週|来週|今週)\s*の?\s*(?P<wd>[月火水木金土日])\s*曜日?", week_wd),
        (r"(?P<w>来週|今週)末|週末", weekend),
        (r"来週\s*(?:頭|初め|はじめ|明け)|週明け", next_monday),
        (r"(?P<m>来月|今月)\s*末日?|月末日?", month_end),
        (r"来月\s*の?\s*(?P<d>\d{1,2})\s*日", next_month_day),
        (r"来月\s*(?:頭|初め|はじめ)|月初め?", next_month_first),
        (r"明々後日|明明後日|しあさって", offset(3)),
        (r"明後日|あさって", offset(2)),
        (r"明日|あした", offset(1)),
        (r"今日|本日|きょう", offset(0)),
        (r"今夜|今晩", offset(0, default_minute=20 * 60, hint="pm")),
        (r"今朝", offset(0, default_minute=8 * 60, hint="am")),
        (r"(?P<wd>[月火水木金土日])\s*曜日?", weekday),
        (r"再来週|来週", vague_week),
        (r"来月", vague_month),
        (r"(?<![\d/月])(?P<d>\d{1,2})\s*日(?!\s*(?:後|間|おき|置き|ごと|毎))", day_of_month),
    ]


def _hit(d: date | None, **kw) -> _DateHit | None:
    return None if d is None else _DateHit(d, **kw)


# ---------------- 時刻の解釈 ----------------

def _to_minute(h: int, mi: int, pre: str, suf: str, ctx_hint: str | None) -> tuple[int, bool] | None:
    """(0:00 からの分, 午前午後が曖昧か)。範囲外なら None。"""
    if h > 24 or mi > 59:
        return None
    pre, suf = (pre or "").lower(), (suf or "").lower()
    if pre in ("午後", "夕方", "pm") or suf == "pm":
        h = h + 12 if h < 12 else h
    elif pre in ("夜", "晩") or (not pre and not suf and ctx_hint == "pm"):
        if h <= 4:
            h += 24  # 夜1時 → 翌1:00
        elif h < 12:
            h += 12
        elif h == 12:
            h = 24
    elif pre in ("深夜", "夜中"):
        if h <= 5:
            h += 24
        elif h == 11:
            h = 23
        elif h in (0, 12):
            h = 24
    elif pre in ("午前", "朝", "am") or suf == "am" or ctx_hint == "am":
        h = 0 if h == 12 else h
    elif pre == "昼":
        h = h + 12 if 1 <= h <= 5 else h
    elif 1 <= h <= 6:
        return (h + 12) * 60 + mi, True  # 「3時」は15時とみなす(要確認)
    return h * 60 + mi, False


def _fuzzy_re(words: dict[str, int]) -> re.Pattern:
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?P<w>{alts}){_FUZZY_SUFFIX}")


def _fmt_minute(minute: int) -> str:
    return f"{minute // 60 % 24}:{minute % 60:02d}"


# ---------------- 本体 ----------------

def parse(text: str, now: datetime, aliases: dict[str, time] | None = None) -> ParseResult:
    sc = Scanner(normalize(text))
    today = now.date()
    reasons: list[str] = []

    # 1. 繰り返し
    rec_kw: dict | None = None
    rec_minute: int | None = None
    hint: str | None = None

    if m := sc.first(_INTERVAL_RE):
        sc.take(m)
        unit = {"分": 1, "時間": 60, "日": 1440}[m["unit"]]
        minutes = int(m["n"]) * unit + (unit // 2 if m["half"] else 0)
        rec_kw = {"kind": INTERVAL, "interval": timedelta(minutes=minutes)}
    elif m := sc.first(_HOURLY_RE):
        sc.take(m)
        rec_kw = {"kind": INTERVAL, "interval": timedelta(hours=1)}
    elif m := sc.first(_WEEKLY_RE):
        sc.take(m)
        days = set()
        for item in re.findall(_ITEM, m["list"]):
            days |= {5, 6} if item == "土日" else {WD.index(item[0])}
        rec_kw = {"kind": WEEKLY, "weekdays": frozenset(days), "week_step": 2 if m["prefix"] == "隔週" else 1}
    elif m := sc.first(_WEEKEND_RE):
        sc.take(m)
        rec_kw = {"kind": WEEKLY, "weekdays": frozenset({5})}
    elif m := sc.first(_MAI_WD_RE):
        sc.take(m)
        rec_kw = {"kind": WEEKLY, "weekdays": frozenset({WD.index(m["wd"])})}
    elif m := sc.first(_MULTI_WD_RE):
        sc.take(m)
        days = {WD.index(item[0]) for item in re.findall(_ITEM_STRICT, m.group(0))}
        rec_kw = {"kind": WEEKLY, "weekdays": frozenset(days)}
    elif m := sc.first(_MONTHLY_RE):
        sc.take(m)
        rec_kw = {"kind": MONTHLY, "day_of_month": MONTH_END if m["end"] else int(m["day"])}
    elif m := sc.first(_WEEKDAYS_RE):
        sc.take(m)
        rec_kw = {"kind": WEEKDAYS}
    elif m := sc.first(_DAILY_RE):
        sc.take(m)
        rec_kw = {"kind": DAILY}
        if m["w"] == "朝":
            rec_minute, hint = 8 * 60, "am"
        elif m["w"] in ("晩", "夜"):
            rec_minute, hint = 20 * 60, "pm"

    count = None
    if rec_kw and (m := sc.first(_COUNT_RE)):
        sc.take(m)
        count = int(m["n"])

    # 2. 相対時間
    rel_dt: datetime | None = None
    for pattern in (_REL_RE, _ATO_RE):
        if rel_dt is None and (m := sc.first(pattern)):
            gd = m.groupdict()
            minutes = int(gd.get("h") or 0) * 60 + (30 if gd.get("half") else 0)
            minutes += int(gd.get("hm") or 0) + int(gd.get("m") or 0)
            seconds = int(gd.get("s") or 0)
            if minutes or seconds:
                sc.take(m)
                sc.take_role(m.end())
                rel_dt = now + timedelta(minutes=minutes, seconds=seconds)

    dates: list[_DateHit] = []
    if m := sc.first(_DAY_OFFSET_RE):
        sc.take(m)
        n, u = int(m["n"]), m["u"]
        if u == "日":
            d = today + timedelta(days=n)
        elif u in ("週", "週間"):
            d = today + timedelta(weeks=n)
        else:
            y, mo = _add_months(today, n)
            d = date(y, mo, min(today.day, calendar.monthrange(y, mo)[1]))
        dates.append(_DateHit(d, role=sc.take_role(m.end())))

    # 3. 日付
    for pattern, handler in _date_patterns(today):
        for m in sc.matches(re.compile(pattern)):
            hit = handler(m)
            if hit is None:
                continue
            sc.take(m)
            hit.role = sc.take_role(m.end())
            dates.append(hit)
    dates.sort(key=lambda h: h.role == "until")
    hint = hint or next((d.hint for d in dates if d.hint), None)

    # 4. 時刻
    times: list[_TimeHit] = []
    for m in sc.matches(_TIME_RE):
        mi = 30 if m["half"] else int(m["mm"] or m["m"] or 0)
        conv = _to_minute(int(m["h"]), mi, m["pre"], m["suf"], hint)
        if conv is None:
            continue
        sc.take(m)
        times.append(_TimeHit(conv[0], role=sc.take_role(m.end()), ambiguous=conv[1]))

    def pick(items, until: bool):
        if rec_kw is None:  # 繰り返しがなければ「まで」も普通の日時として扱う
            return items[0] if items and not until else None
        return next((x for x in items if (x.role == "until") == until), None)

    # 5. 曖昧語(数字の時刻が無いときだけ)
    if pick(times, False) is None:
        words = dict(DEFAULT_FUZZY_TIMES)
        for w, t in (aliases or {}).items():
            words[w] = t.hour * 60 + t.minute
        if m := sc.first(_fuzzy_re(words)):
            sc.take(m)
            times.insert(0, _TimeHit(words[m["w"]], role=sc.take_role(m.end())))

    date_hit, time_hit = pick(dates, False), pick(times, False)
    if not (rec_kw or rel_dt or date_hit or time_hit):
        return ParseResult("fail", reasons=["日時が読み取れませんでした"])

    if date_hit and date_hit.vague:
        reasons.append(date_hit.vague)
    if time_hit and time_hit.ambiguous and not date_hit:
        reasons.append(f"午前/午後が分からないので{_fmt_minute(time_hit.minute)}にしました")

    minute = time_hit.minute if time_hit else None
    if minute is None and date_hit and date_hit.default_minute is not None:
        minute = date_hit.default_minute
    if minute is None and rec_minute is not None:
        minute = rec_minute

    def need_minute() -> int:
        if minute is not None:
            return minute
        reasons.append("時刻の指定がないので9:00にしました")
        return DEFAULT_MINUTE

    # 6. 組み立て
    rec: Recurrence | None = None
    if rec_kw is None:
        if rel_dt:
            first = rel_dt
        elif date_hit:
            first = combine(date_hit.day, need_minute(), now.tzinfo)
            if first <= now and date_hit.roll_days:
                first += timedelta(days=date_hit.roll_days)
            elif first <= now:
                reasons.append("過去の日時になっています")
        else:
            first = combine(today, need_minute(), now.tzinfo)
            if first <= now:
                first += timedelta(days=1)
    else:
        if rec_kw["kind"] == INTERVAL:
            if rec_kw["interval"] < MIN_INTERVAL:
                rec_kw["interval"] = MIN_INTERVAL
                reasons.append("間隔は最短5分にしました")
            interval = rec_kw["interval"]
            if rel_dt:
                first = rel_dt
            elif date_hit or time_hit:
                first = combine(date_hit.day if date_hit else today, need_minute(), now.tzinfo)
                while first <= now:
                    first += interval
            else:
                first = now.replace(second=0, microsecond=0) + interval
        else:
            probe = Recurrence(**rec_kw)
            first = first_occurrence(probe, now, need_minute(), date_hit.day if date_hit else None)
            if rec_kw.get("week_step", 1) > 1:
                rec_kw["anchor"] = first

        until = None
        u_date, u_time = pick(dates, True), pick(times, True)
        if u_date or u_time:
            u_day = u_date.day if u_date else first.date()
            until = combine(u_day, u_time.minute if u_time else 23 * 60 + 59, now.tzinfo)
            if until < first and not u_date:
                until += timedelta(days=1)
        elif rec_kw["kind"] == INTERVAL and count is None:
            until = first + timedelta(days=1)
            reasons.append("回数・終わりの指定がないので24時間で止めます")
        rec = Recurrence(**rec_kw, count=count, until=until)

    content = extract_content(sc.segments())
    if not content:
        content = DEFAULT_CONTENT
        reasons.append("内容が読み取れませんでした")

    return ParseResult("confirm" if reasons else "ok", first, rec, content, reasons)
