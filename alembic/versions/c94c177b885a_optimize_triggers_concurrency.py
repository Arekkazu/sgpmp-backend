"""optimize_triggers_concurrency

Revision ID: c94c177b885a
Revises: 67e33de11180
Create Date: 2026-10-29 17:49:08.157075

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c94c177b885a'
down_revision: Union[str, Sequence[str], None] = '67e33de11180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    """
    Optimiza los triggers fn_telemetria_actualiza_contacto_dispositivo y 
    fn_actualizar_estado_sensor para evitar bloqueos de fila (hot-row contention) 
    cuando llegan ráfagas de telemetría del mismo sensor.
    
    Cambios:
    1. fn_telemetria_actualiza_contacto_dispositivo: Solo actualiza si el nuevo 
       timestamp es mayor al actual (evita updates redundantes)
    2. fn_actualizar_estado_sensor: Agrega WHERE en ON CONFLICT DO UPDATE para 
       evitar actualizaciones si el dato en caché es más reciente
    """
    
    # Optimizar fn_telemetria_actualiza_contacto_dispositivo
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_telemetria_actualiza_contacto_dispositivo()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.estado_calidad = 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad THEN
                -- OPTIMIZACIÓN DE CONCURRENCIA: 
                -- Solo actualizar si el nuevo timestamp es estrictamente mayor al actual.
                -- Esto evita bloqueos de fila innecesarios (hot-row update) en ráfagas de telemetría.
                UPDATE modulo3.estados_dispositivos_iot 
                SET
                    fecha_ultimo_contacto      = NEW.timestamp_procesamiento,
                    fecha_ultima_actualizacion = now()
                WHERE id_dispositivo_iot = NEW.id_dispositivo_iot
                  AND (fecha_ultimo_contacto IS NULL OR fecha_ultimo_contacto < NEW.timestamp_procesamiento);
            END IF;
            RETURN NEW;
        END;
        $function$;
    """)
    
    # Optimizar fn_actualizar_estado_sensor
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_actualizar_estado_sensor()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
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

            -- RF-58 (3): Semáforo GRIS si ninguna especie del área tiene umbral activo.
            SELECT EXISTS (
                SELECT 1
                FROM modulo9.sensores_areas_asociadas saa
                JOIN modulo9.infraestructuras i ON i.id_infraestructura = saa.id_infraestructura
                JOIN modulo9.umbrales_ambientales u
                  ON u.id_especie            = i.id_especie
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

            -- RFC-020 D-2 (RF-60 CA-23): la conectividad del dashboard es el estado del dispositivo
            SELECT ed.estado_actual INTO v_estado_dispositivo
            FROM modulo3.estados_dispositivos_iot ed
            WHERE ed.id_dispositivo_iot = NEW.id_dispositivo_iot;

            -- OPTIMIZACIÓN DE CONCURRENCIA (Hot-Row Upsert):
            -- Agregamos una cláusula WHERE al DO UPDATE. Si el dato en caché es más reciente 
            -- que el que estamos intentando insertar, PostgreSQL omite el UPDATE, 
            -- liberando el bloqueo de fila inmediatamente y evitando la cola de espera.
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
            WHERE estados_actuales_sensores.ultimo_timestamp_captura < EXCLUDED.ultimo_timestamp_captura
               OR estados_actuales_sensores.ultimo_timestamp_captura IS NULL;

            RETURN NEW;
        END;
        $function$;
    """)


def downgrade():
    """
    Revierte los triggers a su versión original (sin optimizaciones de concurrencia).
    """
    
    # Restaurar fn_telemetria_actualiza_contacto_dispositivo
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_telemetria_actualiza_contacto_dispositivo()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.estado_calidad = 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad THEN
                UPDATE modulo3.estados_dispositivos_iot SET
                    fecha_ultimo_contacto      = GREATEST(COALESCE(fecha_ultimo_contacto,'1970-01-01'), NEW.timestamp_procesamiento),
                    fecha_ultima_actualizacion = now()
                WHERE id_dispositivo_iot = NEW.id_dispositivo_iot;
            END IF;
            RETURN NEW;
        END;
        $function$;
    """)
    
    # Restaurar fn_actualizar_estado_sensor
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_actualizar_estado_sensor()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        DECLARE
            v_semaforo   TEXT := 'VERDE';
            v_tiene_umbral BOOLEAN;
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
                  AND (saa.fecha_finalizacion IS NULL OR saa.fecha_finalizacion > NEW.timestamp_captura)
                  AND u.es_activo = TRUE
            )
            INTO v_tiene_umbral;

            IF NOT v_tiene_umbral THEN
                v_semaforo := 'GRIS';
            END IF;

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
        $function$;
    """)
