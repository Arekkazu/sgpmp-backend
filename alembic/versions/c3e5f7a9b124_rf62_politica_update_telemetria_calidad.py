# | Fecha      | Nombre | Que se hizo                                                              |
# |------------|--------|--------------------------------------------------------------------------|
# | 2026-10-31 | Claude | INC-M03-239-G165 RF-62: política UPDATE para la transición VIGENTE→SUPERADA |
"""rf62: política UPDATE en telemetria_calidad para marcar SUPERADA

Revision ID: c3e5f7a9b124
Revises: b7d2e4f6a813
Create Date: 2026-10-31

INC-M03-239-G165 (#874). La RLS de modulo3 (0784d8c03206) trató `telemetria_calidad`
como append-only: tiene SELECT, INSERT y la política de servicio, pero no UPDATE.
La reevaluación (RF-62 CA-16, D7) marca la evaluación VIGENTE anterior como
SUPERADA con la identidad del usuario; sin política, PostgreSQL filtra el UPDATE
a 0 filas, SQLAlchemy lanza StaleDataError y la API responde 500.

`pol_telemetria_calidad_update` solo permite la única transición que existe:
- USING: la fila es VIGENTE y su lectura es visible para el usuario (mismo EXISTS
  que `pol_telemetria_calidad_select`).
- WITH CHECK: la fila queda SUPERADA. Una VIGENTE no se puede reescribir como otra
  VIGENTE ni una SUPERADA volver a VIGENTE; el resto de la evaluación sigue
  inmutable por diseño del caso de uso (solo cambia estado y motivo).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3e5f7a9b124'
down_revision: Union[str, Sequence[str], None] = 'b7d2e4f6a813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS pol_telemetria_calidad_update ON modulo3.telemetria_calidad")
    op.execute("""
        CREATE POLICY pol_telemetria_calidad_update ON modulo3.telemetria_calidad
        FOR UPDATE
        USING (
            estado_evaluacion = 'VIGENTE'
            AND EXISTS (SELECT 1 FROM modulo3.telemetrias t
                        WHERE t.id_telemetria = telemetria_calidad.id_telemetria)
        )
        WITH CHECK (
            estado_evaluacion = 'SUPERADA'
            AND EXISTS (SELECT 1 FROM modulo3.telemetrias t
                        WHERE t.id_telemetria = telemetria_calidad.id_telemetria)
        )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS pol_telemetria_calidad_update ON modulo3.telemetria_calidad")
