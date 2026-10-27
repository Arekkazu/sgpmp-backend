"""Fusionar cabezas en conflicto

Revision ID: 1acdde52a4f5
Revises: c32b50fa71e7, ebbb160365e5
Create Date: 2026-10-27 08:47:56.602263

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1acdde52a4f5'
down_revision: Union[str, Sequence[str], None] = ('c32b50fa71e7', 'ebbb160365e5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
