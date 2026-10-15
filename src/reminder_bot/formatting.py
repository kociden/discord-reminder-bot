from __future__ import annotations

from datetime import datetime, timedelta

from .models import DAILY, INTERVAL, MONTH_END, MONTHLY, WEEKDAYS, WEEKLY, ParseResult, Recurrence, Reminder
from .recurrence import next_occurrence

WD_JA = "月火水木金土日"
MAX_PREVIEW = 6

HELP_TEXT = """\
**使い方** — メンションして日本語で書くだけ
```
@reminder 今日の15時にサンフレ試合リマインド
@reminder 今日の18時から1時間おきに3回 コンパス
@reminder 明日の昼ごろ会議
@reminder 30分後に洗濯物
@reminder 毎週月曜の朝ゴミ出し
@reminder 21時まで30分おきに水飲む
```
**通知のボタン**: 「✅ 完了」で済みにする / 「💤 スヌーズ」で選んだ時間後にもう一度通知
**管理**: `@reminder 一覧` / `@reminder 削除 3` / `/list` `/delete` `/alias`"""


def fmt_dt(dt: datetime, now: datetime) -> str:
    head = f"{dt.year}/" if dt.year != now.year else ""
    return f"{head}{dt.month}/{dt.day}({WD_JA[dt.weekday()]}) {dt:%H:%M}"


def _fmt_td(td: timedelta) -> str:
    mins = int(td.total_seconds() // 60)
    if mins % 1440 == 0:
        return f"{mins // 1440}日"
    if mins >= 60:
        h, m = divmod(mins, 60)
        return f"{h}時間{m}分" if m else f"{h}時間"
    return f"{mins}分"


def describe_recurrence(rec: Recurrence, now: datetime) -> str:
    if rec.kind == INTERVAL:
        base = f"{_fmt_td(rec.interval)}おき"
    elif rec.kind == DAILY:
        base = "毎日"
    elif rec.kind == WEEKDAYS:
        base = "平日"
    elif rec.kind == WEEKLY:
        days = "・".join(WD_JA[d] for d in sorted(rec.weekdays))
        base = f"{'隔週' if rec.week_step == 2 else '毎週'} {days}"
    elif rec.kind == MONTHLY:
        base = "毎月末" if rec.day_of_month == MONTH_END else f"毎月{rec.day_of_month}日"
    else:
        base = rec.kind
    parts = [base]
    if rec.count:
        parts.append(f"{rec.count}回")
    if rec.until:
        parts.append(f"{fmt_dt(rec.until, now)}まで")
    return "・".join(parts)


def _when(first: datetime, rec: Recurrence | None, now: datetime) -> str:
    """回数が少ない間隔指定は全時刻を並べる。それ以外は初回日時。"""
    if rec and rec.kind == INTERVAL and rec.count and rec.count <= MAX_PREVIEW:
        times = [first]
        while len(times) < rec.count and (n := next_occurrence(rec, times[-1])):
            times.append(n)
        if all(t.date() == first.date() for t in times):
            return fmt_dt(first, now) + "".join(f" / {t:%H:%M}" for t in times[1:])
        return " / ".join(fmt_dt(t, now) for t in times)
    return fmt_dt(first, now)


def _body(first: datetime, rec: Recurrence | None, content: str, now: datetime) -> list[str]:
    lines = [f"📅 {_when(first, rec, now)}"]
    if rec:
        lines.append(f"🔁 {describe_recurrence(rec, now)}")
    lines.append(f"📝 {content}")
    return lines


def format_registered(rid: int, first: datetime, rec: Recurrence | None, content: str, now: datetime) -> str:
    return "\n".join([f"✅ 登録しました (#{rid})", *_body(first, rec, content, now)])


def format_confirm(result: ParseResult, now: datetime) -> str:
    lines = ["🤔 この内容で登録しますか？", *_body(result.first_at, result.recurrence, result.content, now)]
    lines += [f"⚠️ {r}" for r in result.reasons]
    return "\n".join(lines)


def format_list(reminders: list[Reminder], now: datetime) -> str:
    if not reminders:
        return "登録中のリマインダーはありません"
    lines = ["**登録中のリマインダー**"]
    for r in reminders:
        rep = f" 🔁 {describe_recurrence(r.recurrence, now)}" if r.recurrence else ""
        lines.append(f"`#{r.id}` {fmt_dt(r.next_at, now)}{rep} — {r.content}")
    return "\n".join(lines)


def format_notification(rem: Reminder, late: bool, now: datetime) -> str:
    text = f"<@{rem.user_id}> ⏰ **{rem.content}**"
    if rem.recurrence and rem.recurrence.count:
        text += f" ({rem.count_done + 1}/{rem.recurrence.count}回目)"
    if late:
        text += f"\n(遅れて通知: 予定 {fmt_dt(rem.next_at, now)})"
    return text
