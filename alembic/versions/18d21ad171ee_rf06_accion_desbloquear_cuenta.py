"""RF-06: acción administrativa 'desbloquear' en enum_accion_cuenta

Revision ID: 18d21ad171ee
Revises: d3d166092570
Create Date: 2026-10-11

RF-06 define la acción 'Desbloquear' (solo aplicable a cuentas BLOQUEADAS,
400 si no). La bitácora modulo1.gestiones_cuenta guarda la acción en
enum_accion_cuenta, que no tenía ese valor.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '18d21ad171ee'
down_revision: Union[str, Sequence[str], None] = 'd3d166092570'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE modulo1.enum_accion_cuenta ADD VALUE IF NOT EXISTS 'desbloquear'")


def downgrade() -> None:
    # Postgres no permite quitar valores de un enum: 'desbloquear' queda en el
    # tipo (mismo criterio que cf12e716a4ec). El código anterior no lo usa.
    pass
