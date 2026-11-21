# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | RFC-020 RF-58/RF-60: el dashboard refleja el estado del dispositivo |
"""rfc020: la conectividad del dashboard es el estado operativo del dispositivo

Revision ID: 8a8f1dae36f1
Revises: 4a4b067e7a24
Create Date: 2026-10-29

RFC-020 (#794), aclaración de RF-58 frente a RF-60:

D-1 — ``fn_marcar_sensores_sin_senal`` (trigger ``trg_rf60_05``, AFTER UPDATE de
``estados_dispositivos_iot`` cuando cambia ``estado_actual``) solo copiaba SIN_SEÑAL,
INACTIVO y el regreso a ACTIVO: el dashboard nunca mostraba BUFFER_ACTIVO ni
EN_MANTENIMIENTO. Ahora copia toda transición a los sensores del dispositivo.

D-2 — ``fn_actualizar_estado_sensor`` (trigger ``trg_rf58_01``, AFTER INSERT de
``telemetrias``) derivaba la conectividad del booleano de la lectura: una lectura
sincronizada desde el buffer (RF-54, ``estado_conectividad = false``) dejaba el sensor
en SIN_SEÑAL. Ahora toma ``estado_actual`` del dispositivo (DESCONOCIDO si aún no hay
estado). Solo la evaluación de RF-60 produce SIN_SEÑAL/INACTIVO.

Solo reemplaza dos funciones (CREATE OR REPLACE, misma firma); no toca tablas, filas
ni triggers. El downgrade restaura las definiciones anteriores (baseline y 60bf7fe3d775).
"""
from typing import Sequence, Union

from alembic import op

revision: str = '8a8f1dae36f1'
down_revision: Union[str, Sequence[str], None] = '4a4b067e7a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MARCAR = r"""
CREATE OR REPLACE FUNCTION modulo3.fn_marcar_sensores_sin_senal()
RETURNS trigger
LANGUAGE plpgsql
AS $BODY$
BEGIN
    -- 'SIN_SEÑAL' con tilde — valor real del enum_estado_dispositivo
    IF NEW.estado_actual IN ('SIN_SEÑAL','INACTIVO') THEN
        UPDATE modulo3.estados_actuales_sensores SET
            dato_desactualizado            = TRUE,
            estado_conectividad            = NEW.estado_actual,
            estado_semaforo                = 'GRIS',
            ultimo_timestamp_actualizacion = now()
        WHERE id_dispositivo_iot = NEW.id_dispositivo_iot;

    ELSE
        -- RFC-020 D-1 (RF-60 CA-22): BUFFER_ACTIVO, EN_MANTENIMIENTO y DESCONOCIDO
        -- también llegan al dashboard; solo ACTIVO vuelve a dar el dato por vigente.
        -- El trigger solo dispara si estado_actual cambió.
        UPDATE modulo3.estados_actuales_sensores SET
            dato_desactualizado            = CASE WHEN NEW.estado_actual = 'ACTIVO'
                                                  THEN FALSE ELSE dato_desactualizado END,
            estado_conectividad            = NEW.estado_actual,
            ultimo_timestamp_actualizacion = now()
        WHERE id_dispositivo_iot = NEW.id_dispositivo_iot;
    END IF;

    RETURN NEW;
END;
$BODY$;
"""

_INGESTA = r"""
CREATE OR REPLACE FUNCTION modulo3.fn_actualizar_estado_sensor()
RETURNS trigger
LANGUAGE 'plpgsql'
COST 100
VOLATILE NOT LEAKPROOF
AS $BODY$
DECLARE
    v_semaforo   TEXT := 'VERDE';
    v_tiene_umbral BOOLEAN;
    v_estado_dispositivo modulo3.enum_estado_dispositivo;
BEGIN
    -- RF-58 (1): Filtro de calidad ampliado
    IF NEW.estado_calidad NOT IN (
        'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad,
        'FUERA_DE_RANGO'::modulo3.enum_telemetria_estado_calidad,
        'ERROR_CALIBRACION'::modulo3.enum_telemetria_estado_calidad
    ) THEN
        RETURN NEW;
    END IF;

    -- RF-58 (3): Semáforo GRIS si ninguna especie del área donde está el sensor
    -- al momento de la captura tiene un umbral activo para la variable.
    -- El sensor no lleva especie: sensor -> área (sensores_areas_asociadas, vigente
    -- en la captura, como en DB-03) -> especies del área (DB-06) -> umbral.
    SELECT EXISTS (
        SELECT 1
        FROM modulo9.sensores_areas_asociadas saa
        JOIN modulo9.infraestructuras_especies ie
          ON ie.id_infraestructura = saa.id_infraestructura
        JOIN modulo9.umbrales_ambientales u
          ON u.id_especie            = ie.id_especie
         AND u.id_variable_ambiental = NEW.id_variable
        WHERE saa.id_sensor = NEW.id_sensor
          AND saa.fecha_asociacion <= NEW.timestamp_captura
          AND (saa.fecha_finalizacion IS NULL OR saa.fecha_finalizacion > NEW.timestamp_captura)
          AND u.es_activo = TRUE
    )
    INTO v_tiene_umbral;

    IF NOT v_tiene_umbral THEN
        v_semaforo := 'GRIS';
    END IF;

    -- RFC-020 D-2 (RF-60 CA-23): la conectividad del dashboard es el estado del
    -- dispositivo, no el booleano de la lectura (las de buffer llegan en false).
    SELECT ed.estado_actual INTO v_estado_dispositivo
    FROM modulo3.estados_dispositivos_iot ed
    WHERE ed.id_dispositivo_iot = NEW.id_dispositivo_iot;

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
        COALESCE(v_estado_dispositivo, 'DESCONOCIDO'::modulo3.enum_estado_dispositivo),
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

_MARCAR_ANTERIOR = r"""
CREATE OR REPLACE FUNCTION modulo3.fn_marcar_sensores_sin_senal()
RETURNS trigger
LANGUAGE plpgsql
AS $BODY$
BEGIN
    -- 'SIN_SEÑAL' con tilde — valor real del enum_estado_dispositivo
    IF NEW.estado_actual IN ('SIN_SEÑAL','INACTIVO') THEN
        UPDATE modulo3.estados_actuales_sensores SET
            dato_desactualizado            = TRUE,
            estado_conectividad            = NEW.estado_actual,
            estado_semaforo                = 'GRIS',
            ultimo_timestamp_actualizacion = now()
        WHERE id_dispositivo_iot = NEW.id_dispositivo_iot;

    ELSIF NEW.estado_actual = 'ACTIVO'
      AND OLD.estado_actual <> 'ACTIVO' THEN
        UPDATE modulo3.estados_actuales_sensores SET
            dato_desactualizado            = FALSE,
            estado_conectividad            = 'ACTIVO',
            ultimo_timestamp_actualizacion = now()
        WHERE id_dispositivo_iot = NEW.id_dispositivo_iot;
    END IF;

    RETURN NEW;
END;
$BODY$;
"""

_INGESTA_ANTERIOR = r"""
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

    -- RF-58 (3): Semáforo GRIS si ninguna especie del área donde está el sensor
    -- al momento de la captura tiene un umbral activo para la variable.
    -- El sensor no lleva especie: sensor -> área (sensores_areas_asociadas, vigente
    -- en la captura, como en DB-03) -> especies del área (DB-06) -> umbral.
    SELECT EXISTS (
        SELECT 1
        FROM modulo9.sensores_areas_asociadas saa
        JOIN modulo9.infraestructuras_especies ie
          ON ie.id_infraestructura = saa.id_infraestructura
        JOIN modulo9.umbrales_ambientales u
          ON u.id_especie            = ie.id_especie
         AND u.id_variable_ambiental = NEW.id_variable
        WHERE saa.id_sensor = NEW.id_sensor
          AND saa.fecha_asociacion <= NEW.timestamp_captura
          AND (saa.fecha_finalizacion IS NULL OR saa.fecha_finalizacion > NEW.timestamp_captura)
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


def upgrade() -> None:
    op.execute(_MARCAR)
    op.execute(_INGESTA)


def downgrade() -> None:
    op.execute(_INGESTA_ANTERIOR)
    op.execute(_MARCAR_ANTERIOR)
