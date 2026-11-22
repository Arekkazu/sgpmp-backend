from typing import Sequence, Union
 
from alembic import op
 
 
# revision identifiers, used by Alembic.
revision: str = "c94c177b885a"
# Rebasado sobre el head actual de dev. Verificar con `alembic heads` (una sola línea).
down_revision: Union[str, Sequence[str], None] = "6bd01d026ac4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
 
 
def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1) Contacto del dispositivo: evitar UPDATE cuando no hay cambio real
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_telemetria_actualiza_contacto_dispositivo()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.estado_calidad = 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad THEN
                -- Solo escribe si el nuevo timestamp es estrictamente mayor.
                -- Equivale al GREATEST anterior, pero sin generar una versión
                -- nueva de la fila cuando el valor no cambia.
                UPDATE modulo3.estados_dispositivos_iot
                SET
                    fecha_ultimo_contacto      = NEW.timestamp_procesamiento,
                    fecha_ultima_actualizacion = now()
                WHERE id_dispositivo_iot = NEW.id_dispositivo_iot
                  AND (fecha_ultimo_contacto IS NULL
                       OR fecha_ultimo_contacto < NEW.timestamp_procesamiento);
            END IF;
            RETURN NEW;
        END;
        $function$;
    """)
 
    # ------------------------------------------------------------------
    # 2) Estado actual del sensor (caché del dashboard)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_actualizar_estado_sensor()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
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
            -- RFC-012: la especie se obtiene por la tabla puente
            -- modulo9.infraestructuras_especies (infraestructuras.id_especie ya no existe).
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
 
            -- Upsert de la caché. El WHERE del DO UPDATE omite la escritura si la
            -- caché ya tiene una lectura igual o más reciente.
            -- OJO: la fila en conflicto queda bloqueada igual (comportamiento
            -- documentado de ON CONFLICT DO UPDATE); solo se ahorra la escritura.
            -- Cambio de comportamiento: lecturas desordenadas o con el mismo
            -- timestamp_captura ya no sobrescriben la caché.
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
        $function$;
    """)
 
 
def downgrade() -> None:
    """
    Restaura las funciones a su definición previa (sin los WHERE de no-op).
    IMPORTANTE: debe coincidir con la definición vigente en 6bd01d026ac4.
    Verificar que ninguna migración entre 67e33de11180 y 6bd01d026ac4 haya
    modificado estas funciones; si alguna lo hizo, copiar esa versión aquí.
    """
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
 
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo3.fn_actualizar_estado_sensor()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
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