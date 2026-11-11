# | Fecha      | Nombre       | Que se hizo                                                        |
# |------------|--------------|--------------------------------------------------------------------|
# | 2026-11-08 | destroyerban | INC-M06-313-G14 RF-83: tipo de evento MEDICION_EXCLUIDA en M06     |
"""v5.5.0 inc_m06_313: tipo de evento MEDICION_EXCLUIDA en la auditoría financiera

Revision ID: d81f3a5c7e02
Revises: b7e2d94c1a68
Create Date: 2026-11-08

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

INC-M06-313-G14 (#1000). La medición por evento (RF-83) debe excluir los activos que no son
elegibles (estado INACTIVO, AISLADO o CERRADO en M02, o PENDIENTE_RECONOCIMIENTO en M06 tras una
reversión) y dejar registro de la exclusión. ``modulo6.enum_auditoria_financiera_tipo_evento`` no
tenía un tipo para eso. Ninguna función, trigger ni CHECK de la BD enumera los tipos de M06.

downgrade: PostgreSQL no permite quitar un valor de un ENUM sin recrear el tipo y las
columnas que lo usan; se deja el valor (no rompe nada si no se usa).
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd81f3a5c7e02'
down_revision: Union[str, Sequence[str], None] = 'b7e2d94c1a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE modulo6.enum_auditoria_financiera_tipo_evento ADD VALUE IF NOT EXISTS 'MEDICION_EXCLUIDA'"
    )


def downgrade() -> None:
    pass
