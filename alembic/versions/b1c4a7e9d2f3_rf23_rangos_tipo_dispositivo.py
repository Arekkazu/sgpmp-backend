"""rf23 rangos de configuracion por tipo de dispositivo

Revision ID: b1c4a7e9d2f3
Revises: 192872fafd40
Create Date: 2026-08-24 00:00:00.000000

RF-23 (issue #1632) — rangos de configuracion por tipo de dispositivo IoT.

La tabla modulo9.dispositivos_iot no tenia nocion de "tipo", y la validacion
de frecuencia_captura / intervalo_transmision era un minimo fijo de 1 minuto
sin diferenciacion por hardware. Se agrega:

1. modulo9.tipos_dispositivo_iot: catalogo de tipos con los rangos min/max
   permitidos para cada parametro configurable. Los rangos son la "perilla de
   calibracion": los seeds son ilustrativos, se ajustan por SQL segun el
   hardware real.
2. dispositivos_iot.id_tipo_dispositivo: FK obligatoria. Se agrega nullable,
   se hace backfill de los dispositivos existentes al tipo GENERICO (que
   replica el comportamiento previo min=1), y luego se fuerza NOT NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c4a7e9d2f3'
down_revision: Union[str, Sequence[str], None] = '192872fafd40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tipos_dispositivo_iot",
        sa.Column("id_tipo_dispositivo", sa.Integer, primary_key=True),
        sa.Column("nombre", sa.String(50), nullable=False, unique=True),
        sa.Column("frecuencia_captura_min", sa.Integer, nullable=False),
        sa.Column("frecuencia_captura_max", sa.Integer, nullable=False),
        sa.Column("intervalo_transmision_min", sa.Integer, nullable=False),
        sa.Column("intervalo_transmision_max", sa.Integer, nullable=False),
        sa.Column(
            "fecha_creacion",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "frecuencia_captura_min >= 1 AND frecuencia_captura_max >= frecuencia_captura_min",
            name="tipos_dispositivo_iot_frecuencia_check",
        ),
        sa.CheckConstraint(
            "intervalo_transmision_min >= 1 AND intervalo_transmision_max >= intervalo_transmision_min",
            name="tipos_dispositivo_iot_intervalo_check",
        ),
        schema="modulo9",
    )

    # Seeds. GENERICO replica el comportamiento previo (min 1, sin tope real -> 1 dia).
    # ponytail: rangos seed ilustrativos; el hardware real necesita calibracion, ajustar por SQL/seed.
    op.execute(
        """
        INSERT INTO modulo9.tipos_dispositivo_iot
            (nombre, frecuencia_captura_min, frecuencia_captura_max,
             intervalo_transmision_min, intervalo_transmision_max)
        VALUES
            ('GENERICO', 1, 1440, 1, 1440),
            ('NODO_BAJO_CONSUMO', 15, 1440, 15, 1440),
            ('SENSOR_AMBIENTAL', 5, 120, 5, 240)
        """
    )

    # Columna FK: nullable -> backfill a GENERICO -> NOT NULL.
    op.add_column(
        "dispositivos_iot",
        sa.Column("id_tipo_dispositivo", sa.Integer, nullable=True),
        schema="modulo9",
    )
    op.execute(
        """
        UPDATE modulo9.dispositivos_iot
        SET id_tipo_dispositivo = (
            SELECT id_tipo_dispositivo FROM modulo9.tipos_dispositivo_iot WHERE nombre = 'GENERICO'
        )
        WHERE id_tipo_dispositivo IS NULL
        """
    )
    op.alter_column(
        "dispositivos_iot",
        "id_tipo_dispositivo",
        nullable=False,
        schema="modulo9",
    )
    op.create_foreign_key(
        "dispositivos_iot_id_tipo_dispositivo_fkey",
        "dispositivos_iot",
        "tipos_dispositivo_iot",
        ["id_tipo_dispositivo"],
        ["id_tipo_dispositivo"],
        source_schema="modulo9",
        referent_schema="modulo9",
    )


def downgrade() -> None:
    op.drop_constraint(
        "dispositivos_iot_id_tipo_dispositivo_fkey",
        "dispositivos_iot",
        schema="modulo9",
        type_="foreignkey",
    )
    op.drop_column("dispositivos_iot", "id_tipo_dispositivo", schema="modulo9")
    op.drop_table("tipos_dispositivo_iot", schema="modulo9")
