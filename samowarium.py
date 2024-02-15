import telegram_bot
import samoware_client
import database
import html
import asyncio

active_clients = []

async def client_handler(telegram_id, samoware_session):
    samoware_client.openInbox(samoware_session)
    ackSeq = 0
    while telegram_id in active_clients:
        ackSeq, longPollUpdate = await samoware_client.longPollUpdatesAsync(samoware_session,ackSeq)
        if("INBOX-MM-1" in longPollUpdate):
            updates = samoware_client.getInboxUpdates(samoware_session)
            for update in updates:
                # если стоит флаг Seen, то событие это не новое письмо, а это обновление статуса письма
                if update["flags"] == "Seen": continue
                print(f"new mail for user {telegram_id}")
                mail = samoware_client.getMailById(samoware_session,update["uid"])
                mail_plaintext = html.escape(mail)
                await telegram_bot.send_message(telegram_id, f'Пришло письмо от {update["from_name"]} ({update["from_mail"]})\nТема: {update["subject"]}\n{mail_plaintext}')


async def activate(telegram_id, samovar_login, samovar_password):
    samoware_client.login(samovar_login, samovar_password)
    samovar_session = samoware_client.login(samovar_login,samovar_password)
    database.addClient(telegram_id, samovar_session)
    active_clients.append(telegram_id)
    asyncio.create_task(client_handler(telegram_id, samovar_session))
    await telegram_bot.send_message(telegram_id, "Samowarium активирован!\nНовые письма будут пересылаться с вашей бауманской почты сюда")
    print(f"User {telegram_id} activated bot")

async def deactivate(telegram_id):
    active_clients.remove(telegram_id)
    database.removeClient(telegram_id)
    await telegram_bot.send_message(telegram_id, "Samowarium выключен.\nМы вам больше писать ничего не будем")
    print(f"User {telegram_id} stopped bot")

def main():
    print("loading clients...")

    loop = asyncio.get_event_loop()
    for client in database.loadAllClients():
        active_clients.append(client[0])
        loop.create_task(client_handler(client[0], client[1]))

    print("clients loaded")

    telegram_bot.startBot(onActivate=activate, onDeactivate=deactivate)

if __name__ == "__main__":
    main()