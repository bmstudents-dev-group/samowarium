import logging as log
from sqlite3 import connect
from json import dumps, loads
from typing import Self

import dateutil.parser
from samoware_api import SamowarePollingContext
from context import Context


def map_context_to_dict(context: Context) -> dict:
    return {
        "login": context.samoware_login,
        "ack_seq": context.polling_context.ack_seq,
        "command_id": context.polling_context.command_id,
        "cookies": context.polling_context.cookies,
        "last_revalidate": context.last_revalidate.isoformat(),
        "request_id": context.polling_context.request_id,
        "session": context.polling_context.session,
        "rand": context.polling_context.rand,
    }


def map_context_from_dict(d: dict, telegram_id: int) -> Context:
    return Context(
        polling_context=SamowarePollingContext(
            ack_seq=d["ack_seq"],
            command_id=d["command_id"],
            cookies=d["cookies"],
            rand=d["rand"],
            session=d["session"],
            request_id=d["request_id"],
        ),
        last_revalidation=dateutil.parser.isoparse(d["last_revalidate"]),
        samoware_login=d["login"],
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
        context_encoded = dumps(map_context_to_dict(context))
        self.connection.execute(
            "INSERT INTO clients VALUES(?, ?)",
            (telegram_id, context_encoded),
        )
        self.connection.commit()
        log.debug(f"client {telegram_id} has inserted")

    def set_handler_context(self, context: Context) -> None:
        telegram_id = context.telegram_id
        context_encoded = dumps(map_context_to_dict(context))
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
        raw_context = map_context_from_dict(loads(context_encoded), telegram_id)
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
            return (telegram_id, map_context_from_dict(loads(context), telegram_id))

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
