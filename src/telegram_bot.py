from telegram import Update, InputMediaDocument
import telegram
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
import os
import logging
from typing import Callable, Awaitable
import asyncio

application: Application | None = None
activate: Callable[[int, str, str], Awaitable[None]] | None = None
deactivate: Callable[[int], Awaitable[None]] | None = None


async def tg_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.debug(f"received /start from {update.effective_user.id}")
    await update.message.reply_html(
        "Выдать доступ боту до почты :\n/login <i>логин</i> <i>пароль</i>\n\nОтозвать доступ:\n/stop\n\nFAQ:\n/about"
    )


async def tg_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.debug(f"received /stop from {update.effective_user.id}")
    await deactivate(update.effective_user.id)


async def tg_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.debug(f"received /login from {update.effective_user.id}")
    await application.bot.delete_message(
        update.effective_chat.id, update.effective_message.id
    )
    if len(context.args) != 2:
        await update.message.reply_html(
            "Неверный формат использования команды:\n/login <i>логин</i> <i>пароль</i>"
        )
        logging.debug(
            f"client entered login and password in wrong format: {context.args}"
        )
        return
    user = update.effective_user.id
    login = context.args[0]
    password = context.args[1]
    logging.debug(f'client entered login "{login}" and password')
    await activate(user, login, password)


# TODO: split message if too long
async def send_message(
    telegram_id: int, message: str, format: str | None = None
) -> None:
    sent = False
    logging.debug(f'sending message "{message}" to {telegram_id} ...')
    while not sent:
        try:
            await application.bot.send_message(telegram_id, message, parse_mode=format)
            sent = True
            logging.info(f"sent message to {telegram_id}")
        except telegram.error.BadRequest as error:
            logging.exception("exception in send_message:\n" + str(error))
            logging.info("error is bad request. Not retrying")
            break
        except Exception as error:
            logging.exception("exception in send_message:\n" + str(error))
            logging.info(f"retrying to send message for {telegram_id} in 2 seconds...")
            await asyncio.wait(2)


async def send_attachments(
    telegram_id: int, attachment_files: list, attachment_names: list[str]
):
    media_group = []
    for i in range(len(attachment_files)):
        media_group.append(
            InputMediaDocument(attachment_files[i], filename=attachment_names[i])
        )
    await application.bot.send_media_group(telegram_id, media_group)


async def tg_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        """
Samowarium - бот, который пересылает входящие письма в личные сообщения телеграм.

Список команд бота:
/login - выдать боту доступ к почтовому серверу.
/stop - отозвать доступ и удалить информацию о пользователе.
/about - получить дополнительную информацию.

Как это работает?
При передаче пары логин/пароль бот получает от почтового сервера токен сессии, с помощью которого в дальнейшем обрабатывает входящие письма.
Бот не хранит пароли пользователей, а лишь использует их однократно во время авторизации для получения токена сессии, после чего их забывает. Токен сессии почтового сервера возможно использовать только для работы с почтой, бот не может с помощью него получить доступ к остальным сервисам МГТУ.
        """
    )


async def startBot(
    onActivate: Callable[[int, str, str], Awaitable[None]],
    onDeactivate: Callable[[int], Awaitable[None]],
) -> None:
    global application, activate, deactivate
    logging.info("starting telegram bot...")
    activate = onActivate
    deactivate = onDeactivate

    logging.debug("connecting to telegram api...")
    application = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()

    application.add_handler(CommandHandler("start", tg_start))
    application.add_handler(CommandHandler("stop", tg_stop))
    application.add_handler(CommandHandler("login", tg_login))
    application.add_handler(CommandHandler("about", tg_about))

    await application.initialize()
    await application.start()
    logging.info("starting telegram polling...")
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
