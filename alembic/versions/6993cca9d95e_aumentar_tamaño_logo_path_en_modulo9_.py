"""Aumentar tamaño logo_path en modulo9.indentdiades visuales

Revision ID: 6993cca9d95e
Revises: a50010e91978
Create Date: 2026-09-07 10:04:08.646427

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6993cca9d95e'
down_revision: Union[str, Sequence[str], None] = 'a50010e91978'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE modulo9.identidad_visuales ALTER COLUMN logo_path TYPE VARCHAR(500);")


def downgrade():
    op.execute("ALTER TABLE modulo9.identidad_visuales ALTER COLUMN logo_path TYPE VARCHAR(255);")