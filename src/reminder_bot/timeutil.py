from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def now() -> datetime:
    return datetime.now(JST)


def combine(day: date, minute: int, tz=JST) -> datetime:
    """day の 0:00 から minute 分後。minute >= 1440 は翌日以降になる。"""
    return datetime.combine(day, time(0), tzinfo=tz) + timedelta(minutes=minute)
