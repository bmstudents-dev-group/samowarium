import signal
import telegram_bot
import samoware_client
from samoware_client import SamowareContext
import database
import asyncio
import logging
import env
import util

# TODO: убрать глобальную инициализацию
LOGGER_FOLDER_PATH = "logs"
util.makeDirIfNotExist(LOGGER_FOLDER_PATH)
LOGGER_LEVEL = logging.INFO
if env.isDebug():
    LOGGER_LEVEL = logging.DEBUG
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=f"{LOGGER_FOLDER_PATH}/samowarium.log",
    encoding="utf-8",
    level=LOGGER_LEVEL,
)

logging.getLogger("httpx").setLevel(logging.WARN)


def startHandler(telegram_id: int, context: SamowareContext) -> asyncio.Task:
    async def _isActive():
        nonlocal telegram_id
        return database.isClientActive(telegram_id)

    async def _onMail(mail: samoware_client.Mail):
        nonlocal telegram_id
        await onMail(telegram_id, mail)

    async def _onContextUpdate(context: SamowareContext):
        nonlocal telegram_id
        database.setSamowareContext(telegram_id, context)

    async def _onSessionLost():
        nonlocal telegram_id
        database.removeClient(telegram_id)
        await telegram_bot.send_message(
            telegram_id,
            "Сессия доступа к почте истекла. Для продолжения работы необходима повторная авторизация\n/login _логин_ _пароль_",
            format="markdown",
        )

    return asyncio.create_task(
        samoware_client.longPollingTask(
            context, _isActive, _onMail, _onContextUpdate, _onSessionLost
        ),
        name=f"handler-{telegram_id}"
    )


async def onMail(telegram_id: int, mail: samoware_client.Mail) -> None:
    from_str = f'<a href="copy-this-mail.example/{mail.from_mail}">{mail.from_name}</a>'
    to_str = ""
    for i in range(len(mail.to_name)):
        to_str += (
            f'<a href="copy-this-mail.example/{mail.to_mail[i]}">{mail.to_name[i]}</a>'
        )
        if i != len(mail.to_name) - 1:
            to_str += ", "
    await telegram_bot.send_message(
        telegram_id,
        f'{mail.local_time.strftime("%d.%m.%Y %H:%M")}\n\nОт кого: {from_str}\n\nКому: {to_str}\n\n<b>{mail.subject}</b>\n\n{mail.text}',
        "html",
    )
    if len(mail.attachment_files) > 0:
        await telegram_bot.send_attachments(
            telegram_id, mail.attachment_files, mail.attachment_names
        )


async def activate(
    telegram_id: int, samoware_login: str, samoware_password: str
) -> None:
    if database.isClientActive(telegram_id):
        await telegram_bot.send_message(telegram_id, "Доступ уже был выдан.")
        return
    context = samoware_client.login(samoware_login, samoware_password)
    if context is None:
        await telegram_bot.send_message(telegram_id, "Неверный логин или пароль.")
        logging.info(f"User {telegram_id} entered wrong login or password")
        return
    database.addClient(telegram_id, context)
    startHandler(telegram_id, context)
    await telegram_bot.send_message(
        telegram_id,
        "Доступ выдан. Все новые письма будут пересылаться в этот чат.",
    )
    logging.info(f"User {telegram_id} activated bot")


async def deactivate(telegram_id: int) -> None:
    if not database.isClientActive(telegram_id):
        await telegram_bot.send_message(telegram_id, "Доступ уже был отозван.")
        return
    database.removeClient(telegram_id)
    await telegram_bot.send_message(
        telegram_id, "Доступ отозван. Логин и сессия были удалены."
    )
    logging.info(f"User {telegram_id} stopped bot")


async def loadHandlers() -> list[asyncio.Task]:
    logging.info("loading handlers...")
    handlerTasks = []
    for client in database.getAllClients():
        (telegram_id, samoware_context) = client
        handlerTasks.append(startHandler(telegram_id, samoware_context))
    logging.info("handlers have loaded")
    return handlerTasks


def setupShutdown(eventLoop, handlers):
    async def shutdown(signal) -> None:
        logging.info(f"received exit signal {signal}")
        logging.info("shutdowning all handlers...")
        logging.debug(f"tasks to shutdown: {len(handlers)}")
        logging.info(f"shutdowning bot...")
        await telegram_bot.stopBot()
        [task.cancel() for task in handlers]
        await asyncio.gather(*handlers)
        logging.info("closing db connection")
        database.closeConnection()
        logging.info("application has stopped successfully. exiting...")

    for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        eventLoop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s)))


async def main() -> None:
    logging.info("starting the application...")
    database.initDB()

    handlers = await loadHandlers()

    setupShutdown(asyncio.get_event_loop(), handlers)

    await telegram_bot.startBot(onActivate=activate, onDeactivate=deactivate)
    await asyncio.gather(*[task for task in asyncio.all_tasks() if task is not asyncio.current_task()])



if __name__ == "__main__":
    asyncio.run(main())
