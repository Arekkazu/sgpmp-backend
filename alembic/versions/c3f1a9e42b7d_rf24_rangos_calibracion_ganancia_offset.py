"""rf24 rangos de calibracion por tipo de sensor + ganancia/offset

Revision ID: c3f1a9e42b7d
Revises: b1c4a7e9d2f3
Create Date: 2026-08-25 00:00:00.000000

RF-24 (issue #1635) — validacion de rango de calibracion por tipo de sensor y
modelo de dos parametros (ganancia/offset).

Antes: modulo9.calibraciones solo validaba valor_referencia > 0 y solo guardaba
valor_referencia, obligando al consumidor de telemetry a aproximar
ganancia=1.0, offset=valor_referencia. Se agrega:

1. modulo9.rangos_calibracion: catalogo de rango de seguridad (min/max) por tipo
   de sensor (categoria del enum modulo3.enum_reglas_alertas_tipo_sensor). Los
   rangos son la "perilla de calibracion": los seeds son ilustrativos y se
   ajustan por SQL segun el estandar de calibracion real.
2. calibraciones.ganancia y calibraciones.offset_calibracion: el modelo lineal
   real (valor_ajustado = ganancia * crudo + offset). offset_calibracion se
   backfillea a valor_referencia para no romper al consumidor existente.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f1a9e42b7d'
down_revision: Union[str, Sequence[str], None] = 'b1c4a7e9d2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rangos_calibracion",
        sa.Column("id_rango_calibracion", sa.Integer, primary_key=True),
        sa.Column("categoria", sa.String(30), nullable=False, unique=True),
        sa.Column("valor_min", sa.Numeric(10, 4), nullable=False),
        sa.Column("valor_max", sa.Numeric(10, 4), nullable=False),
        sa.Column(
            "fecha_creacion",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "valor_max >= valor_min",
            name="rangos_calibracion_min_max_check",
        ),
        schema="modulo9",
    )

    # Seeds: un rango por cada valor del enum modulo3.enum_reglas_alertas_tipo_sensor.
    # ponytail: rangos seed ilustrativos (espejo de variables_ambientales acuicolas);
    # el estandar de calibracion real necesita tuning, ajustar por SQL/seed.
    op.execute(
        """
        INSERT INTO modulo9.rangos_calibracion (categoria, valor_min, valor_max)
        VALUES
            ('TEMPERATURA', 0, 45),
            ('OXIGENO', 0, 20),
            ('PH', 0, 14),
            ('AMONIACO', 0, 10),
            ('SALINIDAD', 0, 45),
            ('HUMEDAD', 0, 100),
            ('LUMINOSIDAD', 0, 100000)
        """
    )

    op.add_column(
        "calibraciones",
        sa.Column("ganancia", sa.Numeric(10, 4), nullable=False, server_default="1.0"),
        schema="modulo9",
    )
    op.add_column(
        "calibraciones",
        sa.Column("offset_calibracion", sa.Numeric(10, 4), nullable=False, server_default="0"),
        schema="modulo9",
    )
    # Preserva el comportamiento previo del consumidor: offset == valor_referencia.
    op.execute(
        "UPDATE modulo9.calibraciones SET offset_calibracion = valor_referencia"
    )


def downgrade() -> None:
    op.drop_column("calibraciones", "offset_calibracion", schema="modulo9")
    op.drop_column("calibraciones", "ganancia", schema="modulo9")
    op.drop_table("rangos_calibracion", schema="modulo9")
