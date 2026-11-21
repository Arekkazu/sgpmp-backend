# | Fecha      | Nombre     | Que se hizo                                                              |
# |------------|------------|--------------------------------------------------------------------------|
# | 2026-11-01 | SamuelPR21 | INC-M04-251-G166 RF-62: advisory lock no bloqueante en fn_actualizar_estado_sensor |
# | 2026-11-02 | Arekkazu   | INC-M04-251-G166 RF-58: lock de dos claves (3558), permisos solo si el rol existe |
"""fix_concurrency_advisory_lock_mod9

Revision ID: 9b7d64203f48
Revises: 33ae7f41e560
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

El lock es de dos claves, (3558, id_sensor): el espacio de una sola clave lo usan
otros locks del backend (5246052, 10101608) y un id_sensor igual chocaría con ellos.
3558 no lo usa ningún otro lock (los demás: 680, 3505, 3514, 3544, 4802, 6363 y
0x52463234).

Costo aceptado: en una ráfaga, si la transacción que se omite trae la lectura más
reciente, la caché conserva la anterior hasta la siguiente lectura del sensor. La
telemetría no se pierde (la fila de telemetrias se inserta igual); solo el valor del
dashboard puede quedar una lectura atrás.

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


# Mismo patrón que a3c9e5d17b42: los roles existen en DEV/TEST/PROD pero no en una BD limpia
# (CI y verificación local). CREATE OR REPLACE ya conserva dueño y permisos donde existen.
_PERMISOS = """
    DO $$
    DECLARE r text;
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sgpmp_owner')
           AND pg_has_role(current_user, 'sgpmp_owner', 'MEMBER') THEN
            ALTER FUNCTION modulo3.fn_actualizar_estado_sensor() OWNER TO sgpmp_owner;
        END IF;
        GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO PUBLIC;
        FOR r IN SELECT rolname FROM pg_roles
                 WHERE rolname IN ('rol_app', 'rol_dev', 'rol_impl', 'rol_migracion',
                                   'sgpmp_app', 'sgpmp_owner') LOOP
            EXECUTE format('GRANT EXECUTE ON FUNCTION modulo3.fn_actualizar_estado_sensor() TO %I', r);
        END LOOP;
    END $$;
"""


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

            -- Intervención DBA (2026-11-01): lock transaccional por sensor, sin espera.
            -- Evita que las transacciones del mismo sensor se serialicen en el UPSERT
            -- bajo ráfagas de telemetría. Si otra transacción ya actualiza la caché de
            -- este sensor, se omite esta escritura intermedia (la lectura queda en
            -- telemetrias; la caché puede quedar una lectura atrás hasta la siguiente).
            -- Dos claves: 3558 es el espacio de esta caché (RF-58).
            IF pg_try_advisory_xact_lock(3558, NEW.id_sensor) THEN
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

    """ + _PERMISOS)


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

    """ + _PERMISOS)