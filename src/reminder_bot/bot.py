from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import time

import discord
from discord import app_commands
from discord.ext import tasks

from .formatting import HELP_TEXT, format_confirm, format_list, format_notification, format_registered
from .models import ParseResult, Reminder
from .parser import parse
from .scheduler import is_late, plan_after_fire
from .snooze import SNOOZE_OPTIONS, label_for, snoozed_reminder
from .store import Store
from .timeutil import now

log = logging.getLogger(__name__)

VIEW_TIMEOUT = 600  # ボタンの有効期限(秒)
_LIST_RE = re.compile(r"^(?:一覧|リスト|list|ls)$", re.IGNORECASE)
_DELETE_RE = re.compile(r"^(?:削除|消して|けして|delete|del|rm)\s*#?(\d+)$", re.IGNORECASE)
_HELP_RE = re.compile(r"^(?:ヘルプ|使い方|help|\?|？)?$", re.IGNORECASE)
_HHMM_RE = re.compile(r"^(\d{1,2})[:：時](\d{0,2})分?$")
NO_PINGS = discord.AllowedMentions.none()


@dataclass
class Config:
    token: str
    owner_id: int
    db_path: str
    guild_id: int | None = None


class ReminderBot(discord.Client):
    def __init__(self, config: Config, store: Store):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.store = store
        self.tree = app_commands.CommandTree(self)

    # ---------- 起動 ----------

    async def setup_hook(self) -> None:
        _register_commands(self)
        self.add_view(SnoozeView(self))  # 再起動・更新後も古い通知のボタンを使えるようにする
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        self.tick.start()

    async def on_ready(self) -> None:
        log.info("ログインしました: %s (id=%s)", self.user, self.user.id)

    def is_owner(self, user: discord.abc.User) -> bool:
        return user.id == self.config.owner_id

    # ---------- メンション ----------

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not self.is_owner(message.author):
            return
        is_dm = isinstance(message.channel, discord.DMChannel)
        if not is_dm and self.user not in message.mentions:
            return
        text = re.sub(rf"<@!?{self.user.id}>", "", message.content).strip()
        await self.handle_text(message, text)

    async def handle_text(self, message: discord.Message, text: str) -> None:
        if _HELP_RE.match(text):
            await message.reply(HELP_TEXT, allowed_mentions=NO_PINGS)
            return
        if _LIST_RE.match(text):
            await message.reply(format_list(self.store.active(message.author.id), now()), allowed_mentions=NO_PINGS)
            return
        if m := _DELETE_RE.match(text):
            ok = self.store.deactivate(int(m.group(1)), message.author.id)
            await message.reply(f"🗑 #{m.group(1)} を削除しました" if ok else f"#{m.group(1)} は見つかりません")
            return

        result = parse(text, now(), self.store.aliases())
        if result.status == "fail":
            await message.reply("🤔 日時が読み取れませんでした\n\n" + HELP_TEXT, allowed_mentions=NO_PINGS)
        elif result.status == "ok":
            rid = self.register(result, message.author.id, message.channel.id)
            view = UndoView(self, rid)
            view.message = await message.reply(
                format_registered(rid, result.first_at, result.recurrence, result.content, now()),
                view=view, allowed_mentions=NO_PINGS,
            )
        else:
            view = ConfirmView(self, result, text, message.author.id, message.channel.id)
            view.message = await message.reply(format_confirm(result, now()), view=view, allowed_mentions=NO_PINGS)

    def register(self, result: ParseResult, user_id: int, channel_id: int) -> int:
        return self.store.add(
            Reminder(user_id, channel_id, result.content, result.first_at, result.recurrence)
        )

    # ---------- 通知ループ ----------

    @tasks.loop(seconds=30)
    async def tick(self) -> None:
        current = now()
        for rem in self.store.due(current):
            text = format_notification(rem, is_late(rem.next_at, current), current)
            msg = await self.send_notification(rem.channel_id, rem.user_id, text)
            if msg:
                self.store.record_notified(msg.id, rem.user_id, msg.channel.id, rem.content)
            next_at, done = plan_after_fire(rem, current)
            self.store.update_after_fire(rem.id, next_at, done)

    @tick.before_loop
    async def _wait_ready(self) -> None:
        await self.wait_until_ready()

    @tick.error
    async def _tick_error(self, error: BaseException) -> None:
        log.exception("通知ループでエラー", exc_info=error)

    async def send_notification(self, channel_id: int, user_id: int, text: str) -> discord.Message | None:
        """チャンネルに送り、失敗したらDMに送る。送れたメッセージを返す。"""
        mentions = discord.AllowedMentions(users=True, roles=False, everyone=False)
        try:
            channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
            return await channel.send(text, allowed_mentions=mentions, view=SnoozeView(self))
        except discord.DiscordException:
            log.exception("チャンネル %s への通知に失敗。DMで再送します", channel_id)
        try:
            user = await self.fetch_user(user_id)
            return await user.send(text, allowed_mentions=mentions, view=SnoozeView(self))
        except discord.DiscordException:
            log.exception("ユーザー %s への通知に失敗しました", user_id)
            return None


# ---------- スヌーズ ----------

class SnoozeView(discord.ui.View):
    """通知メッセージに付く常設ボタン。内容は DB の notified から引くので再起動後も動く。"""

    def __init__(self, bot: ReminderBot):
        super().__init__(timeout=None)
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message("このボタンは使えません", ephemeral=True)
        return False

    @discord.ui.button(label="スヌーズ", style=discord.ButtonStyle.secondary, emoji="💤", custom_id="reminder:snooze")
    async def snooze(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        info = self.bot.store.get_notified(interaction.message.id)
        if info is None:
            await interaction.response.send_message("この通知の情報が見つかりません", ephemeral=True)
            return
        user_id, channel_id, content = info
        await interaction.response.send_message(
            f"💤 **{content}** を何分後にもう一度通知しますか？",
            view=SnoozePickView(self.bot, user_id, channel_id, content), ephemeral=True,
        )


class SnoozePickView(discord.ui.View):
    """スヌーズ時間を選ぶセレクト(押した本人にだけ見える)。"""

    def __init__(self, bot: ReminderBot, user_id: int, channel_id: int, content: str):
        super().__init__(timeout=300)
        self.bot, self.user_id, self.channel_id, self.content = bot, user_id, channel_id, content
        select = discord.ui.Select(
            placeholder="何分後にもう一度通知する？",
            options=[discord.SelectOption(label=name, value=str(m)) for name, m in SNOOZE_OPTIONS],
        )
        select.callback = self.picked
        self.add_item(select)

    async def picked(self, interaction: discord.Interaction) -> None:
        minutes = int(interaction.data["values"][0])
        rem = snoozed_reminder(self.user_id, self.channel_id, self.content, minutes, now())
        self.bot.store.add(rem)
        self.stop()
        await interaction.response.edit_message(
            content=f"💤 {label_for(minutes)}({rem.next_at:%H:%M})にもう一度通知します: **{self.content}**", view=None
        )


# ---------- ボタン ----------

class _OwnerView(discord.ui.View):
    def __init__(self, bot: ReminderBot):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.bot = bot
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message("このボタンは使えません", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.DiscordException:
                pass


class UndoView(_OwnerView):
    def __init__(self, bot: ReminderBot, rid: int):
        super().__init__(bot)
        self.rid = rid

    @discord.ui.button(label="取り消し", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def undo(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.bot.store.deactivate(self.rid, interaction.user.id)
        self.stop()
        await interaction.response.edit_message(content=f"🗑 #{self.rid} を取り消しました", view=None)


class ConfirmView(_OwnerView):
    def __init__(self, bot: ReminderBot, result: ParseResult, text: str, user_id: int, channel_id: int):
        super().__init__(bot)
        self.result, self.text = result, text
        self.user_id, self.channel_id = user_id, channel_id

    @discord.ui.button(label="登録", style=discord.ButtonStyle.success, emoji="✅")
    async def ok(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        rid = self.bot.register(self.result, self.user_id, self.channel_id)
        self.stop()
        r = self.result
        undo = UndoView(self.bot, rid)
        undo.message = self.message
        await interaction.response.edit_message(
            content=format_registered(rid, r.first_at, r.recurrence, r.content, now()), view=undo
        )

    @discord.ui.button(label="書き直す", style=discord.ButtonStyle.primary, emoji="🕒")
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(EditModal(self))

    @discord.ui.button(label="やめる", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(content="キャンセルしました", view=None)


class EditModal(discord.ui.Modal, title="リマインダーを書き直す"):
    def __init__(self, view: ConfirmView):
        super().__init__()
        self.parent = view
        self.field = discord.ui.TextInput(label="日時と内容", default=view.text, max_length=200)
        self.add_item(self.field)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        view, bot = self.parent, self.parent.bot
        text = self.field.value
        result = parse(text, now(), bot.store.aliases())
        if result.status == "fail":
            await interaction.response.send_message("🤔 日時が読み取れませんでした", ephemeral=True)
            return
        if result.status == "ok":
            view.stop()
            rid = bot.register(result, view.user_id, view.channel_id)
            undo = UndoView(bot, rid)
            undo.message = view.message
            await interaction.response.edit_message(
                content=format_registered(rid, result.first_at, result.recurrence, result.content, now()), view=undo
            )
            return
        view.result, view.text = result, text
        await interaction.response.edit_message(content=format_confirm(result, now()), view=view)


# ---------- スラッシュコマンド ----------

def _register_commands(bot: ReminderBot) -> None:
    tree = bot.tree

    async def guard(interaction: discord.Interaction) -> bool:
        if bot.is_owner(interaction.user):
            return True
        await interaction.response.send_message("このコマンドは使えません", ephemeral=True)
        return False

    @tree.command(name="list", description="登録中のリマインダー一覧")
    async def list_cmd(interaction: discord.Interaction) -> None:
        if await guard(interaction):
            await interaction.response.send_message(
                format_list(bot.store.active(interaction.user.id), now()), ephemeral=True
            )

    @tree.command(name="delete", description="リマインダーを削除")
    @app_commands.describe(id="削除するリマインダーの番号 (/list で確認)")
    async def delete_cmd(interaction: discord.Interaction, id: int) -> None:
        if await guard(interaction):
            ok = bot.store.deactivate(id, interaction.user.id)
            await interaction.response.send_message(
                f"🗑 #{id} を削除しました" if ok else f"#{id} は見つかりません", ephemeral=True
            )

    alias = app_commands.Group(name="alias", description="自分用の言い回し辞書(例: 昼ごろ = 12:30)")

    @alias.command(name="set", description="言葉に時刻を割り当てる")
    @app_commands.describe(word="言葉 (例: 昼ごろ)", time_text="時刻 (例: 12:30)")
    async def alias_set(interaction: discord.Interaction, word: str, time_text: str) -> None:
        if not await guard(interaction):
            return
        m = _HHMM_RE.match(time_text.strip())
        if not m or int(m.group(1)) > 23 or int(m.group(2) or 0) > 59:
            await interaction.response.send_message("時刻は 12:30 の形式で入力してください", ephemeral=True)
            return
        t = time(int(m.group(1)), int(m.group(2) or 0))
        bot.store.set_alias(word.strip(), t)
        await interaction.response.send_message(f"📖 「{word}」= {t:%H:%M} を登録しました", ephemeral=True)

    @alias.command(name="list", description="辞書の一覧")
    async def alias_list(interaction: discord.Interaction) -> None:
        if not await guard(interaction):
            return
        items = bot.store.aliases()
        text = "\n".join(f"・{w} = {t:%H:%M}" for w, t in sorted(items.items())) or "辞書は空です"
        await interaction.response.send_message(text, ephemeral=True)

    @alias.command(name="delete", description="辞書から削除")
    async def alias_delete(interaction: discord.Interaction, word: str) -> None:
        if await guard(interaction):
            ok = bot.store.delete_alias(word.strip())
            await interaction.response.send_message(
                f"「{word}」を削除しました" if ok else f"「{word}」は辞書にありません", ephemeral=True
            )

    tree.add_command(alias)
