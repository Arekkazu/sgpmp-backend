# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: modo_sombra en resultados_inferencia del motor IA         |
"""rf66: modo_sombra en modulo4.resultados_inferencia

Revision ID: 785022cc8ef9
Revises: 6bd01d026ac4
Create Date: 2026-10-30

Por qué va por Alembic: es el patrón del repo y CI solo despliega lo que está
en `alembic/versions/`.

RF-66 / plan del motor M04: los modelos entregados (ET-02 v5, ET-03 v5) están
entrenados con datos sintéticos y solo autorizan el modo sombra: calculan y se
registran, pero no generan alertas. El resultado es inmutable
(`fn_historial_diagnostico_inmutable`), así que si fue vinculante o de sombra
tiene que quedar en la fila al insertarla: deducirlo del estado de la versión no
sirve, porque ese estado cambia después.

`DEFAULT false` es constante: Postgres agrega la columna sin reescribir filas
ni disparar el trigger BEFORE UPDATE. Las políticas RLS y los GRANT de la tabla
cubren la columna nueva sin cambios.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '785022cc8ef9'
down_revision: Union[str, Sequence[str], None] = '6bd01d026ac4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE modulo4.resultados_inferencia "
        "ADD COLUMN modo_sombra BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "COMMENT ON COLUMN modulo4.resultados_inferencia.modo_sombra IS "
        "'RF-66: el resultado se calculó en modo sombra (registra, no alerta).'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE modulo4.resultados_inferencia DROP COLUMN modo_sombra")
