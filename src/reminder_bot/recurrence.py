from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from .models import DAILY, INTERVAL, MONTH_END, MONTHLY, WEEKDAYS, WEEKLY, Recurrence
from .timeutil import combine


def month_day(year: int, month: int, day_of_month: int) -> int:
    """day_of_month を実在する日に丸める(31日→30日、MONTH_END→末日)。"""
    last = calendar.monthrange(year, month)[1]
    if day_of_month == MONTH_END or day_of_month > last:
        return last
    return day_of_month


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _week_ok(rec: Recurrence, d: date) -> bool:
    if rec.week_step <= 1 or rec.anchor is None:
        return True
    weeks = (_monday(d) - _monday(rec.anchor.date())).days // 7
    return weeks % rec.week_step == 0


def _matches_day(rec: Recurrence, d: date) -> bool:
    if rec.kind == DAILY:
        return True
    if rec.kind == WEEKDAYS:
        return d.weekday() < 5
    if rec.kind == WEEKLY:
        return d.weekday() in rec.weekdays and _week_ok(rec, d)
    if rec.kind == MONTHLY:
        return d.day == month_day(d.year, d.month, rec.day_of_month)
    raise ValueError(rec.kind)


def first_occurrence(rec: Recurrence, now: datetime, minute: int, start_day: date | None = None) -> datetime:
    """日単位の繰り返しで、now より後かつ start_day 以降の最初の発火日時。"""
    day = max(now.date(), start_day) if start_day else now.date()
    for i in range(400):
        d = day + timedelta(days=i)
        if _matches_day(rec, d):
            cand = combine(d, minute, now.tzinfo)
            if cand > now:
                return cand
    raise ValueError("次回日時が見つかりません")


def next_occurrence(rec: Recurrence, prev: datetime) -> datetime | None:
    """prev(前回の予定日時)の次の予定日時。until を超えたら None。回数制限は見ない。"""
    if rec.kind == INTERVAL:
        n = prev + rec.interval
    elif rec.kind == MONTHLY:
        y, m = (prev.year + 1, 1) if prev.month == 12 else (prev.year, prev.month + 1)
        n = prev.replace(year=y, month=m, day=month_day(y, m, rec.day_of_month))
    else:
        n = prev + timedelta(days=1)
        while not _matches_day(rec, n.date()):
            n += timedelta(days=1)
    if rec.until is not None and n > rec.until:
        return None
    return n
