import telegram_bot
import samoware_client
import database
import html
import asyncio

active_clients = []

async def client_handler(telegram_id, samoware_session):
    samoware_client.openInbox(samoware_session)
    await telegram_bot.send_message(telegram_id, "Samovarium активирован!\nНовые письма будут пересылаться с вашей бауманской почты сюда")
    ackSeq = 0
    while telegram_id in active_clients:
        ackSeq, update = await samoware_client.longPollUpdatesAsync(samoware_session,ackSeq)
        print("update string: "+update)
        if("INBOX-MM-1" in update):
            print("new mails arrived:")
            newMails = samoware_client.getNewMails(samoware_session)
            for mail in newMails:
                mail_body = samoware_client.getMailById(samoware_session,mail["uid"])
                mail_body_plaintext = html.escape(mail_body)
                await telegram_bot.send_message(telegram_id, f'Пришло письмо от {mail["from_name"]} ({mail["from_mail"]})\nТема: {mail["subject"]}\n{mail_body_plaintext}')
    await telegram_bot.send_message(telegram_id, "Samovarium выключен.\nМы вам больше писать ничего не будем")


def activate(telegram_id, samovar_login, samovar_password):
    samoware_client.login(samovar_login, samovar_password)
    samovar_session = samoware_client.login(samovar_login,samovar_password)
    database.addClient(telegram_id, samovar_session)
    active_clients.append(telegram_id)
    asyncio.create_task(client_handler(telegram_id, samovar_session))

def deactivate(telegram_id):
    active_clients.remove(telegram_id)
    database.removeClient(telegram_id)

def main():
    loop = asyncio.get_event_loop()
    for client in database.loadAllClients():
        active_clients.append(client[0])
        loop.create_task(client_handler(client[0], client[1]))

    telegram_bot.startBot(onActivate=activate, onDeactivate=deactivate)

if __name__ == "__main__":
    main()