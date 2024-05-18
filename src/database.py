import sqlite3
import pickle

from samoware_client import SamowareContext

DB_PATH = "db/database.db"
db = sqlite3.connect(DB_PATH, check_same_thread=False)


def init():
    db.execute("CREATE TABLE IF NOT EXISTS clients(telegram_id PRIMARY KEY, samoware_context)")


def addClient(telegram_id: int, context: SamowareContext) -> None:
    context_encoded = pickle.dumps(context)
    db.execute(
        "INSERT INTO clients VALUES(?, ?)",
        (telegram_id, context_encoded),
    )
    db.commit()


def setSamowareContext(telegram_id: int, context: SamowareContext) -> None:
    context_encoded = pickle.dumps(context)
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
    context = pickle.loads(context_encoded[0])
    return context


def isClientActive(telegram_id: int) -> bool:
    result = db.execute(
        "SELECT COUNT(*) FROM clients WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()[0]
    return result != 0


def getAllClients() -> list:
    return db.execute("SELECT telegram_id FROM clients").fetchall()


def removeClient(telegram_id: int) -> None:
    db.execute("DELETE FROM clients WHERE telegram_id=?", (telegram_id,))
    db.commit()
