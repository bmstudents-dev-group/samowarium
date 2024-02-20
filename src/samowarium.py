import telegram_bot
import samoware_client
from samoware_client import SamowareContext
import database
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="samowarium.log",
    encoding="utf-8",
    level=logging.DEBUG,
)

logging.getLogger("httpx").setLevel(logging.DEBUG)


def startSamowareLongPolling(telegram_id:int, context:SamowareContext) -> None:
    async def _isActive():
        nonlocal telegram_id
        return database.isClientActive(telegram_id)
    async def _onMail(mail:samoware_client.Mail):
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
            "Ваша сессия Samoware истекла. Чтобы продолжить получать письма, введите\n/login _логин_ _пароль_",
            format="markdown",
        )
    samoware_client.startLongPolling(context, _isActive, _onMail, _onContextUpdate, _onSessionLost)


async def onMail(telegram_id:int, mail:samoware_client.Mail) -> None:
    from_str = f'[{mail.from_name}](copy-this-mail.example/{mail.from_mail})'
    to_str = ''
    for i in range(len(mail.to_name)):
        to_str += f'[{mail.to_name[i]}](copy-this-mail.example/{mail.to_mail[i]})'
        if i != len(mail.to_name) - 1:
            to_str += ", "
    await telegram_bot.send_message(
        telegram_id,
        f'{mail.local_time.strftime("%d.%m.%Y %H:%M")}\n\nОт кого: {from_str}\n\nКому: {to_str}\n\n*{mail.subject}*\n\n{mail.plain_text}',
        "markdown",
    )


async def onSessionLost(telegram_id:int) -> None:
    database.removeClient(telegram_id)
    await telegram_bot.send_message(
        telegram_id,
        "Ваша сессия Samoware истекла. Чтобы продолжить получать письма, введите\n/login _логин_ _пароль_",
        format="markdown",
    )


async def activate(telegram_id:int, samovar_login:int, samovar_password:int) -> None:
    if database.isClientActive(telegram_id):
        await telegram_bot.send_message(telegram_id, "Samowarium уже включен")
        return
    context = samoware_client.login(samovar_login, samovar_password)
    if context is None:
        await telegram_bot.send_message(telegram_id, "Неверный логин или пароль")
        logging.info(f"User {telegram_id} entered wrong login or password")
        return
    database.addClient(telegram_id, context)
    startSamowareLongPolling(telegram_id, context)
    await telegram_bot.send_message(
        telegram_id,
        "Samowarium активирован!\nНовые письма будут пересылаться с вашей бауманской почты сюда",
    )
    logging.info(f"User {telegram_id} activated bot")


async def deactivate(telegram_id:int) -> None:
    if not database.isClientActive(telegram_id):
        await telegram_bot.send_message(telegram_id, "Samowarium уже был выключен")
        return
    await telegram_bot.send_message(telegram_id, "Удаление ваших данных...")
    database.removeClient(telegram_id)
    await telegram_bot.send_message(
        telegram_id, "Samowarium выключен.\nМы вам больше писать ничего не будем"
    )
    logging.info(f"User {telegram_id} stopped bot")


async def main() -> None:
    logging.info("loading clients...")
    for client in database.getAllClients():
        samoware_context = database.getSamowareContext(client[0])
        startSamowareLongPolling(client[0], samoware_context)
    logging.info("loaded clients")

    await telegram_bot.startBot(onActivate=activate, onDeactivate=deactivate)
    await asyncio.gather(*asyncio.all_tasks())


if __name__ == "__main__":
    asyncio.run(main())
