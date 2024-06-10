"""
add password column
"""

from yoyo import step

__depends__ = {"20240608_01_VFpWp-create-clients-table"}

steps = [
    step(
        """
        ALTER TABLE clients
        ADD password TEXT;
        """
    )
]
