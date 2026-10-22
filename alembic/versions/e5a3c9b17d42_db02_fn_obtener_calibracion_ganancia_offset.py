"""DB-02 (RF-53/RF-24): fn_obtener_calibracion usa la ganancia y el offset reales

Revision ID: e5a3c9b17d42
Revises: c41f8e2d7a96
Create Date: 2026-10-19 23:30:00

`fn_ingesta_telemetria` (4007369f8d3d) calcula
`valor_ajustado = valor_crudo * ganancia + offset` con lo que devuelve
`modulo3.fn_obtener_calibracion`. Esa función es anterior a RF-24 (#1635):
devolvía `valor_referencia` como offset y una ganancia fija de 1.0, aunque
`modulo9.calibraciones` ya guarda `ganancia` y `offset_calibracion`
(NOT NULL, por defecto 1.0 y 0).

Mientras la ingesta HTTP calculaba en la aplicación (`CalibracionM09Adapter`,
que sí lee esas dos columnas) solo el canal MQTT tenía el valor ajustado
errado. Con la ingesta B+ de DEV-05 los dos canales pasan por la función: sin
esta corrección, toda lectura de un sensor calibrado quedaría con
`valor_ajustado` desplazado por el valor de referencia, y con él
FUERA_DE_RANGO, las alertas y el semáforo de RF-17.

La firma no cambia (D2 de AIOT-DEV-03).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5a3c9b17d42'
down_revision: Union[str, Sequence[str], None] = 'c41f8e2d7a96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CABECERA = """
    CREATE OR REPLACE FUNCTION modulo3.fn_obtener_calibracion(
        p_id_sensor integer, p_id_dispositivo integer,
        OUT p_offset numeric, OUT p_ganancia numeric, OUT p_encontrado boolean)
    RETURNS record
    LANGUAGE plpgsql
    STABLE
    AS $function$
    BEGIN
"""

_PIE = """
        IF NOT FOUND THEN
            p_offset     := 0;
            p_ganancia   := 1;
            p_encontrado := FALSE;
        END IF;
    END;
    $function$
"""


def upgrade() -> None:
    op.execute(_CABECERA + """
        -- RF-24: modelo lineal valor_ajustado = ganancia * crudo + offset_calibracion.
        SELECT offset_calibracion, ganancia, TRUE
        INTO p_offset, p_ganancia, p_encontrado
        FROM modulo9.calibraciones
        WHERE id_sensor          = p_id_sensor
          AND id_dispositivo_iot = p_id_dispositivo
        ORDER BY fecha_calibracion DESC
        LIMIT 1;
    """ + _PIE)


def downgrade() -> None:
    op.execute(_CABECERA + """
        SELECT
            COALESCE(valor_referencia, 0),
            1.0,
            TRUE
        INTO p_offset, p_ganancia, p_encontrado
        FROM modulo9.calibraciones
        WHERE id_sensor     = p_id_sensor
          AND id_dispositivo_iot = p_id_dispositivo
        ORDER BY fecha_calibracion DESC
        LIMIT 1;
    """ + _PIE)
