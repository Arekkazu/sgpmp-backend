"""fix_logicaCacheDasboardIot

Revision ID: 60bf7fe3d775
Revises: e5a3c9b17d42
Create Date: 2026-10-21 23:03:39.047852

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60bf7fe3d775'
down_revision: Union[str, Sequence[str], None] = 'e5a3c9b17d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        r"""
CREATE OR REPLACE FUNCTION modulo3.fn_actualizar_estado_sensor()
RETURNS trigger
LANGUAGE 'plpgsql'
COST 100
VOLATILE NOT LEAKPROOF
AS $BODY$
DECLARE
    v_semaforo   TEXT := 'VERDE';
    v_tiene_umbral BOOLEAN;
BEGIN
    -- RF-58 (1): Filtro de calidad ampliado
    IF NEW.estado_calidad NOT IN (
        'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad,
        'FUERA_DE_RANGO'::modulo3.enum_telemetria_estado_calidad,
        'ERROR_CALIBRACION'::modulo3.enum_telemetria_estado_calidad
    ) THEN
        RETURN NEW;
    END IF;

    -- RF-58 (3): Semáforo GRIS si no hay umbral activo para la variable
    -- y la especie asociada a la infraestructura del sensor
    SELECT EXISTS (
        SELECT 1
        FROM modulo3.sensores s
        JOIN modulo9.umbrales_ambientales u
          ON u.id_especie  = s.id_especie
         AND u.id_variable = NEW.id_variable
        WHERE s.id_sensor = NEW.id_sensor
          AND u.es_activo = TRUE
    )
    INTO v_tiene_umbral;

    IF NOT v_tiene_umbral THEN
        v_semaforo := 'GRIS';
    END IF;

    INSERT INTO modulo3.estados_actuales_sensores (
        id_dispositivo_iot, id_sensor,
        ultimo_valor, ultima_unidad, ultimo_timestamp_captura,
        ultimo_timestamp_actualizacion,
        estado_semaforo, estado_calidad, estado_conectividad, dato_desactualizado
    ) VALUES (
        NEW.id_dispositivo_iot, NEW.id_sensor,
        NEW.valor_ajustado, NEW.unidad_medida, NEW.timestamp_captura,
        now(),
        v_semaforo, NEW.estado_calidad,
        CASE WHEN NEW.estado_conectividad
             THEN 'ACTIVO'::modulo3.enum_estado_dispositivo
             ELSE 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo
        END,
        FALSE
    )
    ON CONFLICT (id_sensor) DO UPDATE SET
        id_dispositivo_iot             = EXCLUDED.id_dispositivo_iot,
        ultimo_valor                   = EXCLUDED.ultimo_valor,
        ultima_unidad                  = EXCLUDED.ultima_unidad,
        ultimo_timestamp_captura       = EXCLUDED.ultimo_timestamp_captura,
        ultimo_timestamp_actualizacion = now(),
        estado_semaforo                = EXCLUDED.estado_semaforo,
        estado_calidad                 = EXCLUDED.estado_calidad,
        estado_conectividad            = EXCLUDED.estado_conectividad,
        dato_desactualizado            = FALSE;

    RETURN NEW;
END;
$BODY$;
        """
    )


def downgrade() -> None:
    op.execute(
        r"""
CREATE OR REPLACE FUNCTION modulo3.fn_actualizar_estado_sensor()
RETURNS trigger
LANGUAGE 'plpgsql'
COST 100
VOLATILE NOT LEAKPROOF
AS $BODY$
BEGIN
    IF NEW.estado_calidad <> 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad THEN
        RETURN NEW;
    END IF;

    INSERT INTO modulo3.estados_actuales_sensores (
        id_dispositivo_iot, id_sensor,
        ultimo_valor, ultima_unidad, ultimo_timestamp_captura,
        ultimo_timestamp_actualizacion,
        estado_semaforo, estado_calidad, estado_conectividad, dato_desactualizado
    ) VALUES (
        NEW.id_dispositivo_iot, NEW.id_sensor,
        NEW.valor_ajustado, NEW.unidad_medida, NEW.timestamp_captura,
        now(),
        'VERDE', NEW.estado_calidad,
        CASE WHEN NEW.estado_conectividad
             THEN 'ACTIVO'::modulo3.enum_estado_dispositivo
             ELSE 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo
        END,
        FALSE
    )
    ON CONFLICT (id_sensor) DO UPDATE SET
        id_dispositivo_iot             = EXCLUDED.id_dispositivo_iot,
        ultimo_valor                   = EXCLUDED.ultimo_valor,
        ultima_unidad                  = EXCLUDED.ultima_unidad,
        ultimo_timestamp_captura       = EXCLUDED.ultimo_timestamp_captura,
        ultimo_timestamp_actualizacion = now(),
        estado_semaforo                = EXCLUDED.estado_semaforo,
        estado_calidad                 = EXCLUDED.estado_calidad,
        estado_conectividad            = EXCLUDED.estado_conectividad,
        dato_desactualizado            = FALSE;

    RETURN NEW;
END;
$BODY$;
        """
    )