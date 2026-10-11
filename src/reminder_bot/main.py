import logging
import os
import sys
from pathlib import Path

from .bot import Config, ReminderBot
from .store import Store


def load_config() -> Config:
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    owner = os.environ.get("OWNER_ID", "").strip()
    if not token or not owner.isdigit():
        sys.exit("DISCORD_TOKEN と OWNER_ID(数字)を .env に設定してください")
    guild = os.environ.get("GUILD_ID", "").strip()
    return Config(
        token=token,
        owner_id=int(owner),
        db_path=os.environ.get("DB_PATH", "data/reminder.db"),
        guild_id=int(guild) if guild.isdigit() else None,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()
    Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)
    bot = ReminderBot(config, Store(config.db_path))
    bot.run(config.token, log_handler=None)


if __name__ == "__main__":
    main()
