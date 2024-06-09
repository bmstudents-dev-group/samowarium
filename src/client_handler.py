import asyncio
import logging as log
from datetime import datetime, timedelta, timezone
import re
from typing import Self

from aiohttp import ClientSession, ClientTimeout
import aiohttp
from context import Context

from const import (
    HTML_FORMAT,
    HTTP_CONNECT_LONGPOLL_TIMEOUT_SEC,
    HTTP_TOTAL_LONGPOLL_TIMEOUT_SEC,
    LONGPOLL_RETRY_DELAY_SEC,
    MARKDOWN_FORMAT,
)
from database import Database
import samoware_api
from samoware_api import (
    Mail,
    UnauthorizedError,
)
from util import MessageSender

REVALIDATE_INTERVAL = timedelta(hours=5)
SESSION_TOKEN_PATTERN = re.compile("^[0-9]{6}-[a-zA-Z0-9]{20}$")

SUCCESSFUL_LOGIN_PROMPT = (
    "Доступ выдан. Все новые письма будут пересылаться в этот чат."
)
CAN_NOT_REVALIDATE_PROMPT = "Невозможно продлить сессию из-за внутренней ошибки. Для продолжения работы необходима повторная авторизация\n/login _логин_ _пароль_"
SESSION_EXPIRED_PROMPT = "Сессия доступа к почте истекла. Для продолжения работы необходима повторная авторизация\n/login _логин_ _пароль_"
CAN_NOT_RELOGIN_PROMPT = "Ошибка при автоматической повторной авторизации, невозможно продлить сессию. Для продолжения работы необходима авторизация\n/login _логин_ _пароль_"
WRONG_CREDS_PROMPT = "Неверный логин или пароль."
HANDLER_IS_ALREADY_WORKED_PROMPT = "Доступ уже был выдан."
HANDLER_IS_ALREADY_SHUTTED_DOWN_PROMPT = "Доступ уже был отозван."


class ClientHandler:
    def __init__(
        self,
        message_sender: MessageSender,
        db: Database,
        context: Context,
    ):
        self.message_sender = message_sender
        self.db = db
        self.context = context

    @classmethod
    async def make_new(
        cls,
        telegram_id: int,
        samoware_login: str,
        samoware_password: str,
        message_sender: MessageSender,
        db: Database,
    ) -> Self | None:
        if db.is_client_active(telegram_id):
            await message_sender(
                telegram_id, HANDLER_IS_ALREADY_WORKED_PROMPT, MARKDOWN_FORMAT
            )
            return None
        handler = ClientHandler(
            message_sender, db, Context(telegram_id, samoware_login)
        )
        is_successful_login = handler.login(samoware_password)
        if not is_successful_login:
            await message_sender(telegram_id, WRONG_CREDS_PROMPT, MARKDOWN_FORMAT)
            return None
        db.add_client(telegram_id, handler.context)
        await message_sender(telegram_id, SUCCESSFUL_LOGIN_PROMPT, MARKDOWN_FORMAT)
        return handler

    @classmethod
    async def make_from_context(
        cls, context: Context, message_sender: MessageSender, db: Database
    ) -> Self:
        return ClientHandler(message_sender, db, context)

    async def start_handling(self) -> asyncio.Task:
        self.polling_task = asyncio.create_task(self.polling())
        return self.polling_task

    def get_polling_task(self) -> asyncio.Task:
        return self.polling_task

    async def stop_handling(self) -> None:
        if not (self.polling_task.cancelled() or self.polling_task.done()):
            self.polling_task.cancel()
        await asyncio.wait([self.polling_task])

    async def polling(self) -> None:
        async with ClientSession(
            timeout=ClientTimeout(
                connect=HTTP_CONNECT_LONGPOLL_TIMEOUT_SEC,
                total=HTTP_TOTAL_LONGPOLL_TIMEOUT_SEC,
            )
        ) as http_session:
            try:
                retry_count = 0
                log.info(f"longpolling for {self.context.samoware_login} is started")

                while self.db.is_client_active(self.context.telegram_id):
                    try:
                        polling_context = self.context.polling_context
                        self.db.set_handler_context(self.context)
                        (polling_result, polling_context) = (
                            await samoware_api.longpoll_updates(
                                polling_context, http_session
                            )
                        )
                        if samoware_api.has_updates(polling_result):
                            (mails, polling_context) = samoware_api.get_new_mails(
                                polling_context
                            )
                            for mail_header in mails:
                                log.info(f"new mail for {self.context.telegram_id}")
                                log.debug(f"email flags: {mail_header.flags}")
                                mail_body = samoware_api.get_mail_body_by_id(
                                    polling_context, mail_header.uid
                                )
                                await self.forward_mail(Mail(mail_header, mail_body))
                        self.context.polling_context = polling_context
                        if datetime.astimezone(
                            self.context.last_revalidate + REVALIDATE_INTERVAL,
                            timezone.utc,
                        ) < datetime.now(timezone.utc):
                            is_successful_revalidation = self.revalidate()
                            if not is_successful_revalidation:
                                await self.can_not_revalidate()
                                return
                        retry_count = 0
                    except asyncio.CancelledError:
                        return
                    except UnauthorizedError:
                        log.info(f"session for {self.context.samoware_login} expired")
                        samoware_password = self.db.get_password(
                            self.context.telegram_id
                        )
                        if samoware_password is None:
                            await self.session_has_expired()
                            self.db.remove_client(self.context.telegram_id)
                            return
                        is_successful_relogin = self.login(samoware_password)
                        if not is_successful_relogin:
                            await self.can_not_relogin()
                            return
                    except (
                        aiohttp.ClientOSError
                    ) as error:  # unknown source error https://github.com/aio-libs/aiohttp/issues/6912
                        log.warning(
                            f"retry_count={retry_count}. ClientOSError. Probably Broken pipe. Retrying in {LONGPOLL_RETRY_DELAY_SEC} seconds. {str(error)}"
                        )
                        retry_count += 1
                        await asyncio.sleep(LONGPOLL_RETRY_DELAY_SEC)
                    except Exception as error:
                        log.exception("exception in client_handler", error)
                        log.warning(
                            f"retry_count={retry_count}. Retrying longpolling for {self.context.samoware_login} in {LONGPOLL_RETRY_DELAY_SEC} seconds..."
                        )
                        retry_count += 1
                        await asyncio.sleep(LONGPOLL_RETRY_DELAY_SEC)
            finally:
                log.info(f"longpolling for {self.context.samoware_login} stopped")

    def login(self, samoware_password: str) -> bool:
        log.debug("trying to login")
        try:
            relogin_context = samoware_api.login(
                self.context.samoware_login, samoware_password
            )
            if relogin_context is None:
                log.info(f"unsuccessful login for user {self.context.samoware_login}")
                return False
            relogin_context = samoware_api.set_session_info(relogin_context)
            relogin_context = samoware_api.open_inbox(relogin_context)
            self.context.polling_context = relogin_context
            self.db.set_handler_context(self.context)
            log.info(f"successful login for user {self.context.samoware_login}")
            return True
        except Exception as e:
            log.exception("exception on login", e)
            return False

    def revalidate(self) -> bool:
        log.debug("trying to revalidate")
        try:
            polling_context = samoware_api.revalidate(
                self.context.samoware_login, self.context.polling_context.session
            )
            if polling_context is None:
                log.info(
                    f"unsuccessful revalidation for user {self.context.samoware_login}"
                )
                return False
            polling_context = samoware_api.set_session_info(polling_context)
            polling_context = samoware_api.open_inbox(polling_context)
            self.context.polling_context = polling_context
            self.context.last_revalidate = datetime.now(timezone.utc)
            self.db.set_handler_context(self.context)
            log.info(f"successful revalidation for user {self.context.samoware_login}")
        except Exception as e:
            log.exception("exception on revalidation", e)
            return False

    async def can_not_revalidate(self):
        await self.message_sender(
            self.context.telegram_id,
            CAN_NOT_REVALIDATE_PROMPT,
            MARKDOWN_FORMAT,
        )

    async def can_not_relogin(self):
        await self.message_sender(
            self.context.telegram_id, CAN_NOT_RELOGIN_PROMPT, MARKDOWN_FORMAT
        )

    async def session_has_expired(self):
        await self.message_sender(
            self.context.telegram_id,
            SESSION_EXPIRED_PROMPT,
            MARKDOWN_FORMAT,
        )

    async def forward_mail(self, mail: Mail):
        from_str = f'<a href="copy-this-mail.example/{mail.header.from_mail}">{mail.header.from_name}</a>'
        to_str = ", ".join(
            f'<a href="copy-this-mail.example/{recipient[0]}">{recipient[1]}</a>'
            for recipient in mail.header.recipients
        )

        mail_text = f'{datetime.strftime(mail.header.local_time, "%d.%m.%Y %H:%M")}\n\nОт кого: {from_str}\n\nКому: {to_str}\n\n<b>{mail.header.subject}</b>\n\n{mail.body.text}'

        await self.message_sender(
            self.context.telegram_id,
            mail_text,
            HTML_FORMAT,
            mail.body.attachments if len(mail.body.attachments) > 0 else None,
        )
