# Discord リマインダーBot 実装計画

> 設計書: `docs/superpowers/specs/2026-10-11-discord-reminder-bot-design.md`

**Goal:** メンション+アバウトな日本語でリマインダーを登録できる Discord Bot を、UGREEN NAS の Docker で動かす。

**Architecture:** Discord 非依存の純粋関数(parser / recurrence / scheduler 計算 / formatting)を pytest で固め、
薄い discord.py 層(bot.py)から呼ぶ。永続化は SQLite。

**Tech Stack:** Python 3.12, discord.py 2.x, sqlite3, tzdata, pytest, Docker Compose

---

## ファイル構成

| ファイル | 責務 |
|---|---|
| `src/reminder_bot/models.py` | `Recurrence`, `ParseResult`, `Reminder` データ型 |
| `src/reminder_bot/timeutil.py` | JST 定数・`now()`・`combine(day, minute)` |
| `src/reminder_bot/recurrence.py` | `first_occurrence`, `next_occurrence`, `month_day` |
| `src/reminder_bot/parser/normalize.py` | NFKC・漢数字・記号の正規化 |
| `src/reminder_bot/parser/scanner.py` | 消費済み範囲を管理しながら正規表現を当てる |
| `src/reminder_bot/parser/content.py` | 残りテキストから本文を抽出 |
| `src/reminder_bot/parser/core.py` | `parse(text, now, aliases)` 本体 |
| `src/reminder_bot/scheduler.py` | `plan_after_fire`(発火後の次回計算) |
| `src/reminder_bot/store.py` | SQLite 永続化 |
| `src/reminder_bot/formatting.py` | 返信文・通知文 |
| `src/reminder_bot/bot.py` | discord.py(メンション・ボタン・モーダル・スラッシュコマンド・ループ) |
| `src/reminder_bot/main.py` | 環境変数読み込み・起動 |

## タスク

- [ ] 1. プロジェクト雛形(pyproject, .gitignore, .gitattributes)
- [ ] 2. models / timeutil / recurrence + テスト
- [ ] 3. parser(normalize, scanner, content, core)+ 設計書 4.6 の全ケース+追加ケースのテスト
- [ ] 4. scheduler(`plan_after_fire`)+ テスト(回数制限・until・停止中の取りこぼし)
- [ ] 5. store + テスト(往復・due・deactivate・alias)
- [ ] 6. formatting + テスト
- [ ] 7. bot.py / main.py(import スモークテスト)
- [ ] 8. Dockerfile / docker-compose.yml / .env.example / README(Discord 設定と NAS 導入手順)
- [ ] 9. `docker build` で確認、全テスト通過、コミット・push

各タスクごとにテスト → 実装 → `pytest` → コミット。
