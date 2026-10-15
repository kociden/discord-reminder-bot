from datetime import timedelta

from conftest import NOW
from reminder_bot.snooze import SNOOZE_OPTIONS, label_for, snoozed_reminder
from reminder_bot.store import Store


def test_snoozed_reminder_is_one_shot_after_delay():
    rem = snoozed_reminder(1, 2, "コンパス", 30, NOW)
    assert rem.next_at == NOW + timedelta(minutes=30)
    assert rem.recurrence is None
    assert (rem.user_id, rem.channel_id, rem.content) == (1, 2, "コンパス")


def test_options_fit_discord_select_and_are_unique():
    assert len(SNOOZE_OPTIONS) <= 25
    assert len({m for _, m in SNOOZE_OPTIONS}) == len(SNOOZE_OPTIONS)
    assert label_for(60) == "1時間後"
    assert label_for(7) == "7分後"


def test_notified_roundtrip():
    s = Store(":memory:")
    assert s.get_notified(100) is None
    s.record_notified(100, 1, 2, "試合")
    assert s.get_notified(100) == (1, 2, "試合")
