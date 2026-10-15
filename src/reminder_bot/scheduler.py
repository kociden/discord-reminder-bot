from __future__ import annotations

from datetime import datetime, timedelta

from .models import Reminder
from .recurrence import next_occurrence

LATE_THRESHOLD = timedelta(minutes=2)


def is_late(scheduled: datetime, now: datetime) -> bool:
    return now - scheduled > LATE_THRESHOLD


def plan_after_fire(rem: Reminder, now: datetime) -> tuple[datetime | None, int]:
    """通知を1回送った後の (次回日時 or None, 実行済み回数)。

    停止中に過ぎた回は今回の通知にまとめたものとして回数に数え、次回は now より後にする。
    """
    done = rem.count_done + 1
    rec = rem.recurrence
    if rec is None:
        return None, done
    nxt = next_occurrence(rec, rem.next_at)
    while nxt is not None and nxt <= now:
        if rec.count is not None and done >= rec.count:
            return None, done
        done += 1
        nxt = next_occurrence(rec, nxt)
    if nxt is None or (rec.count is not None and done >= rec.count):
        return None, done
    return nxt, done
