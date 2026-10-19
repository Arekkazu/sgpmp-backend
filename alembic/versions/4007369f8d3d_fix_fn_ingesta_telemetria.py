"""fix_fn_ingesta_telemetria

Revision ID: 4007369f8d3d
Revises: 3a9d5e7c1b24
Create Date: 2026-10-19 10:44:37.335274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4007369f8d3d'
down_revision: Union[str, Sequence[str], None] = '3a9d5e7c1b24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.execute(
    """
        CREATE OR REPLACE FUNCTION modulo3.fn_ingesta_telemetria(
            p_id_dispositivo integer,
            p_id_sensor integer,
            p_id_variable integer,
            p_valor_crudo numeric,
            p_unidad character varying,
            p_timestamp_captura timestamp with time zone,
            p_timestamp_envio timestamp with time zone,
            p_origen modulo3.enum_telemetria_origen,
            p_categoria_variable modulo3.enum_telemetria_categoria_variable,
            p_tipo_dato modulo3.enum_telemetria_tipo_dato,
            p_valor_agregado boolean,
            p_ventana_agregacion integer,
            p_latitud numeric,
            p_longitud numeric,
            p_nivel_bateria numeric,
            p_calidad_rssi numeric,
            p_calidad_snr numeric,
            p_estado_conectividad boolean,
            p_metadatos jsonb)
            RETURNS TABLE(id_telemetria integer, estado_calidad modulo3.enum_telemetria_estado_calidad, mensaje text) 
            LANGUAGE 'plpgsql'
            COST 100
            VOLATILE PARALLEL UNSAFE
            ROWS 1000
        AS $BODY$
        DECLARE
            v_ts_procesamiento    TIMESTAMPTZ := NOW();
            v_valor_ajustado      NUMERIC(10,4) := NULL;
            v_calibrado          BOOLEAN := FALSE;
            v_offset              NUMERIC;
            v_ganancia            NUMERIC;
            v_cal_encontrada      BOOLEAN;
            
            -- Variables para contexto, umbrales y rangos físicos
            v_id_especie          INTEGER;
            v_umbral_min          NUMERIC(8,2);
            v_umbral_max          NUMERIC(8,2);
            v_rango_fisico_min    NUMERIC(8,2);
            v_rango_fisico_max    NUMERIC(8,2);
            v_unidad_esperada     VARCHAR(10);
            
            -- Latencia dinámica
            v_latencia_max_ms     INTEGER := 2000;
            v_latencia_ms         INTEGER;
            v_latencia_alta       BOOLEAN := FALSE;
            
            v_frecuencia_esp      INTEGER := NULL;
            v_dato_buferizado     BOOLEAN;
            v_estado              modulo3.enum_telemetria_estado_calidad := 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad;
            v_mensaje             TEXT := 'OK';
            vid_telemetria        INTEGER;
            
            -- Manejo de opcionales
            v_tipo_dato           modulo3.enum_telemetria_tipo_dato;
            v_valor_agregado      BOOLEAN;
            v_ventana_agregacion  INTEGER;
            v_lat                 NUMERIC;
            v_lon                 NUMERIC;
            v_bateria             NUMERIC;
            v_rssi                NUMERIC;
            v_snr                 NUMERIC;
            v_conectividad        BOOLEAN;
            v_metadatos           JSONB;
        BEGIN
            v_tipo_dato          := COALESCE(p_tipo_dato, 'CRUDO'::modulo3.enum_telemetria_tipo_dato);
            v_valor_agregado     := COALESCE(p_valor_agregado, FALSE);
            v_ventana_agregacion := p_ventana_agregacion;
            v_lat                := p_latitud;
            v_lon                := p_longitud;
            v_bateria            := p_nivel_bateria;
            v_rssi               := p_calidad_rssi;
            v_snr                := p_calidad_snr;
            v_conectividad       := COALESCE(p_estado_conectividad, TRUE);
            v_metadatos          := COALESCE(p_metadatos, '{}'::JSONB);

           ----------------------------------------------------------------------------
            -- FASE 0: LATENCIA ALINEADA (HU #3546)
            ----------------------------------------------------------------------------
            -- 1. Intentar obtener el intervalo de transmisión específico del dispositivo (en ms)
            SELECT (cr.intervalo_transmision * 1000) INTO v_latencia_max_ms
            FROM modulo9.configuraciones_remotas cr
            WHERE cr.id_dispositivo_iot = p_id_dispositivo 
            AND cr.estado = 'APLICADA'
            ORDER BY cr.fecha_aplicacion DESC
            LIMIT 1;

            -- 2. Si el dispositivo no tiene configuración específica, usar la global (en ms)
            IF v_latencia_max_ms IS NULL THEN
                SELECT (cg.frecuencia_muestreo * 1000) INTO v_latencia_max_ms
                FROM modulo9.configuraciones_globales cg
                WHERE cg.es_activo = TRUE
                LIMIT 1;
            END IF;

            -- 3. Fallback de seguridad si no hay registros en M09 (2000 ms = 2 segundos)
            v_latencia_max_ms := COALESCE(v_latencia_max_ms, 2000);

            -- 4. Cálculo de latencia y evaluación
            v_latencia_ms   := EXTRACT(EPOCH FROM (v_ts_procesamiento - p_timestamp_envio))::INTEGER * 1000;
            v_latencia_alta := (v_latencia_ms > v_latencia_max_ms);

            ----------------------------------------------------------------------------
            -- FASE 1: VALIDACIÓN ESTRUCTURAL (HU #3547)
            ----------------------------------------------------------------------------
            IF p_id_dispositivo IS NULL OR p_id_sensor IS NULL OR p_id_variable IS NULL
            OR p_valor_crudo IS NULL OR p_unidad IS NULL OR p_timestamp_captura IS NULL THEN
            
                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_ESTRUCTURA'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_ESTRUCTURA: Campos obligatorios faltantes.',
                    jsonb_build_object(
                        'valor_crudo', p_valor_crudo,
                        'unidad', p_unidad,
                        'id_variable', p_id_variable
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_ESTRUCTURA: Campos obligatorios faltantes.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 2: AUTENTICACIÓN (HU #3547)
            ----------------------------------------------------------------------------
            IF NOT modulo3.fn_validar_dispositivo(p_id_dispositivo, p_id_sensor) THEN
            
                INSERT INTO modulo3.bitacora_ingest (id_dispositivo_iot, id_sensor, valor_crudo, motivo_rechazo, timestamp_rechazo)
                VALUES (p_id_dispositivo, p_id_sensor, p_valor_crudo, 'ERROR_AUTENTICACION: Dispositivo o sensor no activo.', v_ts_procesamiento);

                RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_AUTENTICACION: Dispositivo o sensor no activo.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 3: COHERENCIA TEMPORAL (HU #3547)
            ----------------------------------------------------------------------------
            -- 3.1. Validación de fecha futura
            IF p_timestamp_captura > v_ts_procesamiento THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_TIEMPO'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_TIEMPO: timestamp_captura futuro.',
                    jsonb_build_object(
                        'valor_crudo', p_valor_crudo,
                        'timestamp_captura', p_timestamp_captura,
                        'origen', p_origen
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_TIEMPO: timestamp_captura futuro.'::TEXT;
                RETURN;
            END IF;

            -- 3.2. Validación de antigüedad máxima para datos buferizados (> 72 horas)
            v_dato_buferizado := (p_origen = 'BUFFER_LOCAL');

            IF v_dato_buferizado AND p_timestamp_captura < v_ts_procesamiento - INTERVAL '72 hours' THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_TIEMPO'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_TIEMPO: Dato buffer > 72h.',
                    jsonb_build_object(
                        'valor_crudo', p_valor_crudo,
                        'timestamp_captura', p_timestamp_captura,
                        'origen', p_origen
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_TIEMPO: Dato buffer > 72h.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 4: CRUCE DE UNIDAD Y UMBRAL POR ESPECIE (HU #3544 y #3547)
            ----------------------------------------------------------------------------
            -- 4.1. Buscar la especie asociada a la infraestructura/área del sensor
            SELECT inf.id_especie INTO v_id_especie
            FROM modulo9.sensores s
            JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot
            JOIN modulo9.infraestructuras inf ON d.id_infraestructura = inf.id_infraestructura
            WHERE s.id_sensores = p_id_sensor;

            -- 4.2. Consultar unidad, umbral por especie específica y rango físico de M09
            SELECT 
                va.unidad, 
                ua.valor_min, 
                ua.valor_max,
                va.rango_fisico_min,
                va.rango_fisico_max
            INTO 
                v_unidad_esperada, 
                v_umbral_min, 
                v_umbral_max,
                v_rango_fisico_min,
                v_rango_fisico_max
            FROM modulo9.variables_ambientales va
            LEFT JOIN modulo9.umbrales_ambientales ua 
                ON ua.id_variable_ambiental = va.id_variable_ambiental 
                AND ua.id_especie = v_id_especie  
            WHERE va.id_variable_ambiental = p_id_variable AND va.es_activo = TRUE;

            -- 4.3. Validar coincidencia de unidad de medida
            IF v_unidad_esperada IS NOT NULL AND LOWER(p_unidad) <> LOWER(v_unidad_esperada) THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_UNIDAD'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_UNIDAD: Unidad incorrecta.',
                    jsonb_build_object(
                        'unidad_recibida', p_unidad,
                        'unidad_esperada', v_unidad_esperada,
                        'id_variable', p_id_variable,
                        'id_especie', v_id_especie
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_UNIDAD: Unidad incorrecta.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 5: RANGO FÍSICO M09 (HU #3545 y #3547)
            ----------------------------------------------------------------------------
            IF v_rango_fisico_min IS NOT NULL AND v_rango_fisico_max IS NOT NULL THEN
                IF p_valor_crudo > v_rango_fisico_max OR p_valor_crudo < v_rango_fisico_min THEN

                    INSERT INTO modulo3.bitacora_ingest (
                        id_dispositivo_iot,
                        id_sensor,
                        estado_calidad,
                        descripcion_text,
                        payload_recibido,
                        fecha_evento,
                        fecha_captura_dato
                    )
                    VALUES (
                        p_id_dispositivo,
                        p_id_sensor,
                        'ERROR_SENSOR'::modulo3.enum_bitacora_ingest_estado_calidad,
                        'ERROR_SENSOR: Valor físicamente imposible.',
                        jsonb_build_object(
                            'valor_crudo', p_valor_crudo,
                            'rango_fisico_min', v_rango_fisico_min,
                            'rango_fisico_max', v_rango_fisico_max,
                            'id_variable', p_id_variable
                        ),
                        v_ts_procesamiento,
                        p_timestamp_captura
                    );

                    RETURN QUERY SELECT NULL::INTEGER, 
                                        NULL::modulo3.enum_telemetria_estado_calidad,
                                        'ERROR_SENSOR: Valor físicamente imposible.'::TEXT;
                    RETURN;
                END IF;
            END IF;
            ----------------------------------------------------------------------------
            -- FASE 6: DUPLICADOS (HU #3547)
            ----------------------------------------------------------------------------
            IF modulo3.fn_es_duplicado(p_id_sensor, p_id_variable, p_timestamp_captura, p_origen) THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_DUPLICADO'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_DUPLICADO: Registro ya existe.',
                    jsonb_build_object(
                        'valor_crudo', p_valor_crudo,
                        'id_variable', p_id_variable,
                        'origen', p_origen
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_DUPLICADO: Registro ya existe.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 7: CALIBRACIÓN NULL Y FUERA DE RANGO OPERATIVO (HU #3544 y #3545)
            ----------------------------------------------------------------------------
            SELECT p_offset, p_ganancia, p_encontrado
            INTO v_offset, v_ganancia, v_cal_encontrada
            FROM modulo3.fn_obtener_calibracion(p_id_sensor, p_id_dispositivo);

            IF v_cal_encontrada THEN
                v_valor_ajustado := (p_valor_crudo * v_ganancia) + v_offset;
                v_calibrado      := TRUE;
            ELSE
                -- HU #3545: Sin calibración, el valor ajustado DEBE ser explícitamente NULL
                v_valor_ajustado := NULL;
                v_calibrado      := FALSE;
                v_estado         := 'ERROR_CALIBRACION'::modulo3.enum_telemetria_estado_calidad;
                v_mensaje        := 'Sin calibración – valor ajustado es nulo.';
            END IF;

            -- Evaluamos FUERA_DE_RANGO (HU #3544) en línea (Sin abortar, solo marcando estado de calidad)
            IF v_umbral_min IS NOT NULL AND v_umbral_max IS NOT NULL THEN
                
                -- Usamos el ajustado, pero si es null por falta de calibración, evaluamos el crudo
                IF COALESCE(v_valor_ajustado, p_valor_crudo) < v_umbral_min OR 
                COALESCE(v_valor_ajustado, p_valor_crudo) > v_umbral_max THEN
                
                    -- Jerarquía: Solo marcamos FUERA_DE_RANGO si venía limpio. 
                    -- Si ya era ERROR_CALIBRACION arriba, se conserva ese error primario.
                    IF v_estado = 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad THEN
                        v_estado  := 'FUERA_DE_RANGO'::modulo3.enum_telemetria_estado_calidad;
                        v_mensaje := 'Valor fuera de rango operativo de la especie.';
                    END IF;
                END IF;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 8: ESTRUCTURA AGREGADO (HU #3547)
            ----------------------------------------------------------------------------
            IF v_valor_agregado AND v_ventana_agregacion IS NULL THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_ESTRUCTURA'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_ESTRUCTURA: Agregado sin ventana.',
                    jsonb_build_object(
                        'valor_crudo', p_valor_crudo,
                        'valor_agregado', v_valor_agregado,
                        'ventana_agregacion', v_ventana_agregacion
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_ESTRUCTURA: Agregado sin ventana.'::TEXT;
                RETURN;
            END IF;
            ----------------------------------------------------------------------------
            -- FASE 9: PERSISTENCIA FINAL EN TELEMETRIAS
            ----------------------------------------------------------------------------
            INSERT INTO modulo3.telemetrias (
                id_sensor, 
                id_variable, 
                id_dispositivo_iot,
                valor_crudo, 
                valor_ajustado,
                timestamp_captura, 
                timestamp_envio, 
                timestamp_procesamiento,
                origen, 
                estado_calidad, 
                calibrado,
                latitud, 
                longitud, 
                metadatos,
                categoria_variable, 
                unidad_medida,
                valor_agregado, 
                ventana_agregacion_min,
                tipo_dato,
                latencia_alta, 
                frecuencia_anomala,
                posible_drift, 
                dato_buferizado,
                dato_agredado_edge, 
                latencia_procesamiento_ms,
                nivel_bateria_pct, 
                calidad_senal_rssi, 
                calidad_senal_snr,
                frecuencia_muestreo_min, 
                estado_conectividad
            )
            VALUES (
                p_id_sensor, 
                p_id_variable, 
                p_id_dispositivo,
                p_valor_crudo, 
                v_valor_ajustado,
                p_timestamp_captura, 
                p_timestamp_envio, 
                v_ts_procesamiento,
                p_origen, 
                v_estado, 
                v_calibrado,
                v_lat, 
                v_lon, 
                v_metadatos,
                p_categoria_variable, 
                p_unidad,
                v_valor_agregado, 
                v_ventana_agregacion,
                v_tipo_dato,
                v_latencia_alta, 
                FALSE, -- frecuencia_anomala
                FALSE, -- posible_drift
                v_dato_buferizado,
                (v_tipo_dato = 'EVENTO_EDGE'), -- dato_agredado_edge
                v_latencia_ms,
                v_bateria, 
                v_rssi, 
                v_snr,
                NULL, -- frecuencia_muestreo_min (fijo en nulo por ahora)
                v_conectividad
            )
            RETURNING telemetrias.id_telemetria INTO vid_telemetria;

            RETURN QUERY SELECT vid_telemetria, v_estado, v_mensaje;
        END;
        $BODY$;
        """)


def downgrade() -> None:

    op.execute("""
    CREATE OR REPLACE FUNCTION modulo3.fn_ingesta_telemetria(
            p_id_dispositivo integer,
            p_id_sensor integer,
            p_id_variable integer,
            p_valor_crudo numeric,
            p_unidad character varying,
            p_timestamp_captura timestamp with time zone,
            p_timestamp_envio timestamp with time zone,
            p_origen modulo3.enum_telemetria_origen,
            p_categoria_variable modulo3.enum_telemetria_categoria_variable,
            p_tipo_dato modulo3.enum_telemetria_tipo_dato,
            p_valor_agregado boolean,
            p_ventana_agregacion integer,
            p_latitud numeric,
            p_longitud numeric,
            p_nivel_bateria numeric,
            p_calidad_rssi numeric,
            p_calidad_snr numeric,
            p_estado_conectividad boolean,
            p_metadatos jsonb)
            RETURNS TABLE(id_telemetria integer, estado_calidad modulo3.enum_telemetria_estado_calidad, mensaje text) 
            LANGUAGE 'plpgsql'
            COST 100
            VOLATILE PARALLEL UNSAFE
            ROWS 1000
        AS $BODY$
        DECLARE
            v_ts_procesamiento   TIMESTAMPTZ := NOW();
            v_valor_ajustado     NUMERIC(10,4);
            v_calibrado          BOOLEAN := FALSE;
            v_offset             NUMERIC;
            v_ganancia           NUMERIC;
            v_cal_encontrada     BOOLEAN;
            v_umbral_min         NUMERIC(8,2);
            v_umbral_max         NUMERIC(8,2);
            v_frecuencia_esp     INTEGER := NULL;
            v_unidad_esperada    VARCHAR(10);
            v_latencia_ms        INTEGER;
            v_latencia_alta      BOOLEAN := FALSE;
            v_dato_buferizado    BOOLEAN;
            v_estado             modulo3.enum_telemetria_estado_calidad := 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad;
            v_mensaje            TEXT := 'OK';
            vid_telemetria       INTEGER;
            v_tipo_dato          modulo3.enum_telemetria_tipo_dato;
            v_valor_agregado     BOOLEAN;
            v_ventana_agregacion INTEGER;
            v_lat                NUMERIC;
            v_lon                NUMERIC;
            v_bateria            NUMERIC;
            v_rssi               NUMERIC;
            v_snr                NUMERIC;
            v_conectividad       BOOLEAN;
            v_metadatos          JSONB;
        BEGIN
            v_tipo_dato          := COALESCE(p_tipo_dato, 'CRUDO'::modulo3.enum_telemetria_tipo_dato);
            v_valor_agregado     := COALESCE(p_valor_agregado, FALSE);
            v_ventana_agregacion := p_ventana_agregacion;
            v_lat                := p_latitud;
            v_lon                := p_longitud;
            v_bateria            := p_nivel_bateria;
            v_rssi               := p_calidad_rssi;
            v_snr                := p_calidad_snr;
            v_conectividad       := COALESCE(p_estado_conectividad, TRUE);
            v_metadatos          := COALESCE(p_metadatos, '{}'::JSONB);

            -- Fase 0: latencia
            v_latencia_ms   := EXTRACT(EPOCH FROM (v_ts_procesamiento - p_timestamp_envio))::INTEGER * 1000;
            v_latencia_alta := v_latencia_ms > 2000;

            -- Fase 1: validación estructural
            IF p_id_dispositivo IS NULL OR p_id_sensor IS NULL OR p_id_variable IS NULL
               OR p_valor_crudo IS NULL OR p_unidad IS NULL OR p_timestamp_captura IS NULL THEN
                RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_ESTRUCTURA: Campos obligatorios faltantes.'::TEXT;
                RETURN;
            END IF;

            -- Fase 2: autenticación
            IF NOT modulo3.fn_validar_dispositivo(p_id_dispositivo, p_id_sensor) THEN
                RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_AUTENTICACION: Dispositivo o sensor no activo.'::TEXT;
                RETURN;
            END IF;

            -- Fase 3: coherencia temporal
            IF p_timestamp_captura > v_ts_procesamiento THEN
                RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_TIEMPO: timestamp_captura futuro.'::TEXT;
                RETURN;
            END IF;

            v_dato_buferizado := (p_origen = 'BUFFER_LOCAL');
            IF v_dato_buferizado AND p_timestamp_captura < v_ts_procesamiento - INTERVAL '72 hours' THEN
                RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_TIEMPO: Dato buffer > 72h.'::TEXT;
                RETURN;
            END IF;

            -- Fase 4: unidad y rango (NO leemos frecuencia_muestreo porque no existe)
            SELECT va.unidad, ua.valor_min, ua.valor_max
            INTO v_unidad_esperada, v_umbral_min, v_umbral_max
            FROM modulo9.variables_ambientales va
            LEFT JOIN modulo9.umbrales_ambientales ua ON ua.id_variable_ambiental = va.id_variable_ambiental
            WHERE va.id_variable_ambiental = p_id_variable AND va.es_activo = TRUE
            LIMIT 1;

            IF v_unidad_esperada IS NOT NULL AND LOWER(p_unidad) <> LOWER(v_unidad_esperada) THEN
                RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_UNIDAD: Unidad incorrecta.'::TEXT;
                RETURN;
            END IF;

            -- Fase 5: valor físicamente imposible
            IF v_umbral_min IS NOT NULL AND v_umbral_max IS NOT NULL THEN
                IF p_valor_crudo > v_umbral_max * 5 OR p_valor_crudo < v_umbral_min * 5 * -1 THEN
                    RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                        'ERROR_SENSOR: Valor físicamente imposible.'::TEXT;
                    RETURN;
                END IF;
            END IF;

            -- Fase 6: duplicados
            IF modulo3.fn_es_duplicado(p_id_sensor, p_id_variable, p_timestamp_captura, p_origen) THEN
                RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_DUPLICADO: Registro ya existe.'::TEXT;
                RETURN;
            END IF;

            -- Fase 7: calibración
            SELECT p_offset, p_ganancia, p_encontrado
            INTO v_offset, v_ganancia, v_cal_encontrada
            FROM modulo3.fn_obtener_calibracion(p_id_sensor, p_id_dispositivo);

            IF v_cal_encontrada THEN
                v_valor_ajustado := (p_valor_crudo * v_ganancia) + v_offset;
                v_calibrado      := TRUE;
            ELSE
                v_valor_ajustado := p_valor_crudo;
                v_calibrado      := FALSE;
                v_estado         := 'ERROR_CALIBRACION'::modulo3.enum_telemetria_estado_calidad;
                v_mensaje        := 'Sin calibración – se usa valor crudo.';
            END IF;

            -- Evaluar FUERA_DE_RANGO
            IF v_umbral_min IS NOT NULL AND v_umbral_max IS NOT NULL THEN
                IF v_valor_ajustado < v_umbral_min OR v_valor_ajustado > v_umbral_max THEN
                    IF v_estado = 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad THEN
                        v_estado  := 'FUERA_DE_RANGO'::modulo3.enum_telemetria_estado_calidad;
                        v_mensaje := 'Valor fuera de rango operativo.';
                    END IF;
                END IF;
            END IF;

            -- Fase 8: dato agregado sin ventana
            IF v_valor_agregado AND v_ventana_agregacion IS NULL THEN
                RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_ESTRUCTURA: Agregado sin ventana.'::TEXT;
                RETURN;
            END IF;

            -- Fase 9: persistencia
            INSERT INTO modulo3.telemetrias (
                id_sensor, id_variable, id_dispositivo_iot,
                valor_crudo, valor_ajustado,
                timestamp_captura, timestamp_envio, timestamp_procesamiento,
                origen, estado_calidad, calibrado,
                latitud, longitud, metadatos,
                categoria_variable, unidad_medida,
                valor_agregado, ventana_agregacion_min,
                tipo_dato,
                latencia_alta, frecuencia_anomala,
                posible_drift, dato_buferizado,
                dato_agredado_edge, reloj_desincronizado,
                latencia_procesamiento_ms,
                nivel_bateria_pct, calidad_senal_rssi, calidad_senal_snr,
                frecuencia_muestreo_min, estado_conectividad
            )
            VALUES (
                p_id_sensor, p_id_variable, p_id_dispositivo,
                p_valor_crudo, v_valor_ajustado,
                p_timestamp_captura, p_timestamp_envio, v_ts_procesamiento,
                p_origen, v_estado, v_calibrado,
                v_lat, v_lon, v_metadatos,
                p_categoria_variable, p_unidad,
                v_valor_agregado, v_ventana_agregacion,
                v_tipo_dato,
                v_latencia_alta, FALSE,
                FALSE, v_dato_buferizado,
                (v_tipo_dato = 'EVENTO_EDGE'), FALSE,
                v_latencia_ms,
                v_bateria, v_rssi, v_snr,
                v_frecuencia_esp,
                v_conectividad
            )
            RETURNING telemetrias.id_telemetria INTO vid_telemetria;

            RETURN QUERY SELECT vid_telemetria, v_estado, v_mensaje;
        END;
        $BODY$;
    """)