from datetime import timedelta

from conftest import jst
from reminder_bot.models import Nag, Reminder
from reminder_bot.scheduler import NAG_INTERVAL, NAG_MAX, plan_after_nag
from reminder_bot.store import Store

T0 = jst(2026, 10, 12, 15, 0)


def nag(sent=0, next_at=T0 + NAG_INTERVAL):
    return Nag(reminder_id=1, user_id=1, channel_id=2, content="x", next_at=next_at, sent=sent, id=1)


def test_plan_after_nag_continues_until_max():
    assert plan_after_nag(nag(0), T0 + NAG_INTERVAL) == (T0 + 2 * NAG_INTERVAL, 1)
    assert plan_after_nag(nag(NAG_MAX - 1), T0 + NAG_INTERVAL) == (None, NAG_MAX)


def test_plan_after_nag_after_downtime_schedules_from_now():
    late = T0 + timedelta(hours=3)
    assert plan_after_nag(nag(0), late) == (late + NAG_INTERVAL, 1)


def make():
    s = Store(":memory:")
    rid = s.add(Reminder(1, 2, "コンパス", T0))
    return s, rid


def test_nag_lifecycle_and_ack_by_any_message():
    s, rid = make()
    nid = s.start_nag(rid, 1, 2, "コンパス", message_id=100, next_at=T0 + NAG_INTERVAL)
    assert [n.id for n in s.due_nags(T0 + NAG_INTERVAL)] == [nid]
    s.add_nag_message(nid, 101)
    s.update_nag(nid, T0 + 2 * NAG_INTERVAL, 1)
    assert s.due_nags(T0 + NAG_INTERVAL) == []
    assert not s.ack_message(101, user_id=999)  # 他人のリアクションでは止まらない
    assert s.ack_message(101, user_id=1)
    assert s.due_nags(T0 + timedelta(days=1)) == []
    assert not s.ack_message(100, user_id=1)  # 既に完了


def test_nag_stops_at_max():
    s, rid = make()
    nid = s.start_nag(rid, 1, 2, "x", message_id=100, next_at=T0)
    s.update_nag(nid, None, NAG_MAX)
    assert s.due_nags(T0 + timedelta(days=1)) == []


def test_new_occurrence_supersedes_old_nag():
    s, rid = make()
    s.start_nag(rid, 1, 2, "x", message_id=100, next_at=T0)
    new = s.start_nag(rid, 1, 2, "x", message_id=200, next_at=T0)
    assert [n.id for n in s.due_nags(T0)] == [new]


def test_deleting_reminder_stops_nag():
    s, rid = make()
    s.start_nag(rid, 1, 2, "x", message_id=100, next_at=T0)
    s.deactivate(rid, user_id=1)
    assert s.due_nags(T0) == []
