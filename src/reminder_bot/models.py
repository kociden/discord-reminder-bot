from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

INTERVAL = "interval"
DAILY = "daily"
WEEKDAYS = "weekdays"
WEEKLY = "weekly"
MONTHLY = "monthly"

MONTH_END = -1  # day_of_month の「月末」


@dataclass(frozen=True)
class Recurrence:
    kind: str
    interval: timedelta | None = None
    weekdays: frozenset[int] = frozenset()  # 0=月
    day_of_month: int | None = None
    week_step: int = 1
    anchor: datetime | None = None  # 隔週の基準(初回)
    count: int | None = None  # 総回数(初回を含む)
    until: datetime | None = None


@dataclass
class ParseResult:
    status: str  # "ok" | "confirm" | "fail"
    first_at: datetime | None = None
    recurrence: Recurrence | None = None
    content: str = ""
    reasons: list[str] = field(default_factory=list)


@dataclass
class Reminder:
    user_id: int
    channel_id: int
    content: str
    next_at: datetime
    recurrence: Recurrence | None = None
    count_done: int = 0
    active: bool = True
    id: int | None = None
