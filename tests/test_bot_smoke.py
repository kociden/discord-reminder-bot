from reminder_bot.bot import Config, ReminderBot, _register_commands
from reminder_bot.store import Store


def test_bot_builds_and_registers_commands():
    bot = ReminderBot(Config(token="x", owner_id=1, db_path=":memory:"), Store(":memory:"))
    _register_commands(bot)
    names = {c.name for c in bot.tree.get_commands()}
    assert names == {"list", "delete", "alias"}
