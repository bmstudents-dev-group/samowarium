#!/bin/python3

import signal
from const import DB_PATH, LOGGER_FOLDER_PATH, LOGGER_PATH
from telegram_bot import TelegramBot
from database import Database
import asyncio
import logging
import env
import util


class Application:
    async def start(self) -> None:
        self.db = Database(DB_PATH)
        self.db.initialize()
        self.bot = TelegramBot(self.db)
        await self.bot.start_bot()
        self.setupShutdown(asyncio.get_event_loop())

    def setupShutdown(self, event_loop: asyncio.AbstractEventLoop):
        async def shutdown(signal) -> None:
            logging.info(f"received exit signal {signal}")
            logging.info("closing db connection")
            self.db.close()
            await self.bot.stop_bot()
            logging.info("application has stopped successfully")

        for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
            event_loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(shutdown(s))
            )


def setup_logger():
    LOGGER_LEVEL = logging.INFO
    if env.isDebug():
        LOGGER_LEVEL = logging.DEBUG
    util.make_dir_if_not_exist(LOGGER_FOLDER_PATH)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=LOGGER_PATH,
        encoding="utf-8",
        level=LOGGER_LEVEL,
    )
    logging.getLogger("httpx").setLevel(logging.WARN)


async def main() -> None:
    setup_logger()
    logging.info("starting the application...")
    app = Application()
    await app.start()
    await asyncio.gather(
        *[task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    )


if __name__ == "__main__":
    asyncio.run(main())
