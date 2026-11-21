# | Fecha      | Nombre       | Que se hizo                                                        |
# |------------|--------------|--------------------------------------------------------------------|
# | 2026-11-08 | destroyerban | INC-M06-306-G07 RF-82: tipo de evento ACCESO_NO_AUTORIZADO en M06  |
"""v5.5.0 inc_m06_306: tipo de evento ACCESO_NO_AUTORIZADO en la auditoría financiera

Revision ID: a3c5e7f9b201
Revises: b7e2d94c1a68
Create Date: 2026-11-08

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

INC-M06-306-G07 (#993). RNF-82-05 exige que el intento de un rol distinto al Contador sea
"rechazado y registrado en el log de auditoría". El 403 ya salía, pero
``modulo6.enum_auditoria_financiera_tipo_evento`` no tenía un tipo para ese intento y
``modulo6.auditorias_financieras`` no cambiaba. Ninguna función, trigger ni CHECK de la BD
enumera los tipos de evento de M06.

downgrade: PostgreSQL no permite quitar un valor de un ENUM sin recrear el tipo y las
columnas que lo usan; se deja el valor (no rompe nada si no se usa).
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a3c5e7f9b201'
down_revision: Union[str, Sequence[str], None] = 'b7e2d94c1a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE modulo6.enum_auditoria_financiera_tipo_evento ADD VALUE IF NOT EXISTS 'ACCESO_NO_AUTORIZADO'"
    )


def downgrade() -> None:
    pass
