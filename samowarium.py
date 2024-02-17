import telegram_bot
import samoware_client
import database
import html
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="samowarium.log",
    encoding="utf-8",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)

active_clients = []


async def client_handler(telegram_id, samoware_context):
    try:
        samoware_client.openInbox(samoware_context)
        ackSeq = 0
        while telegram_id in active_clients:
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
    except Exception as error:
        logging.exception("exception in client_handler:\n" + str(error))


async def activate(telegram_id, samovar_login, samovar_password):
    if telegram_id in active_clients:
        await telegram_bot.send_message(telegram_id, f"Samowarium уже включен")
        return
    context = samoware_client.login(samovar_login, samovar_password)
    if context == None:
        await telegram_bot.send_message(telegram_id, "Неверный логин или пароль")
        logging.info(f"User {telegram_id} entered wrong login or password")
        return
    database.addClient(telegram_id, samovar_login, context.session)
    active_clients.append(telegram_id)
    asyncio.create_task(client_handler(telegram_id, context))
    await telegram_bot.send_message(
        telegram_id,
        "Samowarium активирован!\nНовые письма будут пересылаться с вашей бауманской почты сюда",
    )
    logging.info(f"User {telegram_id} activated bot")


async def deactivate(telegram_id):
    if telegram_id not in active_clients:
        await telegram_bot.send_message(telegram_id, f"Samowarium уже был выключен")
        return
    await telegram_bot.send_message(telegram_id, f"Удаление ваших данных...")
    active_clients.remove(telegram_id)
    database.removeClient(telegram_id)
    await telegram_bot.send_message(
        telegram_id, "Samowarium выключен.\nМы вам больше писать ничего не будем"
    )
    logging.info(f"User {telegram_id} stopped bot")


def main():
    logging.info("loading clients...")
    loop = asyncio.get_event_loop()
    for client in database.loadAllClients():
        active_clients.append(client[0])
        context = samoware_client.loginWithSession(client[1], client[2])
        loop.create_task(client_handler(client[0], context))
        database.setSession(client[0], context.session)

    logging.info("starting telegram bot...")
    telegram_bot.startBot(onActivate=activate, onDeactivate=deactivate)


if __name__ == "__main__":
    main()
