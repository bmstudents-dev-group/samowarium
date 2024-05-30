from sqlite3 import connect
from pickle import dumps, loads
from typing import Self
from util import make_dir_if_not_exist
from logging import info, debug

from samoware_client import SamowareContext


class Database:
    def __init__(self, DB_PATH: str) -> None:
        self.path = DB_PATH

    def __enter__(self) -> Self:
        self.initialize()
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def initialize(self) -> None:
        debug("initializing db...")
        make_dir_if_not_exist(self.path)
        self.connection = connect(self.path, check_same_thread=False)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS clients(telegram_id PRIMARY KEY, samoware_context)"
        )
        info("db was initialized")

    def close(self) -> None:
        debug("trying to close database")
        if self.connection is None:
            raise RuntimeError("can not close an uninitialized database")
        self.connection.close()
        info("database was closed")

    def add_client(self, telegram_id: int, context: SamowareContext) -> None:
        context_encoded = dumps(context)
        self.connection.execute(
            "INSERT INTO clients VALUES(?, ?)",
            (telegram_id, context_encoded),
        )
        self.connection.commit()
        debug(f"client {telegram_id} has inserted")

    def set_samoware_context(self, telegram_id: int, context: SamowareContext) -> None:
        context_encoded = loads(context)
        self.connection.execute(
            "UPDATE clients SET samoware_context=? WHERE telegram_id=?",
            (context_encoded, telegram_id),
        )
        self.connection.commit()
        debug(f"samoware context for the client {telegram_id} has inserted")

    def get_samoware_context(self, telegram_id: int) -> SamowareContext:
        context_encoded = self.connection.execute(
            "SELECT samoware_context FROM clients WHERE telegram_id=?",
            (telegram_id,),
        ).fetchone()
        context = loads(context_encoded[0])
        debug(f"requested samoware context for the client {telegram_id}")
        return context

    def is_client_active(self, telegram_id: int) -> bool:
        is_active = (
            self.connection.execute(
                "SELECT COUNT(*) FROM clients WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()[0]
            != 0
        )
        debug(f"client {telegram_id} is active: {is_active}")
        return is_active

    def get_all_clients(self) -> list:
        def map_client_from_tuple(client):
            (telegram_id, context) = client
            return (telegram_id, loads(context))

        clients = list(
            map(
                map_client_from_tuple,
                self.connection.execute(
                    "SELECT telegram_id, samoware_context FROM clients"
                ).fetchall(),
            )
        )
        debug(f"fetching all clients from database, an amount of the clients {len(clients)}")
        return clients

    def remove_client(self, telegram_id: int) -> None:
        self.connection.execute(
            "DELETE FROM clients WHERE telegram_id=?", (telegram_id,)
        )
        self.connection.commit()
        debug(f"client {telegram_id} was removed")
