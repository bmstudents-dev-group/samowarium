import sqlite3
import pickle
import json
import dateutil.parser
import util
import logging

from samoware_client import SamowareContext


DB_FOLDER_PATH = "db"
DB_PATH = f"{DB_FOLDER_PATH}/database.db"
util.makeDirIfNotExist(DB_FOLDER_PATH)
# TODO: в рамках рефакторинга избавиться от глобального состояния
db = sqlite3.connect(DB_PATH, check_same_thread=False)


def map_context_to_dict(context: SamowareContext) -> dict:
    try:
        cookies = context.cookies.get_dict()
    except:
        cookies = context.cookies

    return {
        "login": context.login,
        "ack_seq": context.ackSeq,
        "command_id": context.command_id,
        "cookies": cookies,
        "last_revalidate": context.last_revalidate.isoformat(),
        "request_id": context.request_id,
        "session": context.session,
        "rand": context.rand,
    }


def map_context_from_dict(d: dict) -> SamowareContext:
    return SamowareContext(
        login=d["login"],
        session=d["session"],
        request_id=d["request_id"],
        command_id=d["command_id"],
        rand=d["rand"],
        ackSeq=d["ack_seq"],
        last_revalidate=dateutil.parser.isoparse(d["last_revalidate"]),
        cookies=d["cookies"],
    )


def initDB():
    db.execute(
        "CREATE TABLE IF NOT EXISTS clients(telegram_id PRIMARY KEY, samoware_context)"
    )
    for telegram_id, context in getAllClients():
        setSamowareContext(telegram_id, context)
    logging.info("db was initialized")


def closeConnection():
    db.close()


def addClient(telegram_id: int, context: SamowareContext) -> None:
    context_encoded = json.dumps(map_context_to_dict(context))
    db.execute(
        "INSERT INTO clients VALUES(?, ?)",
        (telegram_id, context_encoded),
    )
    db.commit()


def setSamowareContext(telegram_id: int, context: SamowareContext) -> None:
    context_encoded = json.dumps(map_context_to_dict(context))
    context
    db.execute(
        "UPDATE clients SET samoware_context=? WHERE telegram_id=?",
        (context_encoded, telegram_id),
    )
    db.commit()


def getSamowareContext(telegram_id: int) -> SamowareContext:
    context_encoded = db.execute(
        "SELECT samoware_context FROM clients WHERE telegram_id=?",
        (telegram_id,),
    ).fetchone()
    context = map_context_from_dict(json.loads(context_encoded[0]))
    return context


def isClientActive(telegram_id: int) -> bool:
    result = db.execute(
        "SELECT COUNT(*) FROM clients WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()[0]
    return result != 0


def getAllClients() -> list:
    def mapClient(client):
        (telegram_id, context) = client
        try:
            return (telegram_id, map_context_from_dict(json.loads(context)))
        except:
            return (telegram_id, pickle.loads(context))

    return list(
        map(
            mapClient,
            db.execute("SELECT telegram_id, samoware_context FROM clients").fetchall(),
        )
    )


def removeClient(telegram_id: int) -> None:
    db.execute("DELETE FROM clients WHERE telegram_id=?", (telegram_id,))
    db.commit()
