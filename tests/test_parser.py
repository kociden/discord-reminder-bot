from datetime import time, timedelta

import pytest

from conftest import NOW, jst
from reminder_bot.models import DAILY, INTERVAL, MONTH_END, MONTHLY, WEEKDAYS, WEEKLY
from reminder_bot.parser import parse


def p(text, aliases=None):
    return parse(text, NOW, aliases)


# --- 単発: (入力, status, 初回日時, 内容) ---
SINGLE_CASES = [
    ("今日の15時にサンフレ試合リマインド", "ok", jst(2026, 10, 11, 15, 0), "サンフレ試合"),
    ("明日の昼ごろ会議", "ok", jst(2026, 10, 12, 12, 0), "会議"),
    ("30分後に洗濯物", "ok", jst(2026, 10, 11, 10, 30), "洗濯物"),
    ("来週金曜 夕方 飲み会の店予約", "ok", jst(2026, 10, 16, 17, 0), "飲み会の店予約"),
    ("3時に電話", "confirm", jst(2026, 10, 11, 15, 0), "電話"),
    ("明日3時に電話", "ok", jst(2026, 10, 12, 15, 0), "電話"),
    ("明日 歯医者", "confirm", jst(2026, 10, 12, 9, 0), "歯医者"),
    ("9時に起きる", "ok", jst(2026, 10, 12, 9, 0), "起きる"),
    ("夜9時半に風呂", "ok", jst(2026, 10, 11, 21, 30), "風呂"),
    ("十五時に打ち合わせ", "ok", jst(2026, 10, 11, 15, 0), "打ち合わせ"),
    ("二十一時に寝る", "ok", jst(2026, 10, 11, 21, 0), "寝る"),
    ("１５：３０に会議", "ok", jst(2026, 10, 11, 15, 30), "会議"),
    ("10/20 15時 締切", "ok", jst(2026, 10, 20, 15, 0), "締切"),
    ("10月20日 15時半 締切", "ok", jst(2026, 10, 20, 15, 30), "締切"),
    ("1時間半後に休憩終わり", "ok", jst(2026, 10, 11, 11, 30), "休憩終わり"),
    ("１時間半後に休憩終わり", "ok", jst(2026, 10, 11, 11, 30), "休憩終わり"),
    ("2時間後 洗濯", "ok", jst(2026, 10, 11, 12, 0), "洗濯"),
    ("1時間30分後に電話", "ok", jst(2026, 10, 11, 11, 30), "電話"),
    ("あと10分で出発", "ok", jst(2026, 10, 11, 10, 10), "出発"),
    ("月末に請求書", "confirm", jst(2026, 10, 31, 9, 0), "請求書"),
    ("あさって15:30 美容院", "ok", jst(2026, 10, 13, 15, 30), "美容院"),
    ("明後日の朝 ゴミ出し", "ok", jst(2026, 10, 13, 8, 0), "ゴミ出し"),
    ("金曜の19時に飲み会", "ok", jst(2026, 10, 16, 19, 0), "飲み会"),
    ("来週の月曜日 10時 定例", "ok", jst(2026, 10, 12, 10, 0), "定例"),
    ("今夜9時 映画", "ok", jst(2026, 10, 11, 21, 0), "映画"),
    ("今夜 映画", "ok", jst(2026, 10, 11, 20, 0), "映画"),
    ("3日後に返却", "confirm", jst(2026, 10, 14, 9, 0), "返却"),
    ("1週間後 振り返り", "confirm", jst(2026, 10, 18, 9, 0), "振り返り"),
    ("15時までに提出", "ok", jst(2026, 10, 11, 15, 0), "提出"),
    ("朝イチでメール返信", "ok", jst(2026, 10, 12, 9, 0), "メール返信"),
    ("12/25 クリスマス", "confirm", jst(2026, 12, 25, 9, 0), "クリスマス"),
    ("10:30 打ち合わせ", "ok", jst(2026, 10, 11, 10, 30), "打ち合わせ"),
    ("サンフレ試合を今日の15時にリマインドして", "ok", jst(2026, 10, 11, 15, 0), "サンフレ試合"),
    ("深夜2時にセール", "ok", jst(2026, 10, 12, 2, 0), "セール"),
    ("明日の夜ご飯の買い物", "confirm", jst(2026, 10, 12, 9, 0), "夜ご飯の買い物"),
    ("午後3時に荷物受け取り", "ok", jst(2026, 10, 11, 15, 0), "荷物受け取り"),
    ("夕方5時に散歩", "ok", jst(2026, 10, 11, 17, 0), "散歩"),
    ("20日 18時 支払い", "ok", jst(2026, 10, 20, 18, 0), "支払い"),
    ("来週末 キャンプ準備", "confirm", jst(2026, 10, 17, 9, 0), "キャンプ準備"),
    ("週明けに見積もり送る", "confirm", jst(2026, 10, 12, 9, 0), "見積もり送る"),
    ("2026/11/3 10時 健康診断", "ok", jst(2026, 11, 3, 10, 0), "健康診断"),
    ("pm3時 来客", "ok", jst(2026, 10, 11, 15, 0), "来客"),
    ("明日18時から飲み会って教えて", "ok", jst(2026, 10, 12, 18, 0), "飲み会"),
    ("明日の朝8時 病院 よろしく", "ok", jst(2026, 10, 12, 8, 0), "病院"),
    ("明日の朝", "confirm", jst(2026, 10, 12, 8, 0), "リマインダー"),
]


@pytest.mark.parametrize("text,status,first,content", SINGLE_CASES)
def test_single(text, status, first, content):
    r = p(text)
    assert (r.status, r.first_at, r.content) == (status, first, content), r.reasons
    assert r.recurrence is None


def test_fail_without_datetime():
    assert p("会議").status == "fail"
    assert p("").status == "fail"


def test_reasons_present_when_confirm():
    r = p("3時に電話")
    assert r.reasons


# --- 繰り返し ---

def test_interval_with_start_and_count():
    r = p("今日の18時から1時間おきに3回ゲームジャムのコンパスリマインド")
    assert r.status == "ok"
    assert r.first_at == jst(2026, 10, 11, 18, 0)
    assert r.content == "ゲームジャムのコンパス"
    rec = r.recurrence
    assert (rec.kind, rec.interval, rec.count) == (INTERVAL, timedelta(hours=1), 3)


def test_interval_until():
    r = p("21時まで30分おきに水飲む")
    assert r.status == "ok"
    assert r.first_at == jst(2026, 10, 11, 10, 30)
    assert r.recurrence.until == jst(2026, 10, 11, 21, 0)
    assert r.recurrence.interval == timedelta(minutes=30)
    assert r.content == "水飲む"


def test_interval_count_only():
    r = p("5分おきに3回 ストレッチ")
    assert r.status == "ok"
    assert r.first_at == jst(2026, 10, 11, 10, 5)
    assert r.recurrence.count == 3
    assert r.content == "ストレッチ"


def test_interval_without_limit_needs_confirm():
    r = p("毎時 水分")
    assert r.status == "confirm"
    assert r.recurrence.interval == timedelta(hours=1)
    assert r.recurrence.until == r.first_at + timedelta(days=1)
    assert r.content == "水分"


def test_interval_minimum():
    r = p("1分おきに3回 テスト")
    assert r.status == "confirm"
    assert r.recurrence.interval == timedelta(minutes=5)


def test_interval_past_start_aligns_forward():
    r = p("今日の9時から1時間ごとに5回 水")
    assert r.first_at == jst(2026, 10, 11, 11, 0)


def test_interval_half_hour_unit():
    r = p("1時間半おきに 目薬")
    assert r.recurrence.interval == timedelta(minutes=90)
    assert r.content == "目薬"


def test_weekly_morning():
    r = p("毎週月曜の朝ゴミ出し")
    assert r.status == "ok"
    assert r.first_at == jst(2026, 10, 12, 8, 0)
    assert (r.recurrence.kind, r.recurrence.weekdays) == (WEEKLY, frozenset({0}))
    assert r.content == "ゴミ出し"


def test_weekly_multi():
    r = p("毎週月・木 7時半 ゴミ")
    assert r.recurrence.weekdays == frozenset({0, 3})
    assert r.first_at == jst(2026, 10, 12, 7, 30)
    assert r.content == "ゴミ"


def test_weekly_multi_without_maishuu():
    r = p("月曜と木曜の20時 ジム")
    assert r.recurrence.kind == WEEKLY
    assert r.recurrence.weekdays == frozenset({0, 3})
    assert r.content == "ジム"


def test_weekly_mainichiyou():
    r = p("毎日曜 10時 洗車")
    assert r.recurrence.weekdays == frozenset({6})
    assert r.first_at == jst(2026, 10, 18, 10, 0)


def test_biweekly():
    r = p("隔週水曜 19時 燃えないゴミ")
    rec = r.recurrence
    assert (rec.kind, rec.weekdays, rec.week_step) == (WEEKLY, frozenset({2}), 2)
    assert r.first_at == jst(2026, 10, 14, 19, 0)
    assert rec.anchor == r.first_at


def test_weekdays():
    r = p("平日8時に体温測る")
    assert r.status == "ok"
    assert r.recurrence.kind == WEEKDAYS
    assert r.first_at == jst(2026, 10, 12, 8, 0)
    assert r.content == "体温測る"


def test_daily():
    r = p("毎日22時に薬")
    assert r.status == "ok"
    assert r.recurrence.kind == DAILY
    assert r.first_at == jst(2026, 10, 11, 22, 0)
    assert r.content == "薬"


def test_daily_without_time_confirms():
    r = p("毎日ストレッチ")
    assert r.status == "confirm"
    assert r.first_at == jst(2026, 10, 12, 9, 0)


def test_maiban():
    r = p("毎晩 日記")
    assert r.status == "ok"
    assert r.first_at == jst(2026, 10, 11, 20, 0)
    assert r.content == "日記"


def test_monthly_day():
    r = p("毎月25日に家賃")
    assert r.status == "confirm"
    assert (r.recurrence.kind, r.recurrence.day_of_month) == (MONTHLY, 25)
    assert r.first_at == jst(2026, 10, 25, 9, 0)
    assert r.content == "家賃"


def test_monthly_end():
    r = p("毎月末 18時 経費精算")
    assert r.status == "ok"
    assert r.recurrence.day_of_month == MONTH_END
    assert r.first_at == jst(2026, 10, 31, 18, 0)


def test_daily_until_date():
    r = p("10/20まで毎日21時 ストレッチ")
    assert r.recurrence.kind == DAILY
    assert r.recurrence.until == jst(2026, 10, 20, 23, 59)
    assert r.first_at == jst(2026, 10, 11, 21, 0)


def test_start_date_for_daily():
    r = p("明日から毎朝 ラジオ体操")
    assert r.first_at == jst(2026, 10, 12, 8, 0)
    assert r.content == "ラジオ体操"


# --- ユーザー辞書 ---

def test_alias_overrides_default():
    r = p("昼ごろ ランチ", aliases={"昼ごろ": time(12, 30)})
    assert r.first_at == jst(2026, 10, 11, 12, 30)
    assert r.content == "ランチ"


def test_alias_new_word():
    r = p("明日 出勤前に 鍵", aliases={"出勤前": time(7, 45)})
    assert r.first_at == jst(2026, 10, 12, 7, 45)
    assert r.content == "鍵"
