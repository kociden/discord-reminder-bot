from datetime import timedelta

from conftest import NOW, jst
from reminder_bot.formatting import (
    describe_recurrence,
    fmt_dt,
    format_confirm,
    format_notification,
    format_registered,
)
from reminder_bot.models import DAILY, INTERVAL, MONTH_END, MONTHLY, WEEKDAYS, WEEKLY, Recurrence, Reminder
from reminder_bot.parser import parse


def test_fmt_dt():
    assert fmt_dt(jst(2026, 10, 11, 18, 0), NOW) == "10/11(日) 18:00"
    assert fmt_dt(jst(2027, 1, 2, 9, 5), NOW) == "2027/1/2(土) 09:05"


def test_describe_recurrence():
    assert describe_recurrence(Recurrence(INTERVAL, interval=timedelta(hours=1), count=3), NOW) == "1時間おき・3回"
    assert describe_recurrence(Recurrence(INTERVAL, interval=timedelta(minutes=90)), NOW) == "1時間30分おき"
    assert describe_recurrence(Recurrence(DAILY), NOW) == "毎日"
    assert describe_recurrence(Recurrence(WEEKDAYS), NOW) == "平日"
    assert describe_recurrence(Recurrence(WEEKLY, weekdays=frozenset({3, 0})), NOW) == "毎週 月・木"
    assert describe_recurrence(Recurrence(WEEKLY, weekdays=frozenset({2}), week_step=2), NOW) == "隔週 水"
    assert describe_recurrence(Recurrence(MONTHLY, day_of_month=MONTH_END), NOW) == "毎月末"
    assert describe_recurrence(
        Recurrence(MONTHLY, day_of_month=25, until=jst(2026, 12, 31, 23, 59)), NOW
    ) == "毎月25日・12/31(木) 23:59まで"


def test_registered_lists_interval_times():
    r = parse("今日の18時から1時間おきに3回ゲームジャムのコンパスリマインド", NOW)
    text = format_registered(7, r.first_at, r.recurrence, r.content, NOW)
    assert "10/11(日) 18:00 / 19:00 / 20:00" in text
    assert "ゲームジャムのコンパス" in text
    assert "#7" in text


def test_confirm_shows_reasons():
    r = parse("3時に電話", NOW)
    text = format_confirm(r, NOW)
    assert "午前/午後" in text
    assert "15:00" in text


def test_notification():
    rec = Recurrence(INTERVAL, interval=timedelta(hours=1), count=3)
    rem = Reminder(123, 1, "コンパス", jst(2026, 10, 11, 19, 0), rec, count_done=1)
    assert format_notification(rem, late=False, now=NOW) == "<@123> ⏰ **コンパス** (2/3回目)"
    single = Reminder(123, 1, "試合", jst(2026, 10, 11, 15, 0))
    assert "遅れて通知" in format_notification(single, late=True, now=NOW)

