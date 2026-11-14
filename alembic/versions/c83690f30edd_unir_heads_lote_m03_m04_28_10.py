# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | Lote fixes M03/M04 RF-53/RF-54/RF-60: une los heads de #806, #807, #811 y #813 |
"""Une los cuatro heads del lote de fixes M03/M04 del 28-10.

Los cuatro cuelgan de ebbb160365e5 y no se pisan entre sí:

- #806 (b68127f54a01, RF-54): columna modulo3.heartbeats.json_metricas_buffer.
- #807 (c68227f60a01, RF-60): fn_procesar_heartbeat y sp_clasificar_estado_dispositivo.
- #811 (c685130a0260, RF-53): bloque de frecuencia anómala de fn_ingesta_telemetria.
- #813 (c687132a0270, RF-54): snapshot de reloj (TIME_DESYNC) de fn_ingesta_telemetria.

#811 y #813 editan la misma función, pero cada una reemplaza un bloque distinto
sobre la definición vigente y falla si no lo encuentra exactamente una vez, así
que el orden entre ellas da igual (probado en los dos sentidos, también el downgrade).

Revision ID: c83690f30edd
Revises: b68127f54a01, c68227f60a01, c685130a0260, c687132a0270
Create Date: 2026-10-28 12:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'c83690f30edd'
down_revision: Union[str, Sequence[str], None] = (
    'b68127f54a01', 'c68227f60a01', 'c685130a0260', 'c687132a0270')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
