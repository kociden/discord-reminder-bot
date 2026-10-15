import asyncio

from reminder_bot.bot import Config, NotifyView, ReminderBot, SnoozePickView, _register_commands
from reminder_bot.snooze import SNOOZE_OPTIONS
from reminder_bot.store import Store


def make_bot():
    return ReminderBot(Config(token="x", owner_id=1, db_path=":memory:"), Store(":memory:"))


def test_bot_builds_and_registers_commands():
    bot = make_bot()
    _register_commands(bot)
    names = {c.name for c in bot.tree.get_commands()}
    assert names == {"list", "delete", "alias"}


def test_notify_view_has_done_left_and_snooze_right():
    async def run():
        view = NotifyView(make_bot())
        assert view.is_persistent()  # 再起動後も使える(timeout=None かつ custom_id 付き)
        assert [b.label for b in view.children] == ["完了", "スヌーズ"]

    asyncio.run(run())


def test_snooze_pick_view_lists_all_options():
    async def run():
        pick = SnoozePickView(make_bot(), 1, 2, "コンパス")
        [select] = pick.children
        assert len(select.options) == len(SNOOZE_OPTIONS)

    asyncio.run(run())
