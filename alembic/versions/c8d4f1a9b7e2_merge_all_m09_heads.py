"""merge all Alembic heads accumulated by fix/m09

Revision ID: c8d4f1a9b7e2
Revises: 47038edfa2fc, 58a6bfab5ce6, 5c844a858bde, 9a5de7d9973f, b9edb971f005, d8e232bc81a3
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c8d4f1a9b7e2"
down_revision: Union[str, Sequence[str], None] = (
    "47038edfa2fc",
    "58a6bfab5ce6",
    "5c844a858bde",
    "9a5de7d9973f",
    "b9edb971f005",
    "d8e232bc81a3",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
