from telegram import Update, InputMediaDocument
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
import os
import logging
from typing import Callable, Awaitable

application: Application | None = None
activate: Callable[[int, str, str], Awaitable[None]] | None = None
deactivate: Callable[[int], Awaitable[None]] | None = None


async def tg_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.debug(f"received /start from {update.effective_user.id}")
    await update.message.reply_html(
        "Привет, это Samowarium, клиент бауманской почты в телеграме!\nДля активации бота напишите: \n/login <i>логин</i> <i>пароль</i>\nДля отключения бота: /stop"
    )


async def tg_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.debug(f"received /stop from {update.effective_user.id}")
    await deactivate(update.effective_user.id)


async def tg_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.debug(f"received /login from {update.effective_user.id}")
    await application.bot.delete_message(
        update.effective_chat.id, update.effective_message.id
    )
    if len(context.args) < 2:
        await update.message.reply_html(
            "Не верный формат\nДля активации бота напишите\n/login <i>логин</i> <i>пароль</i>"
        )
        logging.debug(
            f"client entered login and password in wrong format: {context.args}"
        )
        return
    user = update.effective_user.id
    login = context.args[0]
    password = context.args[1]
    logging.debug(f"client entered login:{login}, password:{password}")
    await activate(user, login, password)


async def send_message(
    telegram_id: int, message: str, format: str | None = None
) -> None:
    logging.debug(f'sending message "{message}" to {telegram_id}')
    await application.bot.send_message(telegram_id, message, parse_mode=format)


async def send_attachments(
    telegram_id: int, attachment_files: list, attachment_names: list[str]
):
    media_group = []
    for i in range(len(attachment_files)):
        media_group.append(
            InputMediaDocument(attachment_files[i], filename=attachment_names[i])
        )
    await application.bot.send_media_group(telegram_id, media_group)


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

    logging.debug("starting telegram polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
