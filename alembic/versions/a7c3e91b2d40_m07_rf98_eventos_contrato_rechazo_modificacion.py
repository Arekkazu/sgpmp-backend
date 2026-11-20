# | Fecha      | Nombre         | Que se hizo |
# |------------|----------------|-------------|
# | 2026-11-19 | LuisfNarvaez01 | INC-M07-375 RF-98/RF-102: eventos de transición rechazada y versión modificada |
"""RF-98/RF-102: eventos CONTRATO_TRANSICION_RECHAZADA y CONTRATO_MODIFICADO

Revision ID: a7c3e91b2d40
Revises: c8e1a7f30b52
Create Date: 2026-11-19

RF-98 CA-26/CA-27 exige auditar con severidad WARNING los intentos de transición inválidos, y RF-98
5.12 permite modificar una versión PENDIENTE (con su auditoría). El enum de tipos de evento de la
integración no tenía ninguno de los dos.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7c3e91b2d40'
down_revision: Union[str, Sequence[str], None] = 'c8e1a7f30b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for valor in ("CONTRATO_TRANSICION_RECHAZADA", "CONTRATO_MODIFICADO"):
        op.execute(f"ALTER TYPE modulo7.enum_evento_integracion_tipo_evento ADD VALUE IF NOT EXISTS '{valor}'")


def downgrade() -> None:
    # Postgres no permite quitar valores de un enum (mismo criterio que 18d21ad171ee).
    pass
