# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71/RF-73: tipo de evento REENTRENAMIENTO_SOLICITADO             |
"""rf71: tipo de evento REENTRENAMIENTO_SOLICITADO en la bitácora M04

Revision ID: 90fd5bff3519
Revises: c31f8a6d920e
Create Date: 2026-10-31

Desde 200 retroalimentaciones nuevas (parámetro min_registros_solicitud_reentrenamiento)
el Administrador o el Veterinario pueden solicitar el reentrenamiento del modelo
individual. La solicitud no ejecuta RF-71: queda como evento en la bitácora de M04
(RF-73), con quién la pidió y con cuántos datos. Necesita su propio tipo en
``modulo4.enum_tipo_evento_auditoria_m04``; REENTRENAMIENTO_INICIADO es del
pipeline, que todavía no corrió.

Solo agrega un valor al enum. No toca tablas, filas, políticas ni triggers.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '90fd5bff3519'
down_revision: Union[str, Sequence[str], None] = 'c31f8a6d920e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE modulo4.enum_tipo_evento_auditoria_m04 ADD VALUE IF NOT EXISTS 'REENTRENAMIENTO_SOLICITADO'"
    )


def downgrade() -> None:
    # Postgres no permite quitar valores de un enum (mismo criterio que 67e33de11180).
    # La bitácora es append-only: los eventos ya registrados con este tipo se conservan.
    pass
