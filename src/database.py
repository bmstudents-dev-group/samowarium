import datetime
import logging as log
from sqlite3 import connect
from json import dumps, loads
from typing import Self
from samoware_api import SamowarePollingContext
from util import make_dir_if_not_exist
from context import Context


class RawContext:
    def __init__(
        self,
        login: str,
        session: str,
        request_id: int,
        command_id: int,
        rand: int,
        ackSeq: int,
        last_revalidate: datetime,
        cookies: dict,
    ):
        self.login = login
        self.session = session
        self.request_id = request_id
        self.command_id = command_id
        self.rand = rand
        self.ackSeq = ackSeq  # saving backward compability
        self.last_revalidate = last_revalidate
        self.cookies = cookies


def map_context_to_raw(context: Context) -> RawContext:
    return RawContext(
        login=context.samoware_login,
        session=context.polling_context.session,
        request_id=context.polling_context.request_id,
        command_id=context.polling_context.command_id,
        rand=context.polling_context.rand,
        ackSeq=context.polling_context.ack_seq,
        last_revalidate=context.last_revalidate,
        cookies=context.polling_context.cookies,
    )


def map_raw_to_context(raw: RawContext, telegram_id: int) -> Context:
    return Context(
        polling_context=SamowarePollingContext(
            ack_seq=raw.ackSeq,
            command_id=raw.command_id,
            cookies=raw.cookies,
            rand=raw.rand,
            session=raw.session,
        ),
        last_revalidation=raw.last_revalidate,
        samoware_login=raw.login,
        telegram_id=telegram_id,
    )


class Database:
    def __init__(self, DB_PATH: str) -> None:
        self.path = DB_PATH

    def __enter__(self) -> Self:
        self.initialize()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def initialize(self) -> None:
        log.debug("initializing db...")
        self.connection = connect(self.path, check_same_thread=False)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS clients(telegram_id PRIMARY KEY, samoware_context)"
        )
        log.info("db was initialized")

    def close(self) -> None:
        log.debug("trying to close database")
        if self.connection is None:
            raise RuntimeError("can not close an uninitialized database")
        self.connection.close()
        log.info("database was closed")

    def add_client(self, telegram_id: int, context: Context) -> None:
        context_encoded = dumps(map_context_to_raw(context))
        self.connection.execute(
            "INSERT INTO clients VALUES(?, ?)",
            (telegram_id, context_encoded),
        )
        self.connection.commit()
        log.debug(f"client {telegram_id} has inserted")

    def set_handler_context(self, context: Context) -> None:
        telegram_id = context.telegram_id
        context_encoded = dumps(map_context_to_raw(context))
        self.connection.execute(
            "UPDATE clients SET samoware_context=? WHERE telegram_id=?",
            (context_encoded, telegram_id),
        )
        self.connection.commit()
        log.debug(f"samoware context for the client {telegram_id} has inserted")

    def get_samoware_context(self, telegram_id: int) -> Context | None:
        row = self.connection.execute(
            "SELECT samoware_context FROM clients WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        if row is None:
            log.warning(
                f"trying to fetch context for {telegram_id}, but context does not exist"
            )
            return None
        (context_encoded,) = row
        raw_context = map_raw_to_context(loads(context_encoded), telegram_id)
        log.debug(f"requested samoware context for the client {telegram_id}")
        return raw_context

    def is_client_active(self, telegram_id: int) -> bool:
        is_active = (
            self.connection.execute(
                "SELECT COUNT(*) FROM clients WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()[0]
            != 0
        )
        log.debug(f"client {telegram_id} is active: {is_active}")
        return is_active

    def get_all_clients(self) -> list[tuple[int, Context]]:
        def map_client_from_tuple(client):
            (telegram_id, context) = client
            return (telegram_id, map_raw_to_context(loads(context), telegram_id))

        clients = list(
            map(
                map_client_from_tuple,
                self.connection.execute(
                    "SELECT telegram_id, samoware_context FROM clients"
                ).fetchall(),
            )
        )
        log.debug(
            f"fetching all clients from database, an amount of the clients {len(clients)}"
        )
        return clients

    def remove_client(self, telegram_id: int) -> None:
        self.connection.execute(
            "DELETE FROM clients WHERE telegram_id=?", (telegram_id,)
        )
        self.connection.commit()
        log.debug(f"client {telegram_id} was removed")
