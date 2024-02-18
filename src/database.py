import sqlite3

db = sqlite3.connect("database.db", check_same_thread=False)


def addClient(telegram_id, samoware_login, samovar_session):
    db.execute(
        "INSERT INTO clients VALUES(?, ?, ?)",
        (telegram_id, samoware_login, samovar_session),
    )
    db.commit()


def setSession(telegram_id, samovar_session):
    db.execute(
        "UPDATE clients SET samoware_session=? WHERE telegram_id=?",
        (samovar_session, telegram_id),
    )
    db.commit()

def getClient(telegram_id):
    return db.execute(
        "SELECT * FROM clients WHERE telegram_id=?",
        (telegram_id,)
    ).fetchone()

def clientActive(telegram_id):
    return db.execute(
        "SELECT COUNT(*) FROM clients WHERE telegram_id = ?",
        (telegram_id,)
    ).fetchone()[0] != 0

def loadAllClients():
    return db.execute("SELECT * FROM clients").fetchall()


def removeClient(telegram_id):
    db.execute("DELETE FROM clients WHERE telegram_id=?", (telegram_id,))
    db.commit()
