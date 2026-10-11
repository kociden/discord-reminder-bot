from datetime import time, timedelta

from conftest import jst
from reminder_bot.models import INTERVAL, WEEKLY, Recurrence, Reminder
from reminder_bot.store import Store


def make_store():
    return Store(":memory:")


def test_roundtrip_with_recurrence():
    s = make_store()
    rec = Recurrence(WEEKLY, weekdays=frozenset({0, 3}), week_step=2, anchor=jst(2026, 10, 12, 8, 0),
                     count=5, until=jst(2026, 12, 31, 23, 59))
    rid = s.add(Reminder(1, 2, "ゴミ", jst(2026, 10, 12, 8, 0), rec))
    [got] = s.active(1)
    assert got.id == rid
    assert got.recurrence == rec
    assert got.next_at == jst(2026, 10, 12, 8, 0)
    assert got.content == "ゴミ"


def test_due_and_update():
    s = make_store()
    rec = Recurrence(INTERVAL, interval=timedelta(minutes=30))
    rid = s.add(Reminder(1, 2, "水", jst(2026, 10, 11, 10, 0), rec))
    s.add(Reminder(1, 2, "後で", jst(2026, 10, 11, 12, 0)))
    assert [r.id for r in s.due(jst(2026, 10, 11, 10, 0))] == [rid]
    s.update_after_fire(rid, jst(2026, 10, 11, 10, 30), 1)
    assert s.due(jst(2026, 10, 11, 10, 0)) == []
    s.update_after_fire(rid, None, 2)
    assert [r.content for r in s.active(1)] == ["後で"]


def test_deactivate_only_own():
    s = make_store()
    rid = s.add(Reminder(1, 2, "x", jst(2026, 10, 11, 12, 0)))
    assert not s.deactivate(rid, user_id=999)
    assert s.deactivate(rid, user_id=1)
    assert not s.deactivate(rid, user_id=1)
    assert s.active(1) == []


def test_aliases():
    s = make_store()
    s.set_alias("昼ごろ", time(12, 30))
    s.set_alias("昼ごろ", time(12, 45))
    assert s.aliases() == {"昼ごろ": time(12, 45)}
    assert s.delete_alias("昼ごろ")
    assert not s.delete_alias("昼ごろ")
