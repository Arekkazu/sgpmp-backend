"""fix: ajustar precision de umbrales ambientales a numeric(5,2) segun RF-17

Revision ID: 1147428cd8fb
Revises: 281e99d58ecb
Create Date: 2026-09-18 12:51:25.666792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1147428cd8fb'
down_revision: Union[str, Sequence[str], None] = '281e99d58ecb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE modulo9.umbrales_ambientales ALTER COLUMN valor_min TYPE NUMERIC(5,2);")
    op.execute("ALTER TABLE modulo9.umbrales_ambientales ALTER COLUMN valor_max TYPE NUMERIC(5,2);")


def downgrade() -> None:
    op.execute("ALTER TABLE modulo9.umbrales_ambientales ALTER COLUMN valor_min TYPE NUMERIC(8,2);")
    op.execute("ALTER TABLE modulo9.umbrales_ambientales ALTER COLUMN valor_max TYPE NUMERIC(8,2);")
