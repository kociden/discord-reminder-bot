from __future__ import annotations

from datetime import datetime, timedelta

from .models import Reminder

# (セレクトに出す名前, 何分後か)。Discord のセレクトは最大25項目。
SNOOZE_OPTIONS: list[tuple[str, int]] = [
    ("5分後", 5),
    ("10分後", 10),
    ("15分後", 15),
    ("30分後", 30),
    ("1時間後", 60),
    ("2時間後", 120),
    ("3時間後", 180),
    ("6時間後", 360),
    ("12時間後", 720),
    ("24時間後", 1440),
]


def label_for(minutes: int) -> str:
    return next((name for name, m in SNOOZE_OPTIONS if m == minutes), f"{minutes}分後")


def snoozed_reminder(user_id: int, channel_id: int, content: str, minutes: int, now: datetime) -> Reminder:
    """元と同じ内容を minutes 分後に1回だけ通知するリマインダー。"""
    return Reminder(user_id, channel_id, content, now + timedelta(minutes=minutes))
