import asyncio

from reminder_bot.bot import Config, ReminderBot, SnoozePickView, SnoozeView, _register_commands
from reminder_bot.snooze import SNOOZE_OPTIONS
from reminder_bot.store import Store


def make_bot():
    return ReminderBot(Config(token="x", owner_id=1, db_path=":memory:"), Store(":memory:"))


def test_bot_builds_and_registers_commands():
    bot = make_bot()
    _register_commands(bot)
    names = {c.name for c in bot.tree.get_commands()}
    assert names == {"list", "delete", "alias"}


def test_snooze_views_build():
    async def run():
        bot = make_bot()
        view = SnoozeView(bot)
        assert view.is_persistent()  # 再起動後も使える(timeout=None かつ custom_id 付き)
        pick = SnoozePickView(bot, 1, 2, "コンパス")
        [select] = pick.children
        assert len(select.options) == len(SNOOZE_OPTIONS)

    asyncio.run(run())
