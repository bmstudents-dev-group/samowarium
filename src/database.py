import sqlite3
from datetime import datetime

from samoware_client import SamowareContext

db = sqlite3.connect("database.db", check_same_thread=False)


def addClient(telegram_id, samoware_login, samovar_session):
    db.execute(
        "INSERT INTO clients VALUES(?, ?, ?)",
        (telegram_id, samoware_login, samovar_session),
    )
    db.commit()


def setSamowareContext(telegram_id, samoware_context:SamowareContext):
    db.execute(
        "UPDATE clients SET samoware_session=? WHERE telegram_id=?",
        (samoware_context.session, telegram_id),
    )
    db.commit()


def getSamowareContext(telegram_id) -> SamowareContext:
    samoware_login, samoware_session = db.execute(
        "SELECT samoware_login, samoware_session FROM clients WHERE telegram_id=?",
        (telegram_id,),
    ).fetchone()
    return SamowareContext(samoware_login, samoware_session, 0, 0, 0, datetime.now())


def isClientActive(telegram_id):
    result = db.execute(
        "SELECT COUNT(*) FROM clients WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()[0]
    return result != 0


def getAllClients():
    return db.execute("SELECT telegram_id FROM clients").fetchall()


def removeClient(telegram_id):
    db.execute("DELETE FROM clients WHERE telegram_id=?", (telegram_id,))
    db.commit()
