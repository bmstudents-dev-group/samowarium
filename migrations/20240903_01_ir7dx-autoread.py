"""
autoread
"""

from yoyo import step

__depends__ = {"20240608_02_yk7yR-add-password-column"}

steps = [
    step(
        """
        ALTER TABLE clients
        ADD autoread INTEGER
        DEFAULT TRUE
        NOT NULL;
        """
    )
]
