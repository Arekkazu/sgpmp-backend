"""merge all Alembic heads accumulated by fix/m02-fixes

Revision ID: 6af637931784
Revises: 2b747aaae732, 4f453b6d2b90, 69d26aea234c, 7abae1ee50f6, c977eab2eb0d
Create Date: 2026-09-23

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "6af637931784"
down_revision: Union[str, Sequence[str], None] = (
    "2b747aaae732",
    "4f453b6d2b90",
    "69d26aea234c",
    "7abae1ee50f6",
    "c977eab2eb0d",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
