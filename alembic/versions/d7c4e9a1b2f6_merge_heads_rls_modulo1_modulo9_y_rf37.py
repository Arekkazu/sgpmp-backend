"""merge heads de RLS de módulos 1 y 9 y RF-37

Revision ID: d7c4e9a1b2f6
Revises: 5243bbbb28de, 8d80fb56a30b, a861b3ed96ad
Create Date: 2026-09-27 19:45:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d7c4e9a1b2f6"
down_revision: Union[str, Sequence[str], None] = (
    "5243bbbb28de",
    "8d80fb56a30b",
    "a861b3ed96ad",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
