from datetime import datetime

import pytest

from reminder_bot.timeutil import JST

# 2026-10-11 は日曜日
NOW = datetime(2026, 10, 11, 10, 0, tzinfo=JST)


def jst(*args) -> datetime:
    return datetime(*args, tzinfo=JST)


@pytest.fixture
def now():
    return NOW
