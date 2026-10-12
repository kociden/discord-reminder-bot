from __future__ import annotations

import sqlite3
from datetime import datetime, time, timedelta

from .models import Nag, Recurrence, Reminder

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    next_at TEXT NOT NULL,
    kind TEXT,
    interval_sec INTEGER,
    weekdays TEXT,
    day_of_month INTEGER,
    week_step INTEGER,
    anchor_at TEXT,
    count_total INTEGER,
    count_done INTEGER NOT NULL DEFAULT 0,
    until_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders (active, next_at);
CREATE TABLE IF NOT EXISTS aliases (
    word TEXT PRIMARY KEY,
    hh INTEGER NOT NULL,
    mm INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS nags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    next_at TEXT NOT NULL,
    sent INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_nags_due ON nags (active, next_at);
CREATE TABLE IF NOT EXISTS nag_messages (
    message_id INTEGER PRIMARY KEY,
    nag_id INTEGER NOT NULL
);
"""


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


class Store:
    def __init__(self, path: str):
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)

    def add(self, rem: Reminder) -> int:
        rec = rem.recurrence
        cur = self._db.execute(
            """INSERT INTO reminders (user_id, channel_id, content, next_at, kind, interval_sec, weekdays,
                   day_of_month, week_step, anchor_at, count_total, count_done, until_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rem.user_id, rem.channel_id, rem.content, _iso(rem.next_at),
                rec.kind if rec else None,
                int(rec.interval.total_seconds()) if rec and rec.interval else None,
                ",".join(map(str, sorted(rec.weekdays))) if rec else None,
                rec.day_of_month if rec else None,
                rec.week_step if rec else None,
                _iso(rec.anchor) if rec else None,
                rec.count if rec else None,
                rem.count_done,
                _iso(rec.until) if rec else None,
            ),
        )
        self._db.commit()
        return cur.lastrowid

    def _row(self, r: sqlite3.Row) -> Reminder:
        rec = None
        if r["kind"]:
            rec = Recurrence(
                kind=r["kind"],
                interval=timedelta(seconds=r["interval_sec"]) if r["interval_sec"] else None,
                weekdays=frozenset(int(x) for x in r["weekdays"].split(",") if x) if r["weekdays"] else frozenset(),
                day_of_month=r["day_of_month"],
                week_step=r["week_step"] or 1,
                anchor=_dt(r["anchor_at"]),
                count=r["count_total"],
                until=_dt(r["until_at"]),
            )
        return Reminder(
            user_id=r["user_id"], channel_id=r["channel_id"], content=r["content"],
            next_at=_dt(r["next_at"]), recurrence=rec, count_done=r["count_done"],
            active=bool(r["active"]), id=r["id"],
        )

    def due(self, now: datetime) -> list[Reminder]:
        # next_at は全て同じタイムゾーンの ISO 形式なので文字列比較で順序が保たれる
        rows = self._db.execute(
            "SELECT * FROM reminders WHERE active = 1 AND next_at <= ? ORDER BY next_at", (_iso(now),)
        )
        return [self._row(r) for r in rows]

    def active(self, user_id: int) -> list[Reminder]:
        rows = self._db.execute(
            "SELECT * FROM reminders WHERE active = 1 AND user_id = ? ORDER BY next_at", (user_id,)
        )
        return [self._row(r) for r in rows]

    def update_after_fire(self, rid: int, next_at: datetime | None, count_done: int) -> None:
        if next_at is None:
            self._db.execute("UPDATE reminders SET active = 0, count_done = ? WHERE id = ?", (count_done, rid))
        else:
            self._db.execute(
                "UPDATE reminders SET next_at = ?, count_done = ? WHERE id = ?", (_iso(next_at), count_done, rid)
            )
        self._db.commit()

    def deactivate(self, rid: int, user_id: int) -> bool:
        cur = self._db.execute(
            "UPDATE reminders SET active = 0 WHERE id = ? AND user_id = ? AND active = 1", (rid, user_id)
        )
        self._db.execute("UPDATE nags SET active = 0 WHERE reminder_id = ? AND user_id = ?", (rid, user_id))
        self._db.commit()
        return cur.rowcount > 0

    # ---------- 再通知 ----------

    def start_nag(self, reminder_id: int, user_id: int, channel_id: int, content: str,
                  message_id: int, next_at: datetime) -> int:
        """通知メッセージを送った後に呼ぶ。同じリマインダーの古い再通知は止める。"""
        self._db.execute("UPDATE nags SET active = 0 WHERE reminder_id = ?", (reminder_id,))
        cur = self._db.execute(
            "INSERT INTO nags (reminder_id, user_id, channel_id, content, next_at) VALUES (?,?,?,?,?)",
            (reminder_id, user_id, channel_id, content, _iso(next_at)),
        )
        self._db.execute("INSERT OR REPLACE INTO nag_messages VALUES (?,?)", (message_id, cur.lastrowid))
        self._db.commit()
        return cur.lastrowid

    def add_nag_message(self, nag_id: int, message_id: int) -> None:
        self._db.execute("INSERT OR REPLACE INTO nag_messages VALUES (?,?)", (message_id, nag_id))
        self._db.commit()

    def due_nags(self, now: datetime) -> list[Nag]:
        rows = self._db.execute(
            "SELECT * FROM nags WHERE active = 1 AND next_at <= ? ORDER BY next_at", (_iso(now),)
        )
        return [
            Nag(r["reminder_id"], r["user_id"], r["channel_id"], r["content"], _dt(r["next_at"]), r["sent"], r["id"])
            for r in rows
        ]

    def update_nag(self, nag_id: int, next_at: datetime | None, sent: int) -> None:
        if next_at is None:
            self._db.execute("UPDATE nags SET active = 0, sent = ? WHERE id = ?", (sent, nag_id))
        else:
            self._db.execute("UPDATE nags SET next_at = ?, sent = ? WHERE id = ?", (_iso(next_at), sent, nag_id))
        self._db.commit()

    def ack_message(self, message_id: int, user_id: int) -> bool:
        """通知メッセージへのリアクションで再通知を止める。止めたら True。"""
        cur = self._db.execute(
            """UPDATE nags SET active = 0
               WHERE active = 1 AND user_id = ?
                 AND id = (SELECT nag_id FROM nag_messages WHERE message_id = ?)""",
            (user_id, message_id),
        )
        self._db.commit()
        return cur.rowcount > 0

    def aliases(self) -> dict[str, time]:
        return {r["word"]: time(r["hh"], r["mm"]) for r in self._db.execute("SELECT * FROM aliases")}

    def set_alias(self, word: str, t: time) -> None:
        self._db.execute(
            "INSERT INTO aliases (word, hh, mm) VALUES (?,?,?) ON CONFLICT(word) DO UPDATE SET hh=excluded.hh, mm=excluded.mm",
            (word, t.hour, t.minute),
        )
        self._db.commit()

    def delete_alias(self, word: str) -> bool:
        cur = self._db.execute("DELETE FROM aliases WHERE word = ?", (word,))
        self._db.commit()
        return cur.rowcount > 0
