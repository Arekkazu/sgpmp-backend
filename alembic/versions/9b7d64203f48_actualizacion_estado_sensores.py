# | Fecha      | Nombre     | Que se hizo                                                              |
# |------------|------------|--------------------------------------------------------------------------|
# | 2026-11-01 | SamuelPR21 | INC-M04-251-G166 RF-62: advisory lock no bloqueante en fn_actualizar_estado_sensor |
"""fix_concurrency_advisory_lock_mod9

Revision ID: a1b2c3d4e5f6
Revises: c94c177b885a
Create Date: 2026-11-01

INC-M04-251-G166 (TC-M03-G166): El trigger trg_rf58_01_cache_estado_sensor
usa ON CONFLICT DO UPDATE sobre modulo9.estados_actuales_sensores. Aunque la
migración c94c177b885a añadió un WHERE condicional, PostgreSQL adquiere un
row-level exclusive lock ANTES de evaluar el WHERE. Bajo ráfagas de 41+
lecturas concurrentes del mismo sensor, las transacciones se serializan,
agotan el pool de conexiones (pool_size=5) y producen ReadTimeout (45s).

Corrección: reemplazar el ON CONFLICT bloqueante por pg_try_advisory_xact_lock.
Si otra transacción ya está actualizando el mismo sensor, el lock no se adquiere
y se omite la actualización intermedia (la última transacción que logre el lock
escribe el estado final). Esto elimina la serialización sin sacrificar la
consistencia del cache.

No se modifica la estructura de la tabla, solo el cuerpo de la función trigger.
RLS, FORCE RLS y triggers de auditoría permanecen intactos.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b7d64203f48'
down_revision: Union[str, Sequence[str], None] = '33ae7f41e560'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_actualizar_estado_sensor()
            RETURNS trigger
            LANGUAGE 'plpgsql'
            COST 100
            VOLATILE NOT LEAKPROOF
        AS $BODY$
        DECLARE
            v_semaforo           TEXT := 'VERDE';
            v_tiene_umbral       BOOLEAN;
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

            -- RF-58 (3): Semáforo GRIS si ninguna especie del área tiene umbral activo.
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
                  AND (saa.fecha_finalizacion IS NULL
                       OR saa.fecha_finalizacion > NEW.timestamp_captura)
                  AND u.es_activo = TRUE
            )
            INTO v_tiene_umbral;

            IF NOT v_tiene_umbral THEN
                v_semaforo := 'GRIS';
            END IF;

            -- RFC-020 D-2 (RF-60 CA-23): la conectividad del dashboard es el estado del dispositivo
            SELECT ed.estado_actual INTO v_estado_dispositivo
            FROM modulo3.estados_dispositivos_iot ed
            WHERE ed.id_dispositivo_iot = NEW.id_dispositivo_iot;

            -- Intervención DBA (2026-11-03): Lock transaccional a nivel de aplicación.
            -- Evita condiciones de carrera y bloqueos pesados en el UPSERT bajo alta
            -- concurrencia de telemetría. Si otra transacción ya procesa este sensor,
            -- ignoramos esta actualización intermedia para no saturar el motor.
            IF pg_try_advisory_xact_lock(NEW.id_sensor) THEN
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
                    dato_desactualizado            = FALSE
                WHERE estados_actuales_sensores.ultimo_timestamp_captura IS NULL
                   OR estados_actuales_sensores.ultimo_timestamp_captura < EXCLUDED.ultimo_timestamp_captura;
            END IF;

            RETURN NEW;
        END;
        $BODY$;

        ALTER FUNCTION modulo3.fn_actualizar_estado_sensor() OWNER TO sgpmp_owner;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO PUBLIC;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO rol_app;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO rol_dev;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO rol_impl;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO rol_migracion;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO sgpmp_app;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO sgpmp_owner;
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_actualizar_estado_sensor()
            RETURNS trigger
            LANGUAGE 'plpgsql'
            COST 100
            VOLATILE NOT LEAKPROOF
        AS $BODY$
        DECLARE
            v_semaforo           TEXT := 'VERDE';
            v_tiene_umbral       BOOLEAN;
            v_estado_dispositivo modulo3.enum_estado_dispositivo;
        BEGIN
            IF NEW.estado_calidad NOT IN (
                'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad,
                'FUERA_DE_RANGO'::modulo3.enum_telemetria_estado_calidad,
                'ERROR_CALIBRACION'::modulo3.enum_telemetria_estado_calidad
            ) THEN
                RETURN NEW;
            END IF;

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
                  AND (saa.fecha_finalizacion IS NULL
                       OR saa.fecha_finalizacion > NEW.timestamp_captura)
                  AND u.es_activo = TRUE
            )
            INTO v_tiene_umbral;

            IF NOT v_tiene_umbral THEN
                v_semaforo := 'GRIS';
            END IF;

            SELECT ed.estado_actual INTO v_estado_dispositivo
            FROM modulo3.estados_dispositivos_iot ed
            WHERE ed.id_dispositivo_iot = NEW.id_dispositivo_iot;

            -- Downgrade: Sin Advisory Lock (comportamiento original)
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
                dato_desactualizado            = FALSE
            WHERE estados_actuales_sensores.ultimo_timestamp_captura IS NULL
               OR estados_actuales_sensores.ultimo_timestamp_captura < EXCLUDED.ultimo_timestamp_captura;

            RETURN NEW;
        END;
        $BODY$;

        ALTER FUNCTION modulo3.fn_actualizar_estado_sensor() OWNER TO sgpmp_owner;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO PUBLIC;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO rol_app;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO rol_dev;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO rol_impl;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO rol_migracion;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO sgpmp_app;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO sgpmp_owner;
    """)