import sqlite3

db = sqlite3.connect("database.db", check_same_thread=False)

db.execute(
    "CREATE TABLE clients(telegram_id PRIMARY KEY, samoware_context)"
)
