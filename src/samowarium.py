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

client_tasks = {}


async def client_handler(telegram_id, samoware_context):
    try:
        samoware_client.openInbox(samoware_context)
        ackSeq = 0
        while True:
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
    if database.clientActive(telegram_id):
        await telegram_bot.send_message(telegram_id, "Samowarium уже включен")
        return
    context = samoware_client.login(samovar_login, samovar_password)
    if context is None:
        await telegram_bot.send_message(telegram_id, "Неверный логин или пароль")
        logging.info(f"User {telegram_id} entered wrong login or password")
        return
    database.addClient(telegram_id, samovar_login, context.session)
    client_tasks[telegram_id] = asyncio.create_task(
        client_handler(telegram_id, context)
    )
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
    client_tasks[telegram_id].cancel()
    database.removeClient(telegram_id)
    await telegram_bot.send_message(
        telegram_id, "Samowarium выключен.\nМы вам больше писать ничего не будем"
    )
    logging.info(f"User {telegram_id} stopped bot")


def ravalidateAllClients():
    logging.info("revalidating clients...")
    for client_task in client_tasks.values():
        client_task.cancel()
    client_tasks.clear()
    for client in database.loadAllClients():
        context = samoware_client.loginWithSession(client[1], client[2])
        client_tasks[client[0]] = asyncio.create_task(
            client_handler(client[0], context)
        )
        database.setSession(client[0], context.session)
    logging.info("revalidated clients")


async def revalidateJob():
    while True:
        await asyncio.sleep(60 * 60 * 5)
        ravalidateAllClients()


async def main():
    ravalidateAllClients()
    asyncio.create_task(revalidateJob())
    await telegram_bot.startBot(onActivate=activate, onDeactivate=deactivate)
    await asyncio.gather(*asyncio.all_tasks())


if __name__ == "__main__":
    asyncio.run(main())
