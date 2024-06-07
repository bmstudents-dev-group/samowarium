from datetime import datetime
import sqlite3
import pickle
import json
import util
import logging

from samoware_client import SamowareContext


DB_FOLDER_PATH = "db"
DB_PATH = f"{DB_FOLDER_PATH}/database.db"
util.makeDirIfNotExist(DB_FOLDER_PATH)
# TODO: в рамках рефакторинга избавиться от глобального состояния
db = sqlite3.connect(DB_PATH, check_same_thread=False)


def initDB():
    db.execute(
        "CREATE TABLE IF NOT EXISTS clients(telegram_id PRIMARY KEY, samoware_context)"
    )
    for telegram_id, context in getAllClients():
        raw_context = json.dumps(context, default=util.data_serial)
        setSamowareContext(telegram_id, raw_context)
    logging.info("db was initialized")


def closeConnection():
    db.close()


def addClient(telegram_id: int, context: SamowareContext) -> None:
    context_encoded = json.dumps(context, default=util.data_serial)
    db.execute(
        "INSERT INTO clients VALUES(?, ?)",
        (telegram_id, context_encoded),
    )
    db.commit()


def setSamowareContext(telegram_id: int, context: SamowareContext) -> None:
    context_encoded = json.dumps(context, default=util.data_serial)
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
    context = json.loads(context_encoded[0], object_hook=util.date_hook)
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
            return (telegram_id, json.loads(context, object_hook=util.date_hook))
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
