# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-02 RF-73: tipo de evento NOTAS_REGISTRADAS     |
"""rf73: tipo de evento NOTAS_REGISTRADAS en la bitácora M04

Revision ID: 67e33de11180
Revises: 8a8f1dae36f1
Create Date: 2026-10-29

QA M04 (27-10) CU09 H-02 / CU05 H-09 / CU05 H-05: guardar las notas de
validación clínica (RF-69 fase 4) se registraba como ``VERSION_APROBADA``. El
historial de transiciones de la versión mostraba entonces "Aprobada" a nombre
del Veterinario, incluso sobre una versión RECHAZADO. Aprobar lo hace solo el
sistema al validar las métricas; registrar notas es otra acción y necesita su
propio tipo en ``modulo4.enum_tipo_evento_auditoria_m04``.

Solo agrega un valor al enum. No toca tablas, filas, políticas ni triggers.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '67e33de11180'
down_revision: Union[str, Sequence[str], None] = '8a8f1dae36f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE modulo4.enum_tipo_evento_auditoria_m04 ADD VALUE IF NOT EXISTS 'NOTAS_REGISTRADAS'"
    )


def downgrade() -> None:
    # Postgres no permite quitar valores de un enum (mismo criterio que 18d21ad171ee).
    # La bitácora es append-only: los eventos ya registrados con este tipo se conservan.
    pass
