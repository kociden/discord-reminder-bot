# Discord リマインダーBot

メンションしてアバウトな日本語を書くだけでリマインダーを登録できる、自分専用の Discord Bot。
外部API不要・AI不要(ルールベース)で、UGREEN NAS の Docker で動かす想定。

```
@reminder 今日の15時にサンフレ試合リマインド
@reminder 今日の18時から1時間おきに3回ゲームジャムのコンパスリマインド
@reminder 明日の昼ごろ会議
@reminder 毎週月曜の朝ゴミ出し
@reminder 21時まで30分おきに水飲む
```

- 自信がある解釈 → 即登録(↩️取り消しボタン付き)
- 曖昧なとき(時刻なし・「3時」が午前か午後か不明など) → ✅登録 / 🕒書き直す / ❌やめる で確認
- `@reminder 一覧`、`@reminder 削除 3`、`/list`、`/delete`、`/alias set 昼ごろ 12:30`

読み取れる表現の一覧は [設計書](docs/superpowers/specs/2026-10-11-discord-reminder-bot-design.md) の4章を参照。

---

## 1. Discord 側の準備

1. https://discord.com/developers/applications → **New Application**(名前は `reminder` など)
2. 左メニュー **Bot**
   - **Reset Token** → 表示されたトークンをコピー(`.env` の `DISCORD_TOKEN`)
   - **Privileged Gateway Intents** の **Message Content Intent** を **ON** にして保存
3. 左メニュー **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `View Channels`, `Send Messages`, `Read Message History`
   - 生成されたURLを開いて自分のサーバーに追加
4. 自分のユーザーIDを取得: Discord の 設定 → 詳細設定 → **開発者モード** ON → 自分のアイコンを右クリック → **ユーザーIDをコピー**(`OWNER_ID`)
5. (任意)サーバーアイコンを右クリック → **サーバーIDをコピー**(`GUILD_ID`。入れるとスラッシュコマンドが即反映)

## 2. UGREEN NAS で動かす

### 方法A: SSH(確実)

UGOS の **コントロールパネル → ターミナル** で SSH を有効にしてから、PCで:

```bash
ssh <NASのユーザー名>@<NASのIP>
```

```bash
cd /volume1/docker
git clone https://github.com/kociden/discord-reminder-bot.git
cd discord-reminder-bot
cp .env.example .env
vi .env   # DISCORD_TOKEN / OWNER_ID / GUILD_ID を記入
sudo docker compose up -d --build
sudo docker compose logs -f   # 「ログインしました」が出ればOK(Ctrl+Cで抜ける)
```

※ リポジトリは private なので、`git clone` で GitHub のユーザー名と Personal Access Token を聞かれる。
面倒なら方法Bのようにフォルダごとコピーしてもよい。`/volume1/docker` は環境に合わせて変更。

### 方法B: Docker アプリの「プロジェクト」(GUI)

1. PCからエクスプローラーで NAS の共有フォルダ(例: `\\<NASのIP>\docker\`)にこのフォルダをコピー
2. `.env.example` をコピーして `.env` を作り、値を記入
3. UGOS の **Docker → プロジェクト → 作成** で、コピーしたフォルダを選択(`docker-compose.yml` が読み込まれる)→ 作成・起動

### 更新するとき

```bash
cd /volume1/docker/discord-reminder-bot
git pull
sudo docker compose up -d --build
```

データ(リマインダーと辞書)は `./data/reminder.db` に保存されるので、再ビルドしても消えない。

## 3. 開発

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # macOS/Linux は .venv/bin/python
.venv/Scripts/python -m pytest
```

| ファイル | 役割 |
|---|---|
| `src/reminder_bot/parser/` | 日本語 → 日時・繰り返し・内容(Discord 非依存) |
| `src/reminder_bot/recurrence.py` | 繰り返しの次回計算 |
| `src/reminder_bot/scheduler.py` | 通知後の次回・回数計算 |
| `src/reminder_bot/store.py` | SQLite |
| `src/reminder_bot/formatting.py` | 返信・通知の文面 |
| `src/reminder_bot/bot.py` | Discord(メンション・ボタン・スラッシュコマンド・30秒ごとの通知ループ) |

読み取れない言い回しを見つけたら `tests/test_parser.py` にケースを足してから `parser/core.py` を直す。
