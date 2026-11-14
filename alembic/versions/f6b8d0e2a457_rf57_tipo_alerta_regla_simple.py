# | Fecha      | Nombre | Que se hizo                                                          |
# |------------|--------|----------------------------------------------------------------------|
# | 2026-10-31 | Claude | INC-M03-240-G69 RF-57: valor REGLA_SIMPLE en enum_tipo_alerta          |
"""rf57: tipo de alerta REGLA_SIMPLE

Revision ID: f6b8d0e2a457
Revises: e5a7c9d1f346
Create Date: 2026-10-31

INC-M03-240-G69 (#881). RF-57 Fase 5 define reglas simples con severidad propia y E14
dice que, sin compuesta aplicable, "se genera una alerta independiente por cada
variable". `enum_tipo_alerta` solo tenía tipos compuestos, así que una lectura aislada
de temperatura, humedad u oxígeno disuelto fuera de su banda NORMAL se rechazaba con
422 REGLA_COMPUESTA_NO_ACTIVADA y no alertaba (ver la decisión 1 de
anotaciones/modulo_3/inc_m03_163_g70_condicion_minima_compuestas.md).

`REGLA_SIMPLE` identifica esa alerta sin hacerla pasar por la compuesta (BUG-G70-01).
Ninguna función, trigger ni CHECK de la BD enumera los tipos de alerta.

downgrade: PostgreSQL no permite quitar un valor de un ENUM sin recrear el tipo y las
columnas que lo usan; se deja el valor (no rompe nada si no se usa).
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f6b8d0e2a457'
down_revision: Union[str, Sequence[str], None] = 'e5a7c9d1f346'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE modulo3.enum_tipo_alerta ADD VALUE IF NOT EXISTS 'REGLA_SIMPLE'")


def downgrade() -> None:
    pass
