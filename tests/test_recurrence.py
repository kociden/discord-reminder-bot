from datetime import timedelta

from conftest import NOW, jst
from reminder_bot.models import DAILY, INTERVAL, MONTH_END, MONTHLY, WEEKDAYS, WEEKLY, Recurrence
from reminder_bot.recurrence import first_occurrence, month_day, next_occurrence


def test_month_day_clamps():
    assert month_day(2026, 2, 31) == 28
    assert month_day(2026, 11, MONTH_END) == 30
    assert month_day(2026, 10, 25) == 25


def test_interval_next_and_until():
    rec = Recurrence(INTERVAL, interval=timedelta(minutes=30), until=jst(2026, 10, 11, 11, 0))
    assert next_occurrence(rec, jst(2026, 10, 11, 10, 30)) == jst(2026, 10, 11, 11, 0)
    assert next_occurrence(rec, jst(2026, 10, 11, 11, 0)) is None


def test_daily_first_today_or_tomorrow():
    rec = Recurrence(DAILY)
    assert first_occurrence(rec, NOW, 22 * 60) == jst(2026, 10, 11, 22, 0)
    assert first_occurrence(rec, NOW, 9 * 60) == jst(2026, 10, 12, 9, 0)


def test_weekdays_skip_weekend():
    rec = Recurrence(WEEKDAYS)
    assert first_occurrence(rec, NOW, 8 * 60) == jst(2026, 10, 12, 8, 0)
    assert next_occurrence(rec, jst(2026, 10, 16, 8, 0)) == jst(2026, 10, 19, 8, 0)


def test_weekly_multiple_days():
    rec = Recurrence(WEEKLY, weekdays=frozenset({0, 3}))
    assert next_occurrence(rec, jst(2026, 10, 12, 7, 30)) == jst(2026, 10, 15, 7, 30)
    assert next_occurrence(rec, jst(2026, 10, 15, 7, 30)) == jst(2026, 10, 19, 7, 30)


def test_biweekly():
    rec = Recurrence(WEEKLY, weekdays=frozenset({2}), week_step=2, anchor=jst(2026, 10, 14, 19, 0))
    assert next_occurrence(rec, jst(2026, 10, 14, 19, 0)) == jst(2026, 10, 28, 19, 0)


def test_monthly_end_and_clamp():
    rec = Recurrence(MONTHLY, day_of_month=MONTH_END)
    assert next_occurrence(rec, jst(2026, 10, 31, 18, 0)) == jst(2026, 11, 30, 18, 0)
    rec31 = Recurrence(MONTHLY, day_of_month=31)
    assert next_occurrence(rec31, jst(2027, 1, 31, 9, 0)) == jst(2027, 2, 28, 9, 0)
    assert next_occurrence(rec31, jst(2027, 2, 28, 9, 0)) == jst(2027, 3, 31, 9, 0)
    assert next_occurrence(rec31, jst(2026, 12, 31, 9, 0)) == jst(2027, 1, 31, 9, 0)
