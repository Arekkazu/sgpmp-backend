"""BRK-09 (RF-53 E15): marca de variable crítica en el catálogo de M09

Revision ID: b0eb84a30467
Revises: b3d4f69e9303
Create Date: 2026-10-19 17:30:00

La cola de prioridad del broker bajo saturación (BRK-09, RF-53 E15) trata
como crítica toda lectura de una variable que el Administrador marque en el
catálogo de M09. Esa marca es `es_critica`, el nombre que el broker busca
(`app/db/repositories/registry.py`).

`NOT NULL DEFAULT false`: ninguna variable existente pasa a ser crítica sin
que alguien la marque, y el `ADD COLUMN` con default constante no reescribe
la tabla (PG ≥ 11). El broker la detecta por `information_schema`: mientras
la columna no exista, o su rol no tenga `SELECT` sobre ella, sigue con el
resto de las reglas (control, heartbeat, eventos Edge y `nivel_umbral`).

Pendiente fuera de esta revisión: que Análisis apruebe la definición de
"crítico" (AN-5) y que M09 exponga la marca en el CRUD de variables.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b0eb84a30467'
down_revision: Union[str, Sequence[str], None] = 'b3d4f69e9303'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo9.variables_ambientales
            ADD COLUMN es_critica BOOLEAN NOT NULL DEFAULT false;

        COMMENT ON COLUMN modulo9.variables_ambientales.es_critica IS
            'RF-53 E15 / BRK-09: las lecturas de esta variable van a la cola P0 del broker cuando hay saturación.';
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE modulo9.variables_ambientales DROP COLUMN es_critica")
