import telegram_bot
import samoware_client
from samoware_client import SamowareContext
import database
import html
import asyncio
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
import sys

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="samowarium.log",
    encoding="utf-8",
    level=logging.DEBUG,
)

logging.getLogger("httpx").setLevel(logging.DEBUG)


async def client_handler(telegram_id):
    try:

        samoware_context = database.getSession(telegram_id)
        samoware_context = revalidateClient(samoware_context, telegram_id)
        samoware_client.openInbox(samoware_context)

        ackSeq = 0
        while database.isClientActive(telegram_id):
            ackSeq, longPollUpdate = await samoware_client.longPollUpdatesAsync(
                samoware_context, ackSeq
            )
            logging.debug(f"longPollUpdate: {longPollUpdate}")
            if '<folderReport folder="INBOX-MM-1" mode="notify"/>' in longPollUpdate:
                updates = samoware_client.getInboxUpdates(samoware_context)
                for update in updates:
                    if update["mode"] != "added":
                        continue
                    logging.info(f"new mail for user {telegram_id}")
                    logging.debug(f'email flags: {update["flags"]}')
                    mail = samoware_client.getMailById(samoware_context, update["uid"])
                    mail_plaintext = html.escape(mail)
                    to_str = ""
                    for i in range(len(update["to_name"])):
                        to_str += f'[{update["to_name"][i]}](copy-this-mail.example/{update["to_mail"][i]})'
                        if i != len(update["to_name"]) - 1:
                            to_str += ", "
                    await telegram_bot.send_message(
                        telegram_id,
                        f'{update["local_time"].strftime("%d.%m.%Y %H:%M")}\n\nОт кого: [{update["from_name"]}](copy-this-mail.example/{update["from_mail"]})\n\nКому: {to_str}\n\n*{update["subject"]}*\n\n{mail_plaintext}',
                        "markdown",
                    )
            if samoware_context.last_revalidate + timedelta(hours=5) < datetime.now():
                samoware_context = revalidateClient(samoware_context, telegram_id)
                samoware_client.openInbox(samoware_context)
                ackSeq = 0

    except RuntimeError:
        logging.info(f"longpolling for user {telegram_id} stopped")
    except Exception as error:
        database.removeClient(telegram_id)
        logging.exception("exception in client_handler:\n" + str(error))
        await telegram_bot.send_message(
            telegram_id,
            "Ваша сессия Samoware истекла. Чтобы продолжить получать письма, введите\n/login _логин_ _пароль_",
            format="markdown",
        )
        return


def revalidateClient(samoware_context: SamowareContext, telegram_id: int):
    samoware_context = samoware_client.revalidate(samoware_context)
    database.setSession(telegram_id, samoware_context.session)
    logging.info(f"revalidated client {telegram_id}")
    return samoware_context


async def activate(telegram_id, samovar_login, samovar_password):
    if database.isClientActive(telegram_id):
        await telegram_bot.send_message(telegram_id, "Samowarium уже включен")
        return
    context = samoware_client.login(samovar_login, samovar_password)
    if context is None:
        await telegram_bot.send_message(telegram_id, "Неверный логин или пароль")
        logging.info(f"User {telegram_id} entered wrong login or password")
        return
    database.addClient(telegram_id, samovar_login, context.session)
    asyncio.create_task(client_handler(telegram_id))
    await telegram_bot.send_message(
        telegram_id,
        "Samowarium активирован!\nНовые письма будут пересылаться с вашей бауманской почты сюда",
    )
    logging.info(f"User {telegram_id} activated bot")


async def deactivate(telegram_id):
    if not database.isClientActive(telegram_id):
        await telegram_bot.send_message(telegram_id, "Samowarium уже был выключен")
        return
    await telegram_bot.send_message(telegram_id, "Удаление ваших данных...")
    database.removeClient(telegram_id)
    await telegram_bot.send_message(
        telegram_id, "Samowarium выключен.\nМы вам больше писать ничего не будем"
    )
    logging.info(f"User {telegram_id} stopped bot")


def loadAllClients():
    logging.info("loading clients...")
    for client in database.getAllClients():
        asyncio.create_task(client_handler(client[0]))
    logging.info("revalidated clients")


async def main():
    loadAllClients()
    await telegram_bot.startBot(onActivate=activate, onDeactivate=deactivate)
    await asyncio.gather(*asyncio.all_tasks())


if __name__ == "__main__":
    asyncio.run(main())
