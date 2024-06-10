"""
create clients table
"""

from yoyo import step

__depends__ = {}

steps = [
    step(
        """
        CREATE TABLE IF NOT EXISTS clients(
            telegram_id BLOB PRIMARY KEY,
            samoware_context BLOB
        );
        """
    )
]
