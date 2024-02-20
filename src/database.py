import sqlite3
import pickle

from samoware_client import SamowareContext

db = sqlite3.connect("database.db", check_same_thread=False)


def addClient(telegram_id, context):
    context_encoded = pickle.dumps(context)
    db.execute(
        "INSERT INTO clients VALUES(?, ?)",
        (telegram_id, context_encoded),
    )
    db.commit()


def setSamowareContext(telegram_id, context:SamowareContext):
    context_encoded = pickle.dumps(context)
    db.execute(
        "UPDATE clients SET samoware_context=? WHERE telegram_id=?",
        (context_encoded, telegram_id),
    )
    db.commit()


def getSamowareContext(telegram_id) -> SamowareContext:
    context_encoded = db.execute(
        "SELECT samoware_context FROM clients WHERE telegram_id=?",
        (telegram_id,),
    ).fetchone()
    context = pickle.loads(context_encoded[0])
    return context


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
