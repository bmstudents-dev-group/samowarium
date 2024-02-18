import telegram_bot
import samoware_client
import database
import html
import asyncio
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="samowarium.log",
    encoding="utf-8",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)


async def client_handler(telegram_id):
    try:

        samoware_login, samoware_session = database.getSession(telegram_id)
        samoware_context = samoware_client.loginWithSession(
            samoware_login, samoware_session
        )
        database.setSession(telegram_id, samoware_context.session)
        last_revalidate = datetime.now()
        logging.info(f"revalidated client {telegram_id}")

        samoware_client.openInbox(samoware_context)

        ackSeq = 0
        while database.clientActive(telegram_id):
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
                    await telegram_bot.send_message(
                        telegram_id,
                        f'Пришло письмо от {update["from_name"]} ({update["from_mail"]})\nТема: {update["subject"]}\n{mail_plaintext}',
                    )
        if last_revalidate + timedelta(hours=5) > datetime.now():
            samoware_context = samoware_client.revalidate(samoware_context)
            database.setSession(telegram_id, samoware_context.session)
            last_revalidate = datetime.now()
            logging.info(f"revalidated client {telegram_id}")

    except Exception as error:
        logging.exception("exception in client_handler:\n" + str(error))


async def activate(telegram_id, samovar_login, samovar_password):
    if database.clientActive(telegram_id):
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
    if not database.clientActive(telegram_id):
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