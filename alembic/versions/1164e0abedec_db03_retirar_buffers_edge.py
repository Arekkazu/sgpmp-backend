"""DB-03 (RF-54): retirar modulo3.buffers; el buffer vive en el Edge

Revision ID: 1164e0abedec
Revises: 65541db23c71
Create Date: 2026-10-19 16:00:00

Segunda parte del lote DB-03 (Ventana 2 AIoT, D10 de
`AIOT-DEV-03_Acuerdo_Consolidado_Desarrollo_AIoT.md`). El buffer FIFO lo
mantiene el nodo Edge. Al backend le llegan el aviso de buffer
(`POST /iot/eventos-buffer`, DEV-11, que crea una alerta técnica) y la
cantidad pendiente en cada heartbeat (`heartbeats.datos_pendientes_buffer`).
Ni el backend ni el broker leen ni escriben `modulo3.buffers`.

Qué se retira:
- la tabla `modulo3.buffers`, con su secuencia, índices y los 3 triggers RF-54;
- las funciones de trigger `fn_buffer_solo_delete_confirmado`,
  `fn_buffer_marcar_sincronizacion` y `fn_buffer_dato_inmutable`;
- los procedimientos que solo operaban esa tabla: `sp_registrar_en_buffer`,
  `sp_reintentar_buffer`, `sp_sincronizar_buffer_lote` y
  `sp_confirmar_sincronizacion_buffer`;
- los enums que solo usaba la tabla: `enum_buffers_estado_buffer` y
  `enum_buffers_politica_buffer`. `enum_buffer_nivel_severidad` se queda,
  porque lo usan alertas y eventos Edge.

Qué se reescribe para que nada quede apuntando a la tabla:
- `sp_clasificar_estado_dispositivo`: el estado `BUFFER_ACTIVO` sale ahora de
  `datos_pendientes_buffer > 0` en el último heartbeat del nodo.
- `sp_registrar_evento_edge`: deja de copiar el evento al buffer cuando el
  nodo está sin conectividad. El evento se sigue guardando en
  `eventos_edge_computing`.
- `vw_m03_dispositivo_operacional` y `vw_m03_telemetria_contextualizada`:
  conservan todas sus columnas, en el mismo orden y con el mismo tipo
  (`CREATE OR REPLACE VIEW` no permite quitar columnas, y así no se rompe
  quien las consulte). Los conteos de pendientes salen del último heartbeat.
  Los que solo existían en la tabla (confirmados, errores, intentos, horas,
  último dato del buffer) quedan en 0 o NULL.

Además se agregan `BUFFER_OVERFLOW` y `BUFFER_DATA_CORRUPTION` a
`enum_tipo_alerta_tecnica`, que son los subtipos que crea DEV-11. Ninguna
columna usa ese enum todavía (el subtipo vive en `alertas.tipo_variable`), así
que el cambio solo completa el catálogo.

Downgrade: recrea todo con las definiciones exactas de la revisión anterior,
extraídas de una BD construida con `alembic upgrade` y comparadas por md5 con
`sgpmp_dev`. **Las filas de `modulo3.buffers` no vuelven** (en DEV hay 5 de
prueba). Los GRANT que se hayan dado a mano a roles de entorno sobre la tabla
tampoco vuelven, porque no están en Alembic.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '1164e0abedec'
down_revision: Union[str, Sequence[str], None] = '65541db23c71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Valores de enum_tipo_alerta_tecnica antes de esta revisión (para el downgrade).
_ALERTA_TECNICA_ANTES = ['DISPOSITIVO_SIN_SEÑAL', 'DISPOSITIVO_INACTIVO', 'BATERIA_BAJA', 'BATERIA_CRITICA', 'SEÑAL_DEGRADADA', 'SENSOR_FISICO_FALLIDO', 'SOBRECALENTAMIENTO', 'FIRMWARE_DESACTUALIZADO', 'FALLO_MASIVO', 'BUFFER_PROLONGADO', 'DESINCRONIZACION_RELOJ', 'HEARTBEAT_AUSENTE', 'FALLO_INFRAESTRUCTURA_COMPARTIDA']
_ALERTA_TECNICA_NUEVOS = ['BUFFER_OVERFLOW', 'BUFFER_DATA_CORRUPTION']


# ── Definiciones nuevas ─────────────────────────────────────────────────────
_CLASIFICAR_NUEVO = r'''
CREATE OR REPLACE PROCEDURE modulo3.sp_clasificar_estado_dispositivo(IN p_id_dispositivo integer, IN p_margen_tolerancia_min integer DEFAULT 5, IN p_umbral_inactivo_horas integer DEFAULT 6)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_rec                RECORD;
    v_t_sin_contacto     INTERVAL;
    v_tiene_buffer_pend  BOOLEAN;
    v_estado_nuevo       modulo3.enum_estado_dispositivo;
    v_estado_actual      modulo3.enum_estado_dispositivo;
BEGIN
    -- Obtener la fila completa del estado actual del dispositivo
    SELECT edi.estado_actual,
           edi.fecha_ultimo_contacto,
           edi.id_ultimo_heardbeat
    INTO v_rec
    FROM modulo3.estados_dispositivos_iot edi
    WHERE edi.id_dispositivo_iot = p_id_dispositivo;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Dispositivo % no existe en estados_dispositivos_iot', p_id_dispositivo;
    END IF;

    v_estado_actual := v_rec.estado_actual;

    -- Si está en mantenimiento, no se modifica
    IF v_estado_actual = 'EN_MANTENIMIENTO'::modulo3.enum_estado_dispositivo THEN
        RETURN;
    END IF;

    -- Calcular tiempo sin contacto
    v_t_sin_contacto := NOW() - COALESCE(v_rec.fecha_ultimo_contacto, '1970-01-01'::TIMESTAMPTZ);

    -- Buffer pendiente según el último heartbeat del nodo (DB-03 / D10: el
    -- buffer vive en el Edge y su estado llega por heartbeat)
    SELECT COALESCE((
        SELECT h.datos_pendientes_buffer > 0
        FROM modulo3.heartbeats h
        WHERE h.id_dispositivo_iot = p_id_dispositivo
        ORDER BY h.fecha_recepcion DESC, h.id_heartbeat DESC
        LIMIT 1
    ), FALSE) INTO v_tiene_buffer_pend;

    -- Determinar nuevo estado según reglas de negocio
    IF v_t_sin_contacto <= INTERVAL '10 minutes' THEN        -- frecuencia de heartbeat típica
        v_estado_nuevo := 'ACTIVO'::modulo3.enum_estado_dispositivo;
    ELSIF v_tiene_buffer_pend THEN
        v_estado_nuevo := 'BUFFER_ACTIVO'::modulo3.enum_estado_dispositivo;
    ELSIF v_t_sin_contacto <= MAKE_INTERVAL(mins => p_margen_tolerancia_min) THEN
        v_estado_nuevo := 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo;
    ELSIF v_t_sin_contacto > MAKE_INTERVAL(hours => p_umbral_inactivo_horas) THEN
        v_estado_nuevo := 'INACTIVO'::modulo3.enum_estado_dispositivo;
    ELSE
        v_estado_nuevo := 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo;
    END IF;

    -- Actualizar si cambió
    IF v_estado_nuevo IS DISTINCT FROM v_estado_actual THEN
        UPDATE modulo3.estados_dispositivos_iot
        SET estado_actual              = v_estado_nuevo,
            tiempo_sin_contacto        = EXTRACT(EPOCH FROM v_t_sin_contacto)::INTEGER / 60,
            fecha_ultima_actualizacion = NOW()
        WHERE id_dispositivo_iot = p_id_dispositivo;
    END IF;
END;
$procedure$
'''
_EVENTO_EDGE_NUEVO = r'''
CREATE OR REPLACE PROCEDURE modulo3.sp_registrar_evento_edge(IN p_id_dispositivo integer, IN p_id_sensor integer, IN p_tipo_evento modulo3.enum_tipo_evento_edge, IN p_valor_evaluado numeric, IN p_umbral_min numeric, IN p_umbral_max numeric, IN p_id_regla_alerta integer DEFAULT NULL::integer, IN p_variables_involucradas json DEFAULT '[]'::json, IN p_origen_dato modulo3.enum_origen_dato DEFAULT 'TIEMPO_REAL'::modulo3.enum_origen_dato, IN p_estado_conectividad boolean DEFAULT true, IN p_metadatos jsonb DEFAULT '{}'::jsonb, INOUT p_id_evento integer DEFAULT NULL::integer, INOUT p_severidad modulo3.enum_buffer_nivel_severidad DEFAULT NULL::modulo3.enum_buffer_nivel_severidad)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_pct_desviacion   NUMERIC;
    v_fecha_cap        TIMESTAMPTZ := NOW();
    v_tipo_evento_edge modulo3.enum_eventos_edge_computing_tipo_evento;
BEGIN
    v_pct_desviacion := modulo3.fn_porcentaje_desviacion(
                            p_valor_evaluado, p_umbral_min, p_umbral_max);

    IF p_tipo_evento = 'NORMAL' OR v_pct_desviacion = 0 THEN
        p_severidad := 'LEVE';
    ELSIF v_pct_desviacion < 0 THEN
        p_severidad := 'LEVE';
    ELSE
        p_severidad := modulo3.fn_clasificar_severidad(v_pct_desviacion);
    END IF;

    -- fix: mapeo explícito entre los dos enums
    v_tipo_evento_edge := CASE p_tipo_evento
        WHEN 'NORMAL'               THEN 'DATOS_PROCESADOS'
        WHEN 'DESVIACION_SIMPLE'    THEN 'ALERTA_GENERADA'
        WHEN 'DESVIACION_COMPUESTA' THEN 'ALERTA_GENERADA'
        WHEN 'ERROR_CONFIGURACION'  THEN 'ERROR_PROCESAMIENTO'
        ELSE 'DATOS_PROCESADOS'
    END::modulo3.enum_eventos_edge_computing_tipo_evento;

    INSERT INTO modulo3.eventos_edge_computing (
        id_dispositivo_iot, id_sensor,
        tipo_evento, severidad,
        variables_involucradas, id_regla_alerta,
        valor_evaluado, umbral_min_aplicado, umbral_max_aplicado,
        desviacion_pct,
        fecha_captura, fecha_procesamiento,
        origen_dato, estado_conectividad,
        metadatos,
        enviado_backend, almacendado_buffer
    )
    VALUES (
        p_id_dispositivo, p_id_sensor,
        v_tipo_evento_edge,                        -- fix: ya no es un cast directo
        p_severidad,
        p_variables_involucradas, p_id_regla_alerta,
        p_valor_evaluado, p_umbral_min, p_umbral_max,
        v_pct_desviacion,
        v_fecha_cap, NOW(),
        p_origen_dato, p_estado_conectividad,
        p_metadatos,
        p_estado_conectividad,
        NOT p_estado_conectividad
    )
    RETURNING id_evento_edge_computing INTO p_id_evento;
END;
$procedure$
'''
_VW_DISPOSITIVO_OPERACIONAL_NUEVA = r'''
 SELECT d.id_dispositivo_iot,
    d.serial AS dispositivo_serial,
    d.descripcion AS dispositivo_nombre,
    d.es_activo AS dispositivo_activo,
    COALESCE(infra_sensor.id_infraestructura, infra_activo.id_infraestructura) AS id_infraestructura,
    i.nombre AS infraestructura,
    i.id_finca,
    f.nombre AS finca,
    COALESCE(edi.estado_actual::text,
        CASE
            WHEN d.es_activo THEN 'ACTIVO'::text
            ELSE 'INACTIVO'::text
        END) AS conexion,
    edi.fecha_ultimo_contacto,
    hb.fecha_recepcion AS fecha_ultimo_heartbeat,
    hb.nivel_bateria_pct,
    hb.calidad_senal_rssi,
    hb.calidad_senal_snr,
    hb.reloj_sincronizado,
    tx.estado_transmision_mqtt,
    tx.reintentos_mqtt,
    COALESCE(sensores.total_sensores, 0::bigint) AS total_sensores,
    COALESCE(edge.total_registros_buffer, 0::bigint) AS cantidad_registros_edge,
    COALESCE(edge.registros_evento_edge, 0::bigint) AS registros_evento_edge,
    COALESCE(edge.registros_pendientes, 0::bigint) AS registros_pendientes,
    COALESCE(edge.registros_confirmados, 0::bigint) AS registros_confirmados,
    COALESCE(edge.registros_error, 0::bigint) AS registros_error,
    COALESCE(edge.intentos_sincronizacion_total, 0::bigint) AS intentos_sincronizacion_total,
    COALESCE(edge.intentos_sincronizacion_max, 0) AS intentos_sincronizacion_max,
        CASE
            WHEN edge.ultimo_buffer_capturado IS NULL AND tel.ultimo_telemetria_capturada IS NULL THEN NULL::timestamp with time zone
            ELSE GREATEST(COALESCE(edge.ultimo_buffer_capturado, '-infinity'::timestamp with time zone), COALESCE(tel.ultimo_telemetria_capturada, '-infinity'::timestamp with time zone))
        END AS ultimo_dato_capturado,
        CASE
            WHEN edge.ultimo_buffer_capturado IS NULL AND tel.ultimo_telemetria_capturada IS NULL THEN NULL::numeric
            ELSE COALESCE(edge.ultimo_valor_buffer, tel.ultimo_valor_telemetria)
        END AS ultimo_valor_capturado,
    COALESCE(edge.horas_buffer_trabajadas, 0::numeric) AS capacidad_utilizada_horas_buffer
   FROM modulo9.dispositivos_iot d
     LEFT JOIN LATERAL ( SELECT count(*) AS total_sensores
           FROM modulo9.sensores s
          WHERE s.id_dispositivo_iot = d.id_dispositivo_iot) sensores ON true
     LEFT JOIN LATERAL ( SELECT a.id_infraestructura
           FROM modulo9.sensores_areas_asociadas a
          WHERE a.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY (a.fecha_finalizacion IS NULL) DESC, a.fecha_asociacion DESC, a.id_sensores_area_asociada DESC
         LIMIT 1) infra_sensor ON true
     LEFT JOIN LATERAL ( SELECT ab.id_infraestructura
           FROM modulo2.activos_biologicos ab
          WHERE ab.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY ab.fecha_creacion DESC, ab.id_activo_biologico DESC
         LIMIT 1) infra_activo ON true
     LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = COALESCE(infra_sensor.id_infraestructura, infra_activo.id_infraestructura)
     LEFT JOIN modulo9.fincas f ON f.id_finca = i.id_finca
     LEFT JOIN LATERAL ( SELECT e.estado_actual,
            e.fecha_ultimo_contacto
           FROM modulo3.estados_dispositivos_iot e
          WHERE e.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY e.fecha_ultima_actualizacion DESC, e.id_estado_dispositivo_iot DESC
         LIMIT 1) edi ON true
     LEFT JOIN LATERAL ( SELECT h.fecha_recepcion,
            h.nivel_bateria_pct,
            h.calidad_senal_rssi,
            h.calidad_senal_snr,
            h.reloj_sincronizado
           FROM modulo3.heartbeats h
          WHERE h.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY h.fecha_recepcion DESC, h.id_heartbeat DESC
         LIMIT 1) hb ON true
     LEFT JOIN LATERAL ( SELECT tm.estado::text AS estado_transmision_mqtt,
            tm.intentos AS reintentos_mqtt
           FROM modulo3.transmisiones_mqtt tm
          WHERE tm.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY tm.fecha_transmision DESC, tm.id_transmicion_mqqt DESC
         LIMIT 1) tx ON true
     LEFT JOIN LATERAL ( SELECT hb_buf.datos_pendientes_buffer::bigint AS total_registros_buffer,
            0::bigint AS registros_evento_edge,
            hb_buf.datos_pendientes_buffer::bigint AS registros_pendientes,
            0::bigint AS registros_confirmados,
            0::bigint AS registros_error,
            0::bigint AS intentos_sincronizacion_total,
            0 AS intentos_sincronizacion_max,
            NULL::timestamp with time zone AS ultimo_buffer_capturado,
            NULL::numeric AS ultimo_valor_buffer,
            0::numeric AS horas_buffer_trabajadas
           FROM ( SELECT h.datos_pendientes_buffer
                   FROM modulo3.heartbeats h
                  WHERE h.id_dispositivo_iot = d.id_dispositivo_iot
                  ORDER BY h.fecha_recepcion DESC, h.id_heartbeat DESC
                 LIMIT 1) hb_buf) edge ON true
     LEFT JOIN LATERAL ( SELECT max(t.timestamp_captura) AS ultimo_telemetria_capturada,
            (array_agg(COALESCE(t.valor_ajustado, t.valor_crudo) ORDER BY t.timestamp_captura DESC, t.id_telemetria DESC))[1] AS ultimo_valor_telemetria
           FROM modulo3.telemetrias t
          WHERE t.id_dispositivo_iot = d.id_dispositivo_iot) tel ON true;
'''
_VW_TELEMETRIA_CONTEXTUALIZADA_NUEVA = r'''
 SELECT t.id_telemetria,
    t.id_sensor,
    s.nombre AS nombre_sensor,
    s.categoria::text AS categoria_sensor,
    s.es_activo AS sensor_activo,
    t.id_dispositivo_iot,
    d.serial AS dispositivo_serial,
    d.descripcion AS dispositivo_nombre,
    d.es_activo AS dispositivo_activo,
    t.id_variable,
    va.nombre AS variable_ambiental,
    va.unidad AS unidad_variable,
    va.valor_fisico_min,
    va.valor_fisico_max,
    t.categoria_variable::text AS categoria_variable,
    t.unidad_medida,
    t.valor_crudo,
    t.valor_ajustado,
    COALESCE(t.valor_ajustado, t.valor_crudo) AS valor,
    t.calibrado,
    t.version_calibracion,
    t.parametros_calibracion,
    t.timestamp_captura,
    t.timestamp_envio,
    t.timestamp_procesamiento,
        CASE
            WHEN t.timestamp_envio IS NULL THEN NULL::bigint
            ELSE round(EXTRACT(epoch FROM t.timestamp_envio - t.timestamp_captura) * 1000::numeric)::bigint
        END AS latencia_transmision_ms,
        CASE
            WHEN t.latencia_procesamiento_ms IS NOT NULL THEN t.latencia_procesamiento_ms::bigint
            WHEN t.timestamp_envio IS NOT NULL THEN round(EXTRACT(epoch FROM t.timestamp_procesamiento - t.timestamp_envio) * 1000::numeric)::bigint
            ELSE round(EXTRACT(epoch FROM t.timestamp_procesamiento - t.timestamp_captura) * 1000::numeric)::bigint
        END AS latencia_procesamiento_ms,
    round(EXTRACT(epoch FROM t.timestamp_procesamiento - t.timestamp_captura) * 1000::numeric)::bigint AS latencia_total_ms,
    t.origen::text AS origen,
    t.estado_calidad::text AS estado_calidad,
    t.tipo_dato::text AS tipo_dato,
    t.valor_agregado,
    t.ventana_agregacion_min,
    t.latitud,
    t.longitud,
    t.metadatos,
    t.latencia_alta,
    t.frecuencia_anomala,
    t.posible_drift,
    t.dato_buferizado AS dato_bufferizado,
    t.dato_agredado_edge AS dato_agregado_edge,
    t.reloj_desincronizado,
    t.nivel_bateria_pct,
    t.calidad_senal_rssi,
    t.calidad_senal_snr,
    t.frecuencia_muestreo_min,
    t.estado_conectividad,
    vl.id_vinculacion_lectura,
    vl.modelo_manejo::text AS modelo_manejo,
    vl.estado_vinculacion::text AS estado_vinculacion,
    vl.mecanismo_vinculacion::text AS mecanismo_vinculacion,
    COALESCE(vl.id_infraestructura, saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura,
    i.nombre AS infraestructura,
    i.tipo::text AS tipo_infraestructura,
    i.id_finca,
    f.nombre AS finca,
    saa.punto_instalacion,
    vl.id_activo_biologico,
    ab.identificador AS identificador_activo,
    ab.tipo::text AS tipo_activo,
    eab.nombre AS estado_activo_biologico,
    esp.nombre AS especie_activo,
    edi.estado_actual::text AS estado_dispositivo,
    edi.fecha_ultimo_contacto,
    edi.tiempo_sin_contacto,
    edi.causa_primaria::text AS causa_inactividad,
    mqtt.estado_transmision_mqtt,
    mqtt.reintentos_mqtt,
    mqtt.gateway_id,
    COALESCE(buf.total_registros_buffer, 0::bigint) AS buffer_total_registros,
    COALESCE(buf.registros_pendientes, 0::bigint) AS buffer_registros_pendientes,
    COALESCE(buf.registros_confirmados, 0::bigint) AS buffer_registros_confirmados,
    buf.ultimo_dato_capturado AS buffer_ultimo_dato_capturado,
    COALESCE(buf.horas_buffer_trabajadas, 0::numeric) AS buffer_horas_trabajadas,
    COALESCE(buf.intentos_sincronizacion_total, 0::bigint) AS buffer_intentos_total,
    COALESCE(buf.intentos_sincronizacion_max, 0) AS buffer_intentos_max
   FROM modulo3.telemetrias t
     LEFT JOIN modulo9.sensores s ON s.id_sensores = t.id_sensor
     LEFT JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = t.id_dispositivo_iot
     LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
     LEFT JOIN LATERAL ( SELECT v.id_vinculacion_lectura,
            v.id_activo_biologico,
            v.id_infraestructura,
            v.modelo_manejo,
            v.estado_vinculacion,
            v.mecanismo_vinculacion
           FROM modulo3.vinculaciones_lecturas v
          WHERE v.id_telemetria = t.id_telemetria
          ORDER BY v.fecha_creacion DESC, v.id_vinculacion_lectura DESC
         LIMIT 1) vl ON true
     LEFT JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = vl.id_activo_biologico
     LEFT JOIN modulo2.estados_activos_biologicos eab ON eab.id_estado_activo_biologico = ab.id_estado
     LEFT JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
     LEFT JOIN LATERAL ( SELECT a.id_infraestructura,
            a.punto_instalacion
           FROM modulo9.sensores_areas_asociadas a
          WHERE a.id_sensor = t.id_sensor AND a.fecha_asociacion <= t.timestamp_captura AND (a.fecha_finalizacion IS NULL OR a.fecha_finalizacion > t.timestamp_captura)
          ORDER BY a.fecha_asociacion DESC, a.id_sensores_area_asociada DESC
         LIMIT 1) saa ON true
     LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = COALESCE(vl.id_infraestructura, saa.id_infraestructura, ab.id_infraestructura)
     LEFT JOIN modulo9.fincas f ON f.id_finca = i.id_finca
     LEFT JOIN LATERAL ( SELECT e.estado_actual,
            e.fecha_ultimo_contacto,
            e.tiempo_sin_contacto,
            e.causa_primaria
           FROM modulo3.estados_dispositivos_iot e
          WHERE e.id_dispositivo_iot = t.id_dispositivo_iot
          ORDER BY e.fecha_ultima_actualizacion DESC, e.id_estado_dispositivo_iot DESC
         LIMIT 1) edi ON true
     LEFT JOIN LATERAL ( SELECT tm.estado::text AS estado_transmision_mqtt,
            tm.intentos AS reintentos_mqtt,
            tm.gatway_id AS gateway_id
           FROM modulo3.transmisiones_mqtt tm
          WHERE tm.id_dispositivo_iot = t.id_dispositivo_iot AND tm.fecha_transmision <= t.timestamp_procesamiento
          ORDER BY tm.fecha_transmision DESC, tm.id_transmicion_mqqt DESC
         LIMIT 1) mqtt ON true
     LEFT JOIN LATERAL ( SELECT hb_buf.datos_pendientes_buffer::bigint AS total_registros_buffer,
            hb_buf.datos_pendientes_buffer::bigint AS registros_pendientes,
            0::bigint AS registros_confirmados,
            NULL::timestamp with time zone AS ultimo_dato_capturado,
            0::numeric AS horas_buffer_trabajadas,
            0::bigint AS intentos_sincronizacion_total,
            0 AS intentos_sincronizacion_max
           FROM ( SELECT h.datos_pendientes_buffer
                   FROM modulo3.heartbeats h
                  WHERE h.id_dispositivo_iot = t.id_dispositivo_iot
                  ORDER BY h.fecha_recepcion DESC, h.id_heartbeat DESC
                 LIMIT 1) hb_buf) buf ON true;
'''

# ── Definiciones anteriores (downgrade) ────────────────────────────────────
_CLASIFICAR_ANTES = r'''
CREATE OR REPLACE PROCEDURE modulo3.sp_clasificar_estado_dispositivo(IN p_id_dispositivo integer, IN p_margen_tolerancia_min integer DEFAULT 5, IN p_umbral_inactivo_horas integer DEFAULT 6)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_rec                RECORD;
    v_t_sin_contacto     INTERVAL;
    v_tiene_buffer_pend  BOOLEAN;
    v_estado_nuevo       modulo3.enum_estado_dispositivo;
    v_estado_actual      modulo3.enum_estado_dispositivo;
BEGIN
    -- Obtener la fila completa del estado actual del dispositivo
    SELECT edi.estado_actual,
           edi.fecha_ultimo_contacto,
           edi.id_ultimo_heardbeat
    INTO v_rec
    FROM modulo3.estados_dispositivos_iot edi
    WHERE edi.id_dispositivo_iot = p_id_dispositivo;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Dispositivo % no existe en estados_dispositivos_iot', p_id_dispositivo;
    END IF;

    v_estado_actual := v_rec.estado_actual;

    -- Si está en mantenimiento, no se modifica
    IF v_estado_actual = 'EN_MANTENIMIENTO'::modulo3.enum_estado_dispositivo THEN
        RETURN;
    END IF;

    -- Calcular tiempo sin contacto
    v_t_sin_contacto := NOW() - COALESCE(v_rec.fecha_ultimo_contacto, '1970-01-01'::TIMESTAMPTZ);

    -- Verificar existencia de buffers pendientes
    SELECT EXISTS (
        SELECT 1 FROM modulo3.buffers b
        WHERE b.id_dispositivo_iot = p_id_dispositivo
          AND b.estado_buffer IN ('PENDIENTE'::modulo3.enum_buffers_estado_buffer,
                                  'ERROR'::modulo3.enum_buffers_estado_buffer)
    ) INTO v_tiene_buffer_pend;

    -- Determinar nuevo estado según reglas de negocio
    IF v_t_sin_contacto <= INTERVAL '10 minutes' THEN        -- frecuencia de heartbeat típica
        v_estado_nuevo := 'ACTIVO'::modulo3.enum_estado_dispositivo;
    ELSIF v_tiene_buffer_pend THEN
        v_estado_nuevo := 'BUFFER_ACTIVO'::modulo3.enum_estado_dispositivo;
    ELSIF v_t_sin_contacto <= MAKE_INTERVAL(mins => p_margen_tolerancia_min) THEN
        v_estado_nuevo := 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo;
    ELSIF v_t_sin_contacto > MAKE_INTERVAL(hours => p_umbral_inactivo_horas) THEN
        v_estado_nuevo := 'INACTIVO'::modulo3.enum_estado_dispositivo;
    ELSE
        v_estado_nuevo := 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo;
    END IF;

    -- Actualizar si cambió
    IF v_estado_nuevo IS DISTINCT FROM v_estado_actual THEN
        UPDATE modulo3.estados_dispositivos_iot
        SET estado_actual              = v_estado_nuevo,
            tiempo_sin_contacto        = EXTRACT(EPOCH FROM v_t_sin_contacto)::INTEGER / 60,
            fecha_ultima_actualizacion = NOW()
        WHERE id_dispositivo_iot = p_id_dispositivo;
    END IF;
END;
$procedure$
'''
_EVENTO_EDGE_ANTES = r'''
CREATE OR REPLACE PROCEDURE modulo3.sp_registrar_evento_edge(IN p_id_dispositivo integer, IN p_id_sensor integer, IN p_tipo_evento modulo3.enum_tipo_evento_edge, IN p_valor_evaluado numeric, IN p_umbral_min numeric, IN p_umbral_max numeric, IN p_id_regla_alerta integer DEFAULT NULL::integer, IN p_variables_involucradas json DEFAULT '[]'::json, IN p_origen_dato modulo3.enum_origen_dato DEFAULT 'TIEMPO_REAL'::modulo3.enum_origen_dato, IN p_estado_conectividad boolean DEFAULT true, IN p_metadatos jsonb DEFAULT '{}'::jsonb, INOUT p_id_evento integer DEFAULT NULL::integer, INOUT p_severidad modulo3.enum_buffer_nivel_severidad DEFAULT NULL::modulo3.enum_buffer_nivel_severidad)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_pct_desviacion   NUMERIC;
    v_fecha_cap        TIMESTAMPTZ := NOW();
    v_tipo_evento_edge modulo3.enum_eventos_edge_computing_tipo_evento;
BEGIN
    v_pct_desviacion := modulo3.fn_porcentaje_desviacion(
                            p_valor_evaluado, p_umbral_min, p_umbral_max);

    IF p_tipo_evento = 'NORMAL' OR v_pct_desviacion = 0 THEN
        p_severidad := 'LEVE';
    ELSIF v_pct_desviacion < 0 THEN
        p_severidad := 'LEVE';
    ELSE
        p_severidad := modulo3.fn_clasificar_severidad(v_pct_desviacion);
    END IF;

    -- fix: mapeo explícito entre los dos enums
    v_tipo_evento_edge := CASE p_tipo_evento
        WHEN 'NORMAL'               THEN 'DATOS_PROCESADOS'
        WHEN 'DESVIACION_SIMPLE'    THEN 'ALERTA_GENERADA'
        WHEN 'DESVIACION_COMPUESTA' THEN 'ALERTA_GENERADA'
        WHEN 'ERROR_CONFIGURACION'  THEN 'ERROR_PROCESAMIENTO'
        ELSE 'DATOS_PROCESADOS'
    END::modulo3.enum_eventos_edge_computing_tipo_evento;

    INSERT INTO modulo3.eventos_edge_computing (
        id_dispositivo_iot, id_sensor,
        tipo_evento, severidad,
        variables_involucradas, id_regla_alerta,
        valor_evaluado, umbral_min_aplicado, umbral_max_aplicado,
        desviacion_pct,
        fecha_captura, fecha_procesamiento,
        origen_dato, estado_conectividad,
        metadatos,
        enviado_backend, almacendado_buffer
    )
    VALUES (
        p_id_dispositivo, p_id_sensor,
        v_tipo_evento_edge,                        -- fix: ya no es un cast directo
        p_severidad,
        p_variables_involucradas, p_id_regla_alerta,
        p_valor_evaluado, p_umbral_min, p_umbral_max,
        v_pct_desviacion,
        v_fecha_cap, NOW(),
        p_origen_dato, p_estado_conectividad,
        p_metadatos,
        p_estado_conectividad,
        NOT p_estado_conectividad
    )
    RETURNING id_evento_edge_computing INTO p_id_evento;

    IF NOT p_estado_conectividad THEN
        CALL modulo3.sp_registrar_en_buffer(
            p_id_dispositivo, p_id_sensor,
            'EVENTO_EDGE',
            json_build_object(
                'id_evento_edge', p_id_evento,
                'tipo', p_tipo_evento,
                'severidad', p_severidad,
                'valor', p_valor_evaluado)::JSON,
            v_fecha_cap,
            p_severidad
        );
    END IF;
END;
$procedure$
'''
_VW_DISPOSITIVO_OPERACIONAL_ANTES = r'''
 SELECT d.id_dispositivo_iot,
    d.serial AS dispositivo_serial,
    d.descripcion AS dispositivo_nombre,
    d.es_activo AS dispositivo_activo,
    COALESCE(infra_sensor.id_infraestructura, infra_activo.id_infraestructura) AS id_infraestructura,
    i.nombre AS infraestructura,
    i.id_finca,
    f.nombre AS finca,
    COALESCE(edi.estado_actual::text,
        CASE
            WHEN d.es_activo THEN 'ACTIVO'::text
            ELSE 'INACTIVO'::text
        END) AS conexion,
    edi.fecha_ultimo_contacto,
    hb.fecha_recepcion AS fecha_ultimo_heartbeat,
    hb.nivel_bateria_pct,
    hb.calidad_senal_rssi,
    hb.calidad_senal_snr,
    hb.reloj_sincronizado,
    tx.estado_transmision_mqtt,
    tx.reintentos_mqtt,
    COALESCE(sensores.total_sensores, 0::bigint) AS total_sensores,
    COALESCE(edge.total_registros_buffer, 0::bigint) AS cantidad_registros_edge,
    COALESCE(edge.registros_evento_edge, 0::bigint) AS registros_evento_edge,
    COALESCE(edge.registros_pendientes, 0::bigint) AS registros_pendientes,
    COALESCE(edge.registros_confirmados, 0::bigint) AS registros_confirmados,
    COALESCE(edge.registros_error, 0::bigint) AS registros_error,
    COALESCE(edge.intentos_sincronizacion_total, 0::bigint) AS intentos_sincronizacion_total,
    COALESCE(edge.intentos_sincronizacion_max, 0) AS intentos_sincronizacion_max,
        CASE
            WHEN edge.ultimo_buffer_capturado IS NULL AND tel.ultimo_telemetria_capturada IS NULL THEN NULL::timestamp with time zone
            ELSE GREATEST(COALESCE(edge.ultimo_buffer_capturado, '-infinity'::timestamp with time zone), COALESCE(tel.ultimo_telemetria_capturada, '-infinity'::timestamp with time zone))
        END AS ultimo_dato_capturado,
        CASE
            WHEN edge.ultimo_buffer_capturado IS NULL AND tel.ultimo_telemetria_capturada IS NULL THEN NULL::numeric
            ELSE COALESCE(edge.ultimo_valor_buffer, tel.ultimo_valor_telemetria)
        END AS ultimo_valor_capturado,
    COALESCE(edge.horas_buffer_trabajadas, 0::numeric) AS capacidad_utilizada_horas_buffer
   FROM modulo9.dispositivos_iot d
     LEFT JOIN LATERAL ( SELECT count(*) AS total_sensores
           FROM modulo9.sensores s
          WHERE s.id_dispositivo_iot = d.id_dispositivo_iot) sensores ON true
     LEFT JOIN LATERAL ( SELECT a.id_infraestructura
           FROM modulo9.sensores_areas_asociadas a
          WHERE a.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY (a.fecha_finalizacion IS NULL) DESC, a.fecha_asociacion DESC, a.id_sensores_area_asociada DESC
         LIMIT 1) infra_sensor ON true
     LEFT JOIN LATERAL ( SELECT ab.id_infraestructura
           FROM modulo2.activos_biologicos ab
          WHERE ab.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY ab.fecha_creacion DESC, ab.id_activo_biologico DESC
         LIMIT 1) infra_activo ON true
     LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = COALESCE(infra_sensor.id_infraestructura, infra_activo.id_infraestructura)
     LEFT JOIN modulo9.fincas f ON f.id_finca = i.id_finca
     LEFT JOIN LATERAL ( SELECT e.estado_actual,
            e.fecha_ultimo_contacto
           FROM modulo3.estados_dispositivos_iot e
          WHERE e.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY e.fecha_ultima_actualizacion DESC, e.id_estado_dispositivo_iot DESC
         LIMIT 1) edi ON true
     LEFT JOIN LATERAL ( SELECT h.fecha_recepcion,
            h.nivel_bateria_pct,
            h.calidad_senal_rssi,
            h.calidad_senal_snr,
            h.reloj_sincronizado
           FROM modulo3.heartbeats h
          WHERE h.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY h.fecha_recepcion DESC, h.id_heartbeat DESC
         LIMIT 1) hb ON true
     LEFT JOIN LATERAL ( SELECT tm.estado::text AS estado_transmision_mqtt,
            tm.intentos AS reintentos_mqtt
           FROM modulo3.transmisiones_mqtt tm
          WHERE tm.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY tm.fecha_transmision DESC, tm.id_transmicion_mqqt DESC
         LIMIT 1) tx ON true
     LEFT JOIN LATERAL ( SELECT count(*) AS total_registros_buffer,
            count(*) FILTER (WHERE b.tipo_dato::text = 'EVENTO_EDGE'::text) AS registros_evento_edge,
            count(*) FILTER (WHERE b.estado_buffer::text = ANY (ARRAY['PENDIENTE'::text, 'ERROR'::text])) AS registros_pendientes,
            count(*) FILTER (WHERE b.estado_buffer::text = 'CONFIRMADO'::text) AS registros_confirmados,
            count(*) FILTER (WHERE b.estado_buffer::text = 'ERROR'::text) AS registros_error,
            COALESCE(sum(b.intentos_envio), 0::bigint) AS intentos_sincronizacion_total,
            COALESCE(max(b.intentos_envio), 0) AS intentos_sincronizacion_max,
            max(b.fecha_captura) AS ultimo_buffer_capturado,
            (array_agg((b.payload_raw ->> 'valor'::text)::numeric ORDER BY b.fecha_captura DESC, b.id_buffer DESC) FILTER (WHERE (b.payload_raw ->> 'valor'::text) ~ '^-?[0-9]+(\.[0-9]+)?$'::text))[1] AS ultimo_valor_buffer,
            COALESCE(round(EXTRACT(epoch FROM max(b.fecha_captura) - min(b.fecha_captura)) / 3600.0, 2), 0::numeric) AS horas_buffer_trabajadas
           FROM modulo3.buffers b
          WHERE b.id_dispositivo_iot = d.id_dispositivo_iot) edge ON true
     LEFT JOIN LATERAL ( SELECT max(t.timestamp_captura) AS ultimo_telemetria_capturada,
            (array_agg(COALESCE(t.valor_ajustado, t.valor_crudo) ORDER BY t.timestamp_captura DESC, t.id_telemetria DESC))[1] AS ultimo_valor_telemetria
           FROM modulo3.telemetrias t
          WHERE t.id_dispositivo_iot = d.id_dispositivo_iot) tel ON true;
'''
_VW_TELEMETRIA_CONTEXTUALIZADA_ANTES = r'''
 SELECT t.id_telemetria,
    t.id_sensor,
    s.nombre AS nombre_sensor,
    s.categoria::text AS categoria_sensor,
    s.es_activo AS sensor_activo,
    t.id_dispositivo_iot,
    d.serial AS dispositivo_serial,
    d.descripcion AS dispositivo_nombre,
    d.es_activo AS dispositivo_activo,
    t.id_variable,
    va.nombre AS variable_ambiental,
    va.unidad AS unidad_variable,
    va.valor_fisico_min,
    va.valor_fisico_max,
    t.categoria_variable::text AS categoria_variable,
    t.unidad_medida,
    t.valor_crudo,
    t.valor_ajustado,
    COALESCE(t.valor_ajustado, t.valor_crudo) AS valor,
    t.calibrado,
    t.version_calibracion,
    t.parametros_calibracion,
    t.timestamp_captura,
    t.timestamp_envio,
    t.timestamp_procesamiento,
        CASE
            WHEN t.timestamp_envio IS NULL THEN NULL::bigint
            ELSE round(EXTRACT(epoch FROM t.timestamp_envio - t.timestamp_captura) * 1000::numeric)::bigint
        END AS latencia_transmision_ms,
        CASE
            WHEN t.latencia_procesamiento_ms IS NOT NULL THEN t.latencia_procesamiento_ms::bigint
            WHEN t.timestamp_envio IS NOT NULL THEN round(EXTRACT(epoch FROM t.timestamp_procesamiento - t.timestamp_envio) * 1000::numeric)::bigint
            ELSE round(EXTRACT(epoch FROM t.timestamp_procesamiento - t.timestamp_captura) * 1000::numeric)::bigint
        END AS latencia_procesamiento_ms,
    round(EXTRACT(epoch FROM t.timestamp_procesamiento - t.timestamp_captura) * 1000::numeric)::bigint AS latencia_total_ms,
    t.origen::text AS origen,
    t.estado_calidad::text AS estado_calidad,
    t.tipo_dato::text AS tipo_dato,
    t.valor_agregado,
    t.ventana_agregacion_min,
    t.latitud,
    t.longitud,
    t.metadatos,
    t.latencia_alta,
    t.frecuencia_anomala,
    t.posible_drift,
    t.dato_buferizado AS dato_bufferizado,
    t.dato_agredado_edge AS dato_agregado_edge,
    t.reloj_desincronizado,
    t.nivel_bateria_pct,
    t.calidad_senal_rssi,
    t.calidad_senal_snr,
    t.frecuencia_muestreo_min,
    t.estado_conectividad,
    vl.id_vinculacion_lectura,
    vl.modelo_manejo::text AS modelo_manejo,
    vl.estado_vinculacion::text AS estado_vinculacion,
    vl.mecanismo_vinculacion::text AS mecanismo_vinculacion,
    COALESCE(vl.id_infraestructura, saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura,
    i.nombre AS infraestructura,
    i.tipo::text AS tipo_infraestructura,
    i.id_finca,
    f.nombre AS finca,
    saa.punto_instalacion,
    vl.id_activo_biologico,
    ab.identificador AS identificador_activo,
    ab.tipo::text AS tipo_activo,
    eab.nombre AS estado_activo_biologico,
    esp.nombre AS especie_activo,
    edi.estado_actual::text AS estado_dispositivo,
    edi.fecha_ultimo_contacto,
    edi.tiempo_sin_contacto,
    edi.causa_primaria::text AS causa_inactividad,
    mqtt.estado_transmision_mqtt,
    mqtt.reintentos_mqtt,
    mqtt.gateway_id,
    COALESCE(buf.total_registros_buffer, 0::bigint) AS buffer_total_registros,
    COALESCE(buf.registros_pendientes, 0::bigint) AS buffer_registros_pendientes,
    COALESCE(buf.registros_confirmados, 0::bigint) AS buffer_registros_confirmados,
    buf.ultimo_dato_capturado AS buffer_ultimo_dato_capturado,
    COALESCE(buf.horas_buffer_trabajadas, 0::numeric) AS buffer_horas_trabajadas,
    COALESCE(buf.intentos_sincronizacion_total, 0::bigint) AS buffer_intentos_total,
    COALESCE(buf.intentos_sincronizacion_max, 0) AS buffer_intentos_max
   FROM modulo3.telemetrias t
     LEFT JOIN modulo9.sensores s ON s.id_sensores = t.id_sensor
     LEFT JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = t.id_dispositivo_iot
     LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
     LEFT JOIN LATERAL ( SELECT v.id_vinculacion_lectura,
            v.id_activo_biologico,
            v.id_infraestructura,
            v.modelo_manejo,
            v.estado_vinculacion,
            v.mecanismo_vinculacion
           FROM modulo3.vinculaciones_lecturas v
          WHERE v.id_telemetria = t.id_telemetria
          ORDER BY v.fecha_creacion DESC, v.id_vinculacion_lectura DESC
         LIMIT 1) vl ON true
     LEFT JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = vl.id_activo_biologico
     LEFT JOIN modulo2.estados_activos_biologicos eab ON eab.id_estado_activo_biologico = ab.id_estado
     LEFT JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
     LEFT JOIN LATERAL ( SELECT a.id_infraestructura,
            a.punto_instalacion
           FROM modulo9.sensores_areas_asociadas a
          WHERE a.id_sensor = t.id_sensor AND a.fecha_asociacion <= t.timestamp_captura AND (a.fecha_finalizacion IS NULL OR a.fecha_finalizacion > t.timestamp_captura)
          ORDER BY a.fecha_asociacion DESC, a.id_sensores_area_asociada DESC
         LIMIT 1) saa ON true
     LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = COALESCE(vl.id_infraestructura, saa.id_infraestructura, ab.id_infraestructura)
     LEFT JOIN modulo9.fincas f ON f.id_finca = i.id_finca
     LEFT JOIN LATERAL ( SELECT e.estado_actual,
            e.fecha_ultimo_contacto,
            e.tiempo_sin_contacto,
            e.causa_primaria
           FROM modulo3.estados_dispositivos_iot e
          WHERE e.id_dispositivo_iot = t.id_dispositivo_iot
          ORDER BY e.fecha_ultima_actualizacion DESC, e.id_estado_dispositivo_iot DESC
         LIMIT 1) edi ON true
     LEFT JOIN LATERAL ( SELECT tm.estado::text AS estado_transmision_mqtt,
            tm.intentos AS reintentos_mqtt,
            tm.gatway_id AS gateway_id
           FROM modulo3.transmisiones_mqtt tm
          WHERE tm.id_dispositivo_iot = t.id_dispositivo_iot AND tm.fecha_transmision <= t.timestamp_procesamiento
          ORDER BY tm.fecha_transmision DESC, tm.id_transmicion_mqqt DESC
         LIMIT 1) mqtt ON true
     LEFT JOIN LATERAL ( SELECT count(*) AS total_registros_buffer,
            count(*) FILTER (WHERE b.estado_buffer::text = ANY (ARRAY['PENDIENTE'::text, 'ERROR'::text])) AS registros_pendientes,
            count(*) FILTER (WHERE b.estado_buffer::text = 'CONFIRMADO'::text) AS registros_confirmados,
            max(b.fecha_captura) AS ultimo_dato_capturado,
            COALESCE(round(EXTRACT(epoch FROM max(b.fecha_captura) - min(b.fecha_captura)) / 3600.0, 2), 0::numeric) AS horas_buffer_trabajadas,
            COALESCE(sum(b.intentos_envio), 0::bigint) AS intentos_sincronizacion_total,
            COALESCE(max(b.intentos_envio), 0) AS intentos_sincronizacion_max
           FROM modulo3.buffers b
          WHERE b.id_dispositivo_iot = t.id_dispositivo_iot) buf ON true;
'''
_ENUMS_BUFFER = r'''
CREATE TYPE modulo3.enum_buffers_estado_buffer AS ENUM ('PENDIENTE', 'ENVIADO', 'CONFIRMADO', 'ERROR');
CREATE TYPE modulo3.enum_buffers_politica_buffer AS ENUM ('POLITICA_RECHAZO', 'POLITICA_SOBRESCRITURA');
'''
_FUNCIONES_TRIGGER = [
r'''
CREATE OR REPLACE FUNCTION modulo3.fn_buffer_solo_delete_confirmado()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF OLD.estado_buffer IS DISTINCT FROM 'CONFIRMADO'::modulo3.enum_buffers_estado_buffer THEN
        RAISE EXCEPTION
            'RF-54 [INTEGRIDAD]: Solo se eliminan buffers CONFIRMADOS. id_buffer=% estado=%',
            OLD.id_buffer, OLD.estado_buffer
            USING ERRCODE = 'P0003';
    END IF;
    RETURN OLD;
END;
$function$
''',
r'''
CREATE OR REPLACE FUNCTION modulo3.fn_buffer_marcar_sincronizacion()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.estado_buffer = 'CONFIRMADO'::modulo3.enum_buffers_estado_buffer
       AND OLD.estado_buffer <> 'CONFIRMADO'::modulo3.enum_buffers_estado_buffer
    THEN
        NEW.fecha_sincornizacion := now();
    END IF;

    IF NEW.estado_buffer = 'ENVIADO'::modulo3.enum_buffers_estado_buffer
       AND OLD.estado_buffer IN (
           'PENDIENTE'::modulo3.enum_buffers_estado_buffer,
           'ERROR'::modulo3.enum_buffers_estado_buffer)
    THEN
        NEW.intentos_envio := OLD.intentos_envio + 1;
        NEW.ultimo_intento := now();
    END IF;
    RETURN NEW;
END;
$function$
''',
r'''
CREATE OR REPLACE FUNCTION modulo3.fn_buffer_dato_inmutable()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF OLD.payload_raw::text  <> NEW.payload_raw::text OR
       OLD.checksum_dato      <> NEW.checksum_dato     OR
       OLD.fecha_captura      <> NEW.fecha_captura     OR
       OLD.buffer_sequence_id <> NEW.buffer_sequence_id
    THEN
        RAISE EXCEPTION
            'RF-54 [INMUTABILIDAD]: payload_raw/checksum/fecha_captura/sequence_id son inmutables. id_buffer=%',
            OLD.id_buffer USING ERRCODE = 'P0004';
    END IF;
    RETURN NEW;
END;
$function$
''',
]
_TABLA_BUFFERS = r'''
CREATE TABLE modulo3.buffers (
    id_buffer integer NOT NULL,
    id_dispositivo_iot integer NOT NULL,
    id_sensor integer NOT NULL,
    buffer_sequence_id bigint NOT NULL,
    tipo_dato modulo3.enum_telemetria_tipo_dato DEFAULT 'CRUDO'::modulo3.enum_telemetria_tipo_dato NOT NULL,
    nivel_severidad modulo3.enum_buffer_nivel_severidad,
    id_evento_edge integer,
    payload_raw json NOT NULL,
    checksum_dato character varying(64) NOT NULL,
    fecha_captura timestamp with time zone NOT NULL,
    fecha_procesamiento_edge timestamp with time zone,
    fecha_creacion timestamp with time zone DEFAULT now() NOT NULL,
    fecha_sincornizacion timestamp with time zone,
    estado_buffer modulo3.enum_buffers_estado_buffer DEFAULT 'PENDIENTE'::modulo3.enum_buffers_estado_buffer,
    intentos_envio integer DEFAULT 0 NOT NULL,
    ultimo_intento timestamp with time zone,
    error_ultimo_intento timestamp with time zone,
    politica_aplicada modulo3.enum_buffers_politica_buffer,
    estado_conectividad_captura boolean,
    CONSTRAINT chk_buffer_severidad CHECK (((tipo_dato = 'EVENTO_EDGE'::modulo3.enum_telemetria_tipo_dato) OR (nivel_severidad IS NULL)))
);

COMMENT ON TABLE modulo3.buffers IS 'RF-54: Buffer de persistencia local para datos en modo offline. Garantiza orden FIFO mediante buffer_sequence_id. Un registro se elimina SOLO cuando estado_buffer = CONFIRMADO (confirmación explícita del backend).';

CREATE SEQUENCE modulo3.buffers_id_buffer_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE modulo3.buffers_id_buffer_seq OWNED BY modulo3.buffers.id_buffer;

ALTER TABLE ONLY modulo3.buffers ALTER COLUMN id_buffer SET DEFAULT nextval('modulo3.buffers_id_buffer_seq'::regclass);

ALTER TABLE ONLY modulo3.buffers
    ADD CONSTRAINT buffers_pkey PRIMARY KEY (id_buffer);

ALTER TABLE ONLY modulo3.buffers
    ADD CONSTRAINT uq_buffer_device_sensor_captura UNIQUE (id_dispositivo_iot, id_sensor, fecha_captura);

CREATE INDEX idx_buffer_dispositivo_secuencia ON modulo3.buffers USING btree (id_dispositivo_iot, buffer_sequence_id);

CREATE INDEX idx_buffer_estado ON modulo3.buffers USING btree (estado_buffer, id_dispositivo_iot);

CREATE INDEX idx_buffer_pendientes ON modulo3.buffers USING btree (id_dispositivo_iot, fecha_captura) WHERE (estado_buffer = ANY (ARRAY['PENDIENTE'::modulo3.enum_buffers_estado_buffer, 'ERROR'::modulo3.enum_buffers_estado_buffer]));




ALTER TABLE ONLY modulo3.buffers
    ADD CONSTRAINT fk_dispositovo_id FOREIGN KEY (id_dispositivo_iot) REFERENCES modulo9.dispositivos_iot(id_dispositivo_iot);

ALTER TABLE ONLY modulo3.buffers
    ADD CONSTRAINT fk_sensor_id FOREIGN KEY (id_sensor) REFERENCES modulo9.sensores(id_sensores);
'''
_TRIGGERS_BUFFERS = r'''
CREATE TRIGGER trg_rf54_01_delete_solo_confirmado BEFORE DELETE ON modulo3.buffers FOR EACH ROW EXECUTE FUNCTION modulo3.fn_buffer_solo_delete_confirmado();
CREATE TRIGGER trg_rf54_02_sincronizacion BEFORE UPDATE ON modulo3.buffers FOR EACH ROW EXECUTE FUNCTION modulo3.fn_buffer_marcar_sincronizacion();
CREATE TRIGGER trg_rf54_03_dato_inmutable BEFORE UPDATE ON modulo3.buffers FOR EACH ROW EXECUTE FUNCTION modulo3.fn_buffer_dato_inmutable();
'''
# (definición, firma, comentario)
_PROCEDIMIENTOS_BUFFER = [
    (r'''
CREATE OR REPLACE PROCEDURE modulo3.sp_registrar_en_buffer(IN p_id_dispositivo integer, IN p_id_sensor integer, IN p_tipo_dato modulo3.enum_telemetria_tipo_dato, IN p_payload_raw json, IN p_fecha_captura timestamp with time zone, IN p_nivel_severidad modulo3.enum_buffer_nivel_severidad DEFAULT NULL::modulo3.enum_buffer_nivel_severidad, IN p_id_evento_edge integer DEFAULT NULL::integer, INOUT p_id_buffer integer DEFAULT NULL::integer, INOUT p_estado_resultado text DEFAULT NULL::text)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_max_seq  BIGINT;
    v_checksum VARCHAR(64);
BEGIN
    SELECT COALESCE(MAX(buffer_sequence_id), 0) + 1
    INTO v_max_seq
    FROM modulo3.buffers
    WHERE id_dispositivo_iot = p_id_dispositivo;   -- fix: era id_dispositivo

    v_checksum := md5(p_payload_raw::TEXT);

    INSERT INTO modulo3.buffers (
        id_dispositivo_iot, id_sensor,             -- fix: era id_dispositivo
        buffer_sequence_id, tipo_dato,
        nivel_severidad, id_evento_edge,
        payload_raw, checksum_dato,
        fecha_captura, fecha_creacion,
        estado_buffer, intentos_envio
    ) VALUES (
        p_id_dispositivo, p_id_sensor,
        v_max_seq, p_tipo_dato,
        p_nivel_severidad, p_id_evento_edge,
        p_payload_raw, v_checksum,
        p_fecha_captura, NOW(),
        'PENDIENTE', 0
    )
    RETURNING id_buffer INTO p_id_buffer;

    p_estado_resultado := 'ALMACENADO';

EXCEPTION WHEN OTHERS THEN
    p_estado_resultado := 'ERROR: ' || SQLERRM;
    RAISE WARNING '[sp_registrar_en_buffer] %', SQLERRM;
END;
$procedure$
''',
     'modulo3.sp_registrar_en_buffer(integer,integer,modulo3.enum_telemetria_tipo_dato,json,timestamp with time zone,modulo3.enum_buffer_nivel_severidad,integer,integer,text)',
     'RF-54: Buffer FIFO con checksum. [CORREGIDO: id_dispositivo_iot]'),
    (r'''
CREATE OR REPLACE PROCEDURE modulo3.sp_reintentar_buffer(IN p_id_dispositivo integer, IN p_max_reintentos integer DEFAULT 5)
 LANGUAGE plpgsql
AS $procedure$
BEGIN
    UPDATE modulo3.buffers
    SET estado_buffer        = 'ERROR',
        error_ultimo_intento = NOW()
    WHERE id_dispositivo_iot = p_id_dispositivo    -- fix: era id_dispositivo
      AND estado_buffer      = 'ENVIADO'
      AND intentos_envio     >= p_max_reintentos;

    UPDATE modulo3.buffers
    SET estado_buffer  = 'PENDIENTE',
        ultimo_intento = NOW(),
        intentos_envio = intentos_envio + 1
    WHERE id_dispositivo_iot = p_id_dispositivo    -- fix: era id_dispositivo
      AND estado_buffer      = 'ENVIADO'
      AND intentos_envio     < p_max_reintentos;
END;
$procedure$
''',
     'modulo3.sp_reintentar_buffer(integer,integer)',
     'RF-54: Reintentos de buffer. [CORREGIDO: id_dispositivo_iot]'),
    (r'''
CREATE OR REPLACE PROCEDURE modulo3.sp_sincronizar_buffer_lote(IN p_batch_size integer DEFAULT 100, IN p_max_reintentos integer DEFAULT 5)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    rec_buffer          RECORD;
    v_intentos          INTEGER;
    v_duplicado         BOOLEAN;
    vid_telemetria      INTEGER;
    v_estado_calidad    modulo3.enum_telemetria_estado_calidad;
    v_mensaje           TEXT;
BEGIN
    FOR rec_buffer IN
        SELECT b.id_buffer,
               b.id_dispositivo_iot,
               b.id_sensor,
               b.payload_raw,
               b.fecha_captura,
               b.intentos_envio,
               b.ultimo_intento,
               b.tipo_dato,
               b.nivel_severidad
        FROM modulo3.buffers b
        WHERE b.estado_buffer IN ('PENDIENTE'::modulo3.enum_buffers_estado_buffer,
                                  'ERROR'::modulo3.enum_buffers_estado_buffer)
          AND b.intentos_envio < p_max_reintentos
        ORDER BY b.fecha_captura ASC
        LIMIT p_batch_size
        FOR UPDATE OF b SKIP LOCKED
    LOOP
        -- Resolver duplicados con telemetrías
        SELECT EXISTS (
            SELECT 1 FROM modulo3.telemetrias t
            WHERE t.id_sensor = rec_buffer.id_sensor
              AND t.timestamp_captura = rec_buffer.fecha_captura
        ) INTO v_duplicado;

        IF v_duplicado THEN
            UPDATE modulo3.buffers
            SET estado_buffer        = 'CONFIRMADO'::modulo3.enum_buffers_estado_buffer,
                fecha_sincornizacion = NOW()
            WHERE id_buffer = rec_buffer.id_buffer;
            CONTINUE;
        END IF;

        -- Llamada completa a fn_ingesta_telemetria (todos los parámetros)
        SELECT id_telemetria, estado_calidad, mensaje
        INTO vid_telemetria, v_estado_calidad, v_mensaje
        FROM modulo3.fn_ingesta_telemetria(
            p_id_dispositivo      => rec_buffer.id_dispositivo_iot,
            p_id_sensor           => rec_buffer.id_sensor,
            p_id_variable         => (rec_buffer.payload_raw->>'id_variable')::INTEGER,
            p_valor_crudo         => (rec_buffer.payload_raw->>'valor_crudo')::NUMERIC,
            p_unidad              => rec_buffer.payload_raw->>'unidad',
            p_timestamp_captura   => rec_buffer.fecha_captura,
            p_timestamp_envio     => rec_buffer.fecha_captura,
            p_origen              => 'BUFFER_LOCAL'::modulo3.enum_telemetria_origen,
            p_categoria_variable  => 'AMBIENTAL'::modulo3.enum_telemetria_categoria_variable,
            p_tipo_dato           => rec_buffer.tipo_dato,
            p_valor_agregado      => FALSE,
            p_ventana_agregacion  => NULL,
            p_latitud             => NULL,
            p_longitud            => NULL,
            p_nivel_bateria       => NULL,
            p_calidad_rssi        => NULL,
            p_calidad_snr         => NULL,
            p_estado_conectividad => FALSE,          -- buffer local → sin conectividad
            p_metadatos           => COALESCE((rec_buffer.payload_raw->>'metadatos')::JSONB, '{}'::JSONB)
        );

        -- Evaluar resultado
        IF vid_telemetria IS NOT NULL THEN
            UPDATE modulo3.buffers
            SET estado_buffer        = 'CONFIRMADO'::modulo3.enum_buffers_estado_buffer,
                fecha_sincornizacion = NOW(),
                intentos_envio       = rec_buffer.intentos_envio + 1,
                ultimo_intento       = NOW()
            WHERE id_buffer = rec_buffer.id_buffer;
        ELSE
            UPDATE modulo3.buffers
            SET intentos_envio       = rec_buffer.intentos_envio + 1,
                ultimo_intento       = NOW(),
                error_ultimo_intento = NOW(),
                estado_buffer        = CASE
                    WHEN rec_buffer.intentos_envio + 1 >= p_max_reintentos THEN
                        'ERROR'::modulo3.enum_buffers_estado_buffer
                    ELSE
                        'PENDIENTE'::modulo3.enum_buffers_estado_buffer
                END
            WHERE id_buffer = rec_buffer.id_buffer;
        END IF;
    END LOOP;
END;
$procedure$
''',
     'modulo3.sp_sincronizar_buffer_lote(integer,integer)',
     None),
    (r'''
CREATE OR REPLACE PROCEDURE modulo3.sp_confirmar_sincronizacion_buffer(IN p_id_buffer integer)
 LANGUAGE plpgsql
AS $procedure$
BEGIN
    UPDATE modulo3.buffers
    SET estado_buffer          = 'CONFIRMADO',
        fecha_sincornizacion   = NOW()
    WHERE id_buffer = p_id_buffer
      AND estado_buffer IN ('ENVIADO','PENDIENTE');

    IF NOT FOUND THEN
        RAISE WARNING 'Buffer id=% no encontrado o ya confirmado.', p_id_buffer;
    END IF;
END;
$procedure$
''',
     'modulo3.sp_confirmar_sincronizacion_buffer(integer)',
     'RF-54: Marca un registro de buffer como CONFIRMADO tras ACK del backend. Solo libera el dato tras confirmación explícita (CA-6).'),
]
_COMENTARIO_EVENTO_EDGE = 'RF-55: Evento Edge con severidad. [CORREGIDO: mapeo enum tipo_evento]'


def _comentar_procedimiento(firma: str, comentario: str | None) -> None:
    if comentario:
        op.execute(f"COMMENT ON PROCEDURE {firma} IS " + "'" + comentario.replace("'", "''") + "'")


def upgrade() -> None:
    # 1. Lo que referenciaba la tabla deja de hacerlo.
    op.execute("CREATE OR REPLACE VIEW modulo3.vw_m03_dispositivo_operacional AS\n" + _VW_DISPOSITIVO_OPERACIONAL_NUEVA)
    op.execute("CREATE OR REPLACE VIEW modulo3.vw_m03_telemetria_contextualizada AS\n" + _VW_TELEMETRIA_CONTEXTUALIZADA_NUEVA)
    op.execute(_CLASIFICAR_NUEVO)
    op.execute(_EVENTO_EDGE_NUEVO)

    # 2. Procedimientos, tabla (arrastra secuencia, índices y triggers),
    #    funciones de trigger y enums propios de la tabla.
    for _definicion, firma, _comentario in _PROCEDIMIENTOS_BUFFER:
        op.execute(f"DROP PROCEDURE {firma}")
    op.execute("DROP TABLE modulo3.buffers")
    op.execute(
        """
        DROP FUNCTION modulo3.fn_buffer_solo_delete_confirmado();
        DROP FUNCTION modulo3.fn_buffer_marcar_sincronizacion();
        DROP FUNCTION modulo3.fn_buffer_dato_inmutable();
        DROP TYPE modulo3.enum_buffers_estado_buffer;
        DROP TYPE modulo3.enum_buffers_politica_buffer;
        """
    )

    # 3. Subtipos de alerta técnica de DEV-11.
    for valor in _ALERTA_TECNICA_NUEVOS:
        op.execute(f"ALTER TYPE modulo3.enum_tipo_alerta_tecnica ADD VALUE IF NOT EXISTS '{valor}'")


def downgrade() -> None:
    # ALTER TYPE ... DROP VALUE no existe. Ninguna columna ni firma usa el enum
    # (se verifica antes de tocarlo), así que se recrea con los valores previos.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_depend
                WHERE refobjid = 'modulo3.enum_tipo_alerta_tecnica'::regtype
                  AND deptype = 'n'
            ) THEN
                RAISE EXCEPTION 'enum_tipo_alerta_tecnica ya tiene dependencias; el downgrade no puede quitarle valores';
            END IF;
        END $$;
        """
    )
    op.execute("DROP TYPE modulo3.enum_tipo_alerta_tecnica")
    op.execute(
        "CREATE TYPE modulo3.enum_tipo_alerta_tecnica AS ENUM ("
        + ", ".join("'" + v + "'" for v in _ALERTA_TECNICA_ANTES)
        + ")"
    )

    op.execute(_ENUMS_BUFFER)
    for definicion in _FUNCIONES_TRIGGER:
        op.execute(definicion)
    op.execute(_TABLA_BUFFERS)
    op.execute(_TRIGGERS_BUFFERS)
    op.execute(
        "COMMENT ON TABLE modulo3.buffers IS "
        + "'" + 'RF-54: Buffer de persistencia local para datos en modo offline. Garantiza orden FIFO mediante buffer_sequence_id. Un registro se elimina SOLO cuando estado_buffer = CONFIRMADO (confirmación explícita del backend).'.replace("'", "''") + "'"
    )
    for definicion, firma, comentario in _PROCEDIMIENTOS_BUFFER:
        op.execute(definicion)
        _comentar_procedimiento(firma, comentario)

    op.execute(_CLASIFICAR_ANTES)
    op.execute(_EVENTO_EDGE_ANTES)
    op.execute("CREATE OR REPLACE VIEW modulo3.vw_m03_dispositivo_operacional AS\n" + _VW_DISPOSITIVO_OPERACIONAL_ANTES)
    op.execute("CREATE OR REPLACE VIEW modulo3.vw_m03_telemetria_contextualizada AS\n" + _VW_TELEMETRIA_CONTEXTUALIZADA_ANTES)
