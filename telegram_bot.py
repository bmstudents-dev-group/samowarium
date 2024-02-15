from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import os
from dotenv import load_dotenv

load_dotenv()

application = None
activate = None
deactivate = None

async def tg_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(f"Привет {user.mention_html()}!\nДля активации бота напишите /login &lt;логин&gt; &lt;пароль&gt;")

async def tg_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(f"Удаление ваших данных...")
    await deactivate(update.effective_user.id)

async def tg_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user.id
    login = context.args[0]
    password = context.args[1]
    await update.message.reply_html(f"Вы ввели\nлогин: {login}\nлогин: {password}")
    await activate(user,login,password)

async def send_message(telegram_id, message):
    await application.bot.send_message(telegram_id, message)

def startBot(onActivate, onDeactivate):
    global application, activate, deactivate
    activate = onActivate
    deactivate = onDeactivate
    application = Application.builder().token(os.environ['SAMOWARIUM_TOKEN']).build()
    
    application.add_handler(CommandHandler("start", tg_start))
    application.add_handler(CommandHandler("stop", tg_stop))
    application.add_handler(CommandHandler("login", tg_login))

    application.run_polling(allowed_updates=Update.ALL_TYPES)