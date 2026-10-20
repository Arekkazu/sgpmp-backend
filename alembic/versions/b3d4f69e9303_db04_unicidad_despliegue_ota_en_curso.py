"""DB-04 (RF-70): un solo despliegue OTA en curso por dispositivo y componente

Revision ID: b3d4f69e9303
Revises: 1164e0abedec
Create Date: 2026-10-19 17:00:00

D6 de `AIOT-DEV-03_Acuerdo_Consolidado_Desarrollo_AIoT.md`: el orquestador
OTA (DEV-15) crea una fila `PENDIENTE` en `despliegues_ota` por
(dispositivo, `tipo_modelo`, `componente`), y los reportes del nodo la
llevan a `EN_PROCESO` y luego a `EXITOSO` o `FALLIDO`. Si hubiera dos filas
abiertas para el mismo componente del mismo nodo, un reporte `ota/*` no sabría
a cuál aplicarse, y el nodo recibiría dos `notify` que compiten.

La unicidad se limita a los estados abiertos (`PENDIENTE`, `EN_PROCESO`). Los
cerrados (`EXITOSO`, `FALLIDO`, `SIN_CAMBIOS`) son el historial y se repiten.
`COALESCE(componente, '')` hace lo mismo que
`uq_version_modelo_activa_tipo_componente` (RFC-009): los modelos sin
componente (poblacionales) también quedan cubiertos, en vez de escaparse por
`NULL <> NULL`.

Las columnas extra que pida DEV-15 para la firma o la URL firmada no van aquí:
todavía no están definidas (tarea #3556) y llegarán en su propia revisión.
En `sgpmp_dev` la tabla está vacía, así que el índice se crea sin conflicto.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3d4f69e9303'
down_revision: Union[str, Sequence[str], None] = '1164e0abedec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_despliegue_ota_dispositivo_tipo_modelo_componente_en_curso
            ON modulo4.despliegues_ota (id_dispositivo_iot, tipo_modelo, COALESCE(componente, ''))
            WHERE estado_despliegue IN ('PENDIENTE', 'EN_PROCESO');
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX modulo4.uq_despliegue_ota_dispositivo_tipo_modelo_componente_en_curso")
