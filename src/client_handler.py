import asyncio
from http.client import HTTPResponse
import logging as log
from datetime import datetime, timedelta
import re
from typing import Awaitable, Callable, Optional, Self

from aiohttp import ClientSession, ClientTimeout

from const import HTML_FORMAT, HTTP_CONENCT_LONGPOLL_TIMEOUT_SEC, HTTP_TOTAL_LONGPOLL_TIMEOUT_SEC, LONGPOLL_RETRY_DELAY_SEC, MARKDOWN_FORMAT
from database import Database
import samoware_api
from samoware_api import (
    Mail,
    UnauthorizedError,
    SamowarePollingContext,
)

REVALIDATE_INTERVAL = timedelta(hours=5)
SESSION_TOKEN_PATTERN = re.compile("^[0-9]{6}-[a-zA-Z0-9]{20}$")


class ClientHandler:
    class Context:
        def __init__(
            self,
            telegram_id: int,
            samoware_login: str,
            polling_context: SamowarePollingContext,
            last_revalidation: datetime | None = None,
        ) -> None:
            self.telegram_id = telegram_id
            self.samoware_login = samoware_login
            self.polling_context = polling_context
            self.last_revalidate = last_revalidation
            if self.last_revalidate is None:
                self.last_revalidate = datetime.now()

    def __init__(
        self,
        message_sender: Callable[
            [int, str, str, Optional[list[tuple[HTTPResponse, str]]]], Awaitable[None]
        ],
        db: Database,
        context: Context,
    ):
        self.message_sender = message_sender
        self.db = db
        self.context = context

    def make_new() -> Self | None:
        pass

    def make_from_db() -> Self | None:
        pass

    async def start_handling(self) -> asyncio.Task:
        self.polling_task = asyncio.create_task(self.polling())
        return self.polling_task

    async def stop_handling(self) -> None:
        self.polling_task.cancel()

    async def polling(self) -> None:
        http_session = ClientSession(
            timeout=ClientTimeout(
                connect=HTTP_CONENCT_LONGPOLL_TIMEOUT_SEC,
                total=HTTP_TOTAL_LONGPOLL_TIMEOUT_SEC,
            )
        )

        retry_count = 0
        polling_context = self.context.polling_context
        log.info(f"longpolling for {polling_context.login} is started")

        while await self.db.is_client_active(self.context.telegram_id):
            try:
                self.db.set_handler_context(self.context)
                (polling_result, polling_context) = await samoware_api.longpoll_updates(
                    polling_context, http_session
                )
                log.debug(f"polling result: {polling_result}")
                if samoware_api.has_updates(polling_result):
                    (mails, polling_context) = samoware_api.get_new_mails(
                        polling_context
                    )
                    for mail_header in mails:
                        log.info(f"new mail for {polling_context.login}")
                        log.debug(f"email flags: {mail_header.flags}")
                        mail_body = samoware_api.get_mail_body_by_id(
                            polling_context, mail_header.uid
                        )
                        await self.forward_mail(Mail(mail_header, mail_body))
                if (
                    polling_context.last_revalidate + REVALIDATE_INTERVAL
                    < datetime.now()
                ):
                    new_context = samoware_api.revalidate(polling_context)
                    if new_context is None:
                        log.warning(
                            f"can not revalidate session for user {self.context.telegram_id} {self.context.samoware_login}"
                        )
                        await self.can_not_revalidate()
                        break
                    polling_context = new_context
                retry_count = 0
                self.context.polling_context = polling_context
            except asyncio.CancelledError:  # It happens when samowarium has been killed
                break
            except UnauthorizedError:  # Session lost
                log.info(f"session for {polling_context.login} expired")
                await self.session_has_expired()
                break
            except Exception as error:
                log.exception("exception in client_handler: " + str(error))
                log.info(
                    f"retry_count={retry_count}. Retrying longpolling for {polling_context.login} in {LONGPOLL_RETRY_DELAY_SEC} seconds..."
                )
                retry_count += 1
                await asyncio.sleep(LONGPOLL_RETRY_DELAY_SEC)

        http_session.close()
        log.info(f"longpolling for {polling_context.login} stopped")

    async def can_not_revalidate(self):
        await self.message_sender(
            self.context.telegram_id,
            "Невозможно продлить сессию из-за внутренней ошибки. Для продолжения работы необходима повторная авторизация\n/login _логин_ _пароль_",
            MARKDOWN_FORMAT,
        )

    async def session_has_expired(self):
        await self.message_sender(
            self.context.telegram_id,
            "Сессия доступа к почте истекла. Для продолжения работы необходима повторная авторизация\n/login _логин_ _пароль_",
            MARKDOWN_FORMAT,
        )

    async def forward_mail(self, mail: Mail):
        from_str = (
            f'<a href="copy-this-mail.example/{mail.from_mail}">{mail.from_name}</a>'
        )
        to_str = ", ".join(
            f'<a href="copy-this-mail.example/{recipient[0]}">{recipient[1]}</a>'
            for recipient in mail.header.recipients
        )

        mail_text = f'{mail.local_time.strftime("%d.%m.%Y %H:%M")}\n\nОт кого: {from_str}\n\nКому: {to_str}\n\n<b>{mail.subject}</b>\n\n{mail.text}'

        self.message_sender(
            self.context.telegram_id,
            mail_text,
            HTML_FORMAT,
            mail.body.attachments if len(mail.body.attachments) > 0 else None,
        )
