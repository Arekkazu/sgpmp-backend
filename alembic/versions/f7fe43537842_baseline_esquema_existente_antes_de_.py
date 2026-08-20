"""baseline: esquema existente antes de Alembic

Revision ID: f7fe43537842
Revises:
Create Date: 2026-08-20 08:49:27.316240

No-op intencional: el esquema hasta este punto se construyó a mano (Paso 0
de cada módulo aplicado directo vía MCP postgres, ver anotaciones/*/cu*_gaps_bd_*.md).
Esta revisión solo marca el punto de partida para que las migraciones nuevas
(a partir de RF-23) tengan una base coherente sobre la que aplicarse, sin
intentar recrear todo lo que ya existe.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7fe43537842'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
