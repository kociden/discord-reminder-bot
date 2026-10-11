from datetime import timedelta

from conftest import jst
from reminder_bot.models import DAILY, INTERVAL, Recurrence, Reminder
from reminder_bot.scheduler import is_late, plan_after_fire


def rem(next_at, rec=None, done=0):
    return Reminder(user_id=1, channel_id=2, content="x", next_at=next_at, recurrence=rec, count_done=done)


def test_single_finishes():
    assert plan_after_fire(rem(jst(2026, 10, 11, 15, 0)), jst(2026, 10, 11, 15, 0)) == (None, 1)


def test_interval_count():
    rec = Recurrence(INTERVAL, interval=timedelta(hours=1), count=3)
    r = rem(jst(2026, 10, 11, 18, 0), rec)
    assert plan_after_fire(r, jst(2026, 10, 11, 18, 0)) == (jst(2026, 10, 11, 19, 0), 1)
    r = rem(jst(2026, 10, 11, 20, 0), rec, done=2)
    assert plan_after_fire(r, jst(2026, 10, 11, 20, 0)) == (None, 3)


def test_until_stops():
    rec = Recurrence(INTERVAL, interval=timedelta(minutes=30), until=jst(2026, 10, 11, 21, 0))
    assert plan_after_fire(rem(jst(2026, 10, 11, 21, 0), rec), jst(2026, 10, 11, 21, 0))[0] is None


def test_missed_occurrences_skip_to_future():
    rec = Recurrence(DAILY)
    r = rem(jst(2026, 10, 8, 9, 0), rec)
    assert plan_after_fire(r, jst(2026, 10, 11, 10, 0)) == (jst(2026, 10, 12, 9, 0), 4)


def test_missed_with_count_finishes():
    rec = Recurrence(INTERVAL, interval=timedelta(hours=1), count=3)
    r = rem(jst(2026, 10, 11, 18, 0), rec)
    assert plan_after_fire(r, jst(2026, 10, 11, 23, 0)) == (None, 3)


def test_is_late():
    assert not is_late(jst(2026, 10, 11, 10, 0), jst(2026, 10, 11, 10, 1))
    assert is_late(jst(2026, 10, 11, 10, 0), jst(2026, 10, 11, 10, 5))
