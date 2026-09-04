"""RF20 catalogo administrable de tipos de area

Revision ID: 2dbb6d44046f
Revises: b5d1e0c93a77
Create Date: 2026-09-04 08:00:00.000000

RF-20 / #1668 — Catálogo tipo_area extensible, no hardcodeado.

Se reemplaza el ENUM modulo9.enum_tipo_infraestructura por VARCHAR(30)
para permitir que el catálogo de tipos de área sea administrable.

Antes de alterar modulo9.infraestructuras.tipo se eliminan todas las
vistas directas e indirectas que dependen de dicha columna.

Una vez realizado el ALTER COLUMN, las vistas son recreadas en el
orden correcto de dependencias.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Identificadores de Alembic
# ---------------------------------------------------------------------------

revision: str = "2dbb6d44046f"
down_revision: Union[str, Sequence[str], None] = "b5d1e0c93a77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------

_TIPOS_DEFAULT = [
    "Galpón",
    "Corral",
    "Potrero",
    "Estanque",
    "Invernadero",
]

_TIPOS_ENUM = [
    "galpon",
    "corral",
    "potrero",
    "estanque",
    "invernadero",
]


# ---------------------------------------------------------------------------
# VISTAS
#
# Ordenadas desde las vistas base hacia las vistas que dependen de ellas.
#
# El DROP se realiza en orden inverso.
# ---------------------------------------------------------------------------

VIEW_DEFINITIONS = [

    # -----------------------------------------------------------------------
    # 1. Vista base
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_telemetria_contextualizada",
        """
SELECT t.id_telemetria,
    t.id_sensor,
    s.nombre AS nombre_sensor,
    (s.categoria)::text AS categoria_sensor,
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
    (t.categoria_variable)::text AS categoria_variable,
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
        ELSE round(
            EXTRACT(
                epoch FROM (
                    t.timestamp_envio - t.timestamp_captura
                )
            ) * 1000
        )::bigint
    END AS latencia_transmision_ms,
    CASE
        WHEN t.latencia_procesamiento_ms IS NOT NULL
            THEN t.latencia_procesamiento_ms::bigint
        WHEN t.timestamp_envio IS NOT NULL
            THEN round(
                EXTRACT(
                    epoch FROM (
                        t.timestamp_procesamiento - t.timestamp_envio
                    )
                ) * 1000
            )::bigint
        ELSE round(
            EXTRACT(
                epoch FROM (
                    t.timestamp_procesamiento - t.timestamp_captura
                )
            ) * 1000
        )::bigint
    END AS latencia_procesamiento_ms,
    round(
        EXTRACT(
            epoch FROM (
                t.timestamp_procesamiento - t.timestamp_captura
            )
        ) * 1000
    )::bigint AS latencia_total_ms,
    (t.origen)::text AS origen,
    (t.estado_calidad)::text AS estado_calidad,
    (t.tipo_dato)::text AS tipo_dato,
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
    (vl.modelo_manejo)::text AS modelo_manejo,
    (vl.estado_vinculacion)::text AS estado_vinculacion,
    (vl.mecanismo_vinculacion)::text AS mecanismo_vinculacion,
    COALESCE(
        vl.id_infraestructura,
        saa.id_infraestructura,
        ab.id_infraestructura
    ) AS id_infraestructura,
    i.nombre AS infraestructura,
    (i.tipo)::text AS tipo_infraestructura,
    i.id_finca,
    f.nombre AS finca,
    saa.punto_instalacion,
    vl.id_activo_biologico,
    ab.identificador AS identificador_activo,
    (ab.tipo)::text AS tipo_activo,
    eab.nombre AS estado_activo_biologico,
    esp.nombre AS especie_activo,
    (edi.estado_actual)::text AS estado_dispositivo,
    edi.fecha_ultimo_contacto,
    edi.tiempo_sin_contacto,
    (edi.causa_primaria)::text AS causa_inactividad,
    mqtt.estado_transmision_mqtt,
    mqtt.reintentos_mqtt,
    mqtt.gateway_id,
    COALESCE(buf.total_registros_buffer, 0::bigint)
        AS buffer_total_registros,
    COALESCE(buf.registros_pendientes, 0::bigint)
        AS buffer_registros_pendientes,
    COALESCE(buf.registros_confirmados, 0::bigint)
        AS buffer_registros_confirmados,
    buf.ultimo_dato_capturado AS buffer_ultimo_dato_capturado,
    COALESCE(buf.horas_buffer_trabajadas, 0::numeric)
        AS buffer_horas_trabajadas,
    COALESCE(buf.intentos_sincronizacion_total, 0::bigint)
        AS buffer_intentos_total,
    COALESCE(buf.intentos_sincronizacion_max, 0)
        AS buffer_intentos_max
FROM modulo3.telemetrias t
LEFT JOIN modulo9.sensores s
    ON s.id_sensores = t.id_sensor
LEFT JOIN modulo9.dispositivos_iot d
    ON d.id_dispositivo_iot = t.id_dispositivo_iot
LEFT JOIN modulo9.variables_ambientales va
    ON va.id_variable_ambiental = t.id_variable
LEFT JOIN LATERAL (
    SELECT
        v.id_vinculacion_lectura,
        v.id_activo_biologico,
        v.id_infraestructura,
        v.modelo_manejo,
        v.estado_vinculacion,
        v.mecanismo_vinculacion
    FROM modulo3.vinculaciones_lecturas v
    WHERE v.id_telemetria = t.id_telemetria
    ORDER BY v.fecha_creacion DESC,
             v.id_vinculacion_lectura DESC
    LIMIT 1
) vl ON true
LEFT JOIN modulo2.activos_biologicos ab
    ON ab.id_activo_biologico = vl.id_activo_biologico
LEFT JOIN modulo2.estados_activos_biologicos eab
    ON eab.id_estado_activo_biologico = ab.id_estado
LEFT JOIN modulo9.especies esp
    ON esp.id_especie = ab.id_especie
LEFT JOIN LATERAL (
    SELECT
        a.id_infraestructura,
        a.punto_instalacion
    FROM modulo9.sensores_areas_asociadas a
    WHERE a.id_sensor = t.id_sensor
      AND a.fecha_asociacion <= t.timestamp_captura
      AND (
          a.fecha_finalizacion IS NULL
          OR a.fecha_finalizacion > t.timestamp_captura
      )
    ORDER BY a.fecha_asociacion DESC,
             a.id_sensores_area_asociada DESC
    LIMIT 1
) saa ON true
LEFT JOIN modulo9.infraestructuras i
    ON i.id_infraestructura = COALESCE(
        vl.id_infraestructura,
        saa.id_infraestructura,
        ab.id_infraestructura
    )
LEFT JOIN modulo9.fincas f
    ON f.id_finca = i.id_finca
LEFT JOIN LATERAL (
    SELECT
        e.estado_actual,
        e.fecha_ultimo_contacto,
        e.tiempo_sin_contacto,
        e.causa_primaria
    FROM modulo3.estados_dispositivos_iot e
    WHERE e.id_dispositivo_iot = t.id_dispositivo_iot
    ORDER BY e.fecha_ultima_actualizacion DESC,
             e.id_estado_dispositivo_iot DESC
    LIMIT 1
) edi ON true
LEFT JOIN LATERAL (
    SELECT
        (tm.estado)::text AS estado_transmision_mqtt,
        tm.intentos AS reintentos_mqtt,
        tm.gatway_id AS gateway_id
    FROM modulo3.transmisiones_mqtt tm
    WHERE tm.id_dispositivo_iot = t.id_dispositivo_iot
      AND tm.fecha_transmision <= t.timestamp_procesamiento
    ORDER BY tm.fecha_transmision DESC,
             tm.id_transmicion_mqqt DESC
    LIMIT 1
) mqtt ON true
LEFT JOIN LATERAL (
    SELECT
        count(*) AS total_registros_buffer,
        count(*) FILTER (
            WHERE (b.estado_buffer)::text
                = ANY (
                    ARRAY[
                        'PENDIENTE'::text,
                        'ERROR'::text
                    ]
                )
        ) AS registros_pendientes,
        count(*) FILTER (
            WHERE (b.estado_buffer)::text = 'CONFIRMADO'::text
        ) AS registros_confirmados,
        max(b.fecha_captura) AS ultimo_dato_capturado,
        COALESCE(
            round(
                EXTRACT(
                    epoch FROM (
                        max(b.fecha_captura) - min(b.fecha_captura)
                    )
                ) / 3600.0,
                2
            ),
            0::numeric
        ) AS horas_buffer_trabajadas,
        COALESCE(
            sum(b.intentos_envio),
            0::bigint
        ) AS intentos_sincronizacion_total,
        COALESCE(
            max(b.intentos_envio),
            0
        ) AS intentos_sincronizacion_max
    FROM modulo3.buffers b
    WHERE b.id_dispositivo_iot = t.id_dispositivo_iot
) buf ON true
        """,
    ),

    # -----------------------------------------------------------------------
    # 2. Vista dependiente de la anterior
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_procesamiento_edge",
        """
WITH base AS (
    SELECT
        vw_m03_telemetria_contextualizada.id_telemetria,
        vw_m03_telemetria_contextualizada.id_sensor,
        vw_m03_telemetria_contextualizada.nombre_sensor,
        vw_m03_telemetria_contextualizada.id_variable,
        vw_m03_telemetria_contextualizada.variable_ambiental AS variable,
        vw_m03_telemetria_contextualizada.categoria_variable AS categoria,
        vw_m03_telemetria_contextualizada.valor,
        vw_m03_telemetria_contextualizada.unidad_medida,
        vw_m03_telemetria_contextualizada.valor_fisico_min AS minimo,
        vw_m03_telemetria_contextualizada.valor_fisico_max AS maximo,
        vw_m03_telemetria_contextualizada.ventana_agregacion_min AS ventana,
        vw_m03_telemetria_contextualizada.estado_calidad AS estado,
        CASE
            WHEN (
                vw_m03_telemetria_contextualizada.valor_fisico_min IS NULL
                OR vw_m03_telemetria_contextualizada.valor_fisico_max IS NULL
            )
            THEN NULL::numeric

            WHEN (
                vw_m03_telemetria_contextualizada.valor
                < vw_m03_telemetria_contextualizada.valor_fisico_min
                AND NULLIF(
                    abs(vw_m03_telemetria_contextualizada.valor_fisico_min),
                    0::numeric
                ) IS NOT NULL
            )
            THEN round(
                (
                    (
                        vw_m03_telemetria_contextualizada.valor_fisico_min
                        - vw_m03_telemetria_contextualizada.valor
                    )
                    /
                    NULLIF(
                        abs(
                            vw_m03_telemetria_contextualizada.valor_fisico_min
                        ),
                        0::numeric
                    )
                ) * 100::numeric,
                2
            )

            WHEN (
                vw_m03_telemetria_contextualizada.valor
                > vw_m03_telemetria_contextualizada.valor_fisico_max
                AND NULLIF(
                    abs(vw_m03_telemetria_contextualizada.valor_fisico_max),
                    0::numeric
                ) IS NOT NULL
            )
            THEN round(
                (
                    (
                        vw_m03_telemetria_contextualizada.valor
                        - vw_m03_telemetria_contextualizada.valor_fisico_max
                    )
                    /
                    NULLIF(
                        abs(
                            vw_m03_telemetria_contextualizada.valor_fisico_max
                        ),
                        0::numeric
                    )
                ) * 100::numeric,
                2
            )

            WHEN (
                vw_m03_telemetria_contextualizada.valor
                < vw_m03_telemetria_contextualizada.valor_fisico_min
                OR vw_m03_telemetria_contextualizada.valor
                > vw_m03_telemetria_contextualizada.valor_fisico_max
            )
            THEN NULL::numeric

            ELSE 0::numeric
        END AS desviacion_pct
    FROM modulo3.vw_m03_telemetria_contextualizada
)
SELECT
    id_telemetria,
    id_sensor,
    nombre_sensor,
    id_variable,
    variable,
    valor,
    unidad_medida,
    minimo,
    maximo,
    desviacion_pct AS nivel_desviacion_pct,
    CASE
        WHEN minimo IS NULL OR maximo IS NULL
            THEN 'SIN_RANGO'::text
        WHEN desviacion_pct IS NULL
            THEN 'ERROR_CONFIGURACION'::text
        WHEN desviacion_pct = 0::numeric
            THEN 'NORMAL'::text
        WHEN desviacion_pct <= 10::numeric
            THEN 'LEVE'::text
        WHEN desviacion_pct <= 25::numeric
            THEN 'MODERADO'::text
        ELSE 'CRITICO'::text
    END AS nivel_desviacion,
    categoria,
    ventana,
    estado AS estado_calidad,
    CASE
        WHEN minimo IS NULL OR maximo IS NULL
            THEN 'SIN_RANGO'::text
        WHEN desviacion_pct = 0::numeric
            THEN 'NORMAL'::text
        ELSE 'DESVIACION_SIMPLE'::text
    END AS estado_desviacion
FROM base
        """,
    ),

    # -----------------------------------------------------------------------
    # 3. Monitor de ingesta
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_01_monitor_ingesta",
        """
SELECT
    id_telemetria,
    nombre_sensor,
    variable_ambiental,
    origen,
    valor,
    valor_crudo,
    valor_ajustado,
    unidad_medida,
    estado_calidad,
    latencia_total_ms AS latencia_ms,
    timestamp_captura AS momento_captura,
    dispositivo_nombre,
    dispositivo_serial,
    infraestructura,
    finca,
    buffer_total_registros,
    buffer_registros_pendientes,
    buffer_ultimo_dato_capturado
FROM modulo3.vw_m03_telemetria_contextualizada
        """,
    ),

    # -----------------------------------------------------------------------
    # 4. RF20 áreas finca resumen
    # -----------------------------------------------------------------------

    (
        "modulo9",
        "vw_rf20_areas_finca_resumen",
        """
SELECT
    i.id_finca,
    i.id_infraestructura,
    i.nombre,
    i.descripcion,
    i.tipo,
    i.superficie,
    i.es_activo,
    count(d.id_dispositivo_iot)
        FILTER (WHERE d.es_activo IS TRUE)
        AS dispositivos_activos,
    count(d.id_dispositivo_iot) AS total_dispositivos
FROM modulo9.infraestructuras i
LEFT JOIN (
    SELECT DISTINCT ON (d0.id_dispositivo_iot)
        d0.id_dispositivo_iot,
        d0.serial,
        d0.descripcion,
        d0.es_activo,
        d0.fecha_creacion,
        COALESCE(
            saa.id_infraestructura,
            ab.id_infraestructura
        ) AS id_infraestructura
    FROM modulo9.dispositivos_iot d0
    LEFT JOIN modulo9.sensores s
        ON s.id_dispositivo_iot = d0.id_dispositivo_iot
    LEFT JOIN modulo9.sensores_areas_asociadas saa
        ON saa.id_sensor = s.id_sensores
       AND (
           saa.fecha_finalizacion IS NULL
           OR saa.fecha_finalizacion > now()
       )
    LEFT JOIN modulo2.activos_biologicos ab
        ON ab.id_dispositivo_iot = d0.id_dispositivo_iot
    ORDER BY
        d0.id_dispositivo_iot,
        saa.fecha_asociacion DESC NULLS LAST,
        saa.id_sensores_area_asociada DESC NULLS LAST
) d
    ON d.id_infraestructura = i.id_infraestructura
GROUP BY
    i.id_finca,
    i.id_infraestructura,
    i.nombre,
    i.descripcion,
    i.tipo,
    i.superficie,
    i.es_activo
        """,
    ),

    # -----------------------------------------------------------------------
    # 5. Activo biológico por infraestructura
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_activo_biologico_valor_infraestructura",
        """
SELECT
    id_telemetria,
    id_activo_biologico,
    identificador_activo,
    tipo_activo,
    especie_activo AS especie,
    estado_activo_biologico AS estado_biologico,
    id_infraestructura,
    infraestructura,
    id_finca,
    finca,
    variable_ambiental AS tipo_variable,
    valor AS valor_infraestructura,
    timestamp_captura AS fecha_ultima_captura,
    estado_calidad AS estado_ultima_telemetria,
    estado_vinculacion,
    mecanismo_vinculacion
FROM modulo3.vw_m03_telemetria_contextualizada t
WHERE id_activo_biologico IS NOT NULL
        """,
    ),

    # -----------------------------------------------------------------------
    # 6. RF20 áreas productivas y dispositivos
    # -----------------------------------------------------------------------

    (
        "modulo9",
        "vw_rf20_areas_productivas_dispositivos",
        """
SELECT
    i.id_infraestructura,
    i.id_finca,
    i.nombre AS area,
    i.tipo,
    i.es_activo,
    f.nombre AS finca,
    (f.ubicacion ->> 'municipio'::text) AS municipio,
    count(d.id_dispositivo_iot) AS total_dispositivos
FROM modulo9.infraestructuras i
JOIN modulo9.fincas f
    ON f.id_finca = i.id_finca
LEFT JOIN (
    SELECT DISTINCT ON (d0.id_dispositivo_iot)
        d0.id_dispositivo_iot,
        d0.serial,
        d0.descripcion,
        d0.es_activo,
        d0.fecha_creacion,
        COALESCE(
            saa.id_infraestructura,
            ab.id_infraestructura
        ) AS id_infraestructura
    FROM modulo9.dispositivos_iot d0
    LEFT JOIN modulo9.sensores s
        ON s.id_dispositivo_iot = d0.id_dispositivo_iot
    LEFT JOIN modulo9.sensores_areas_asociadas saa
        ON saa.id_sensor = s.id_sensores
       AND (
           saa.fecha_finalizacion IS NULL
           OR saa.fecha_finalizacion > now()
       )
    LEFT JOIN modulo2.activos_biologicos ab
        ON ab.id_dispositivo_iot = d0.id_dispositivo_iot
    ORDER BY
        d0.id_dispositivo_iot,
        saa.fecha_asociacion DESC NULLS LAST,
        saa.id_sensores_area_asociada DESC NULLS LAST
) d
    ON d.id_infraestructura = i.id_infraestructura
GROUP BY
    i.id_infraestructura,
    i.id_finca,
    i.nombre,
    i.tipo,
    i.es_activo,
    f.nombre,
    f.ubicacion
        """,
    ),

    # -----------------------------------------------------------------------
    # 7. Alertas contextualizadas
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_alerta_contextualizada",
        """
SELECT
    a.id_alerta AS id_alerta_telemetria,
    a.id_alerta,
    COALESCE(
        ra.nombre,
        (a.tipo_alerta)::text::character varying
    ) AS nombre_alerta,
    (a.tipo_alerta)::text AS tipo_alerta,
    a.tipo_variable,
    (a.estado_alerta)::text AS estado_alerta,
    (a.severidad)::text AS nivel_criticidad,
    (a.origen_evento)::text AS origen_evento,
    COALESCE(
        tctx.valor,
        ee.valor_evaluado,
        pi.valor_numerico
    ) AS valor_detectado,
    CASE (a.origen_evento)::text
        WHEN 'EDGE' THEN 'EDGE'::text
        WHEN 'IA' THEN 'IA'::text
        WHEN 'BACKEND' THEN 'BACKEND'::text
        WHEN NULL THEN
            CASE
                WHEN a.id_evento_edge_computing IS NOT NULL
                    THEN 'EDGE'::text
                WHEN a.id_paquete_inferencia IS NOT NULL
                    THEN 'IA'::text
                ELSE 'BACKEND'::text
            END
        ELSE 'BACKEND'::text
    END AS como_se_genera,
    COALESCE(
        a.fecha_evento,
        ee.fecha_captura,
        tctx.timestamp_captura,
        pi.fecha_envio,
        a.fecha_registro
    ) AS fecha_alerta,
    COALESCE(
        a.fecha_evento,
        ee.fecha_captura,
        tctx.timestamp_captura,
        pi.fecha_envio,
        a.fecha_registro
    ) AS fecha_evento,
    a.fecha_generacion,
    a.fecha_notificacion,
    a.fecha_atencion,
    a.fecha_resolucion,
    a.fecha_vencimiento,
    a.id_regla_alerta,
    ra.nombre AS nombre_regla,
    ra.es_regla_compuesta,
    a.id_evento_edge_computing,
    (ee.tipo_evento)::text AS tipo_evento_edge,
    (ee.severidad)::text AS severidad_edge,
    a.id_telemetria,
    a.id_paquete_inferencia,
    (pi.estado_paquete)::text AS estado_paquete_inferencia,
    pi.intento_envios AS intentos_inferencia,
    COALESCE(
        a.id_sensor,
        tctx.id_sensor,
        ee.id_sensor,
        pi.id_sensor
    ) AS id_sensor,
    COALESCE(
        tctx.nombre_sensor,
        s.nombre
    ) AS nombre_sensor,
    COALESCE(
        a.id_dispositivo_ioit,
        tctx.id_dispositivo_iot,
        ee.id_dispositivo_iot,
        pi.id_dispositivo_iot
    ) AS id_dispositivo_iot,
    COALESCE(
        tctx.dispositivo_nombre,
        d.descripcion
    ) AS dispositivo_nombre,
    COALESCE(
        tctx.dispositivo_serial,
        d.serial
    ) AS dispositivo_serial,
    COALESCE(
        a.id_infraestructura,
        tctx.id_infraestructura,
        saa.id_infraestructura,
        ab.id_infraestructura
    ) AS id_infraestructura,
    i.nombre AS infraestructura,
    i.id_finca,
    f.nombre AS finca,
    COALESCE(
        a.id_activo_biologico,
        tctx.id_activo_biologico
    ) AS id_activo_biologico,
    ab.identificador AS identificador_activo,
    (a.conflicto_resolucion)::text AS conflicto_resolucion,
    NULL::text AS severidad_edge_original,
    NULL::text AS severidad_ia,
    NULL::text AS tipo_edge_original,
    NULL::text AS tipo_ia_original,
    a.diagnostico,
    a.motivo_descarte,
    a.accion_sugerida,
    a.metadato_evento,
    CASE (a.estado_alerta)::text
        WHEN 'RESUELTA' THEN 'EXITOSO'::text
        WHEN 'DESCARTADA' THEN 'RECHAZADO'::text
        WHEN 'VENCIDA' THEN 'FALLIDO'::text
        WHEN 'EN_ATENCION' THEN 'PARCIAL'::text
        ELSE 'ADVERTENCIA'::text
    END AS resultado_evento,
    (a.tipo_alerta)::text AS nivel_alerta_raw
FROM modulo3.alertas a
LEFT JOIN modulo3.vw_m03_telemetria_contextualizada tctx
    ON tctx.id_telemetria = a.id_telemetria
LEFT JOIN modulo3.eventos_edge_computing ee
    ON ee.id_evento_edge_computing = a.id_evento_edge_computing
LEFT JOIN modulo3.paquetes_inferencia pi
    ON pi.id_paquetes_inferencia = a.id_paquete_inferencia
LEFT JOIN modulo3.reglas_alertas ra
    ON ra.id_regla_alertas = a.id_regla_alerta
LEFT JOIN modulo9.sensores s
    ON s.id_sensores = COALESCE(
        a.id_sensor,
        tctx.id_sensor,
        ee.id_sensor,
        pi.id_sensor
    )
LEFT JOIN modulo9.dispositivos_iot d
    ON d.id_dispositivo_iot = COALESCE(
        a.id_dispositivo_ioit,
        tctx.id_dispositivo_iot,
        ee.id_dispositivo_iot,
        pi.id_dispositivo_iot
    )
LEFT JOIN LATERAL (
    SELECT x.id_infraestructura
    FROM modulo9.sensores_areas_asociadas x
    WHERE x.id_sensor = COALESCE(
        a.id_sensor,
        tctx.id_sensor,
        ee.id_sensor,
        pi.id_sensor
    )
      AND x.fecha_asociacion <= COALESCE(
          a.fecha_evento,
          ee.fecha_captura,
          tctx.timestamp_captura,
          pi.fecha_envio,
          a.fecha_registro
      )
      AND (
          x.fecha_finalizacion IS NULL
          OR x.fecha_finalizacion > COALESCE(
              a.fecha_evento,
              ee.fecha_captura,
              tctx.timestamp_captura,
              pi.fecha_envio,
              a.fecha_registro
          )
      )
    ORDER BY
        x.fecha_asociacion DESC,
        x.id_sensores_area_asociada DESC
    LIMIT 1
) saa ON true
LEFT JOIN modulo2.activos_biologicos ab
    ON ab.id_activo_biologico = COALESCE(
        a.id_activo_biologico,
        tctx.id_activo_biologico
    )
LEFT JOIN modulo9.infraestructuras i
    ON i.id_infraestructura = COALESCE(
        a.id_infraestructura,
        tctx.id_infraestructura,
        saa.id_infraestructura,
        ab.id_infraestructura
    )
LEFT JOIN modulo9.fincas f
    ON f.id_finca = i.id_finca
        """,
    ),

    # -----------------------------------------------------------------------
    # 8. Áreas destino
    # -----------------------------------------------------------------------

    (
        "modulo9",
        "vw_rf22_areas_destino_disponibles",
        """
SELECT
    i.id_infraestructura,
    i.nombre,
    i.tipo,
    f.id_finca,
    f.nombre AS finca
FROM modulo9.infraestructuras i
JOIN modulo9.fincas f
    ON f.id_finca = i.id_finca
WHERE i.es_activo IS TRUE
  AND f.es_activo IS TRUE
        """,
    ),

    # -----------------------------------------------------------------------
    # 9. Historial de lecturas
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_historial_lecturas",
        """
SELECT
    id_telemetria,
    id_variable,
    variable_ambiental AS tipo_variable,
    valor,
    unidad_medida,
    id_infraestructura,
    infraestructura,
    finca,
    timestamp_captura,
    estado_calidad,
    origen
FROM modulo3.vw_m03_telemetria_contextualizada
        """,
    ),

    # -----------------------------------------------------------------------
    # 10. Lectura contextualizada
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_lectura_contextualizada",
        """
SELECT
    id_telemetria AS id_lectura_sensor,
    id_telemetria,
    id_sensor,
    nombre_sensor,
    sensor_activo,
    id_dispositivo_iot,
    dispositivo_nombre,
    dispositivo_serial,
    id_infraestructura,
    infraestructura,
    id_finca,
    finca,
    id_variable,
    variable_ambiental,
    categoria_variable,
    valor,
    valor_crudo,
    valor_ajustado,
    unidad_medida,
    estado_calidad AS estado_lectura,
    origen AS origen_procesamiento,
    tipo_dato AS mecanismo_dato,
    estado_conectividad,
    estado_dispositivo,
    estado_transmision_mqtt,
    reintentos_mqtt,
    timestamp_captura AS fecha_captura,
    timestamp_envio AS fecha_envio,
    timestamp_procesamiento AS fecha_recepcion,
    latencia_transmision_ms,
    latencia_procesamiento_ms,
    latencia_total_ms,
    estado_vinculacion,
    mecanismo_vinculacion
FROM modulo3.vw_m03_telemetria_contextualizada
        """,
    ),

    # -----------------------------------------------------------------------
    # 11. Bitácora estado sensor
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_03_bitacora_estado_sensor_con_lecturas",
        """
SELECT
    l.id_lectura_sensor,
    l.id_sensor,
    l.nombre_sensor,
    CASE
        WHEN l.sensor_activo THEN 'ACTIVO'::text
        ELSE 'INACTIVO'::text
    END AS estado_sensor,
    eas.estado_semaforo AS estado_semaforo_sensor,
    (eas.estado_calidad)::text
        AS estado_calidad_actual_sensor,
    (eas.estado_desviacion)::text
        AS estado_desviacion_actual_sensor,
    l.dispositivo_nombre,
    l.infraestructura,
    l.finca,
    l.valor,
    l.unidad_medida,
    l.estado_lectura,
    l.origen_procesamiento AS mecanismo,
    l.fecha_captura,
    l.fecha_recepcion
FROM modulo3.vw_m03_lectura_contextualizada l
LEFT JOIN modulo3.estados_actuales_sensores eas
    ON eas.id_estado_actual_sensor = l.id_sensor
   AND eas.id_dispositivo_iot = l.id_dispositivo_iot
        """,
    ),

    # -----------------------------------------------------------------------
    # 12. Monitor ingesta
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_02_monitor_ingesta",
        """
SELECT
    id_telemetria,
    id_sensor,
    nombre_sensor,
    id_dispositivo_iot,
    dispositivo_nombre,
    variable_ambiental,
    timestamp_captura,
    timestamp_envio,
    timestamp_procesamiento,
    latencia_transmision_ms,
    latencia_procesamiento_ms,
    latencia_total_ms,
    latencia_alta,
    origen,
    estado_calidad
FROM modulo3.vw_m03_telemetria_contextualizada
        """,
    ),

    # -----------------------------------------------------------------------
    # 13. Calidad datos
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_calidad_datos_telemetria",
        """
SELECT
    id_telemetria,
    id_variable,
    variable_ambiental AS variable,
    id_infraestructura,
    infraestructura,
    finca,
    id_sensor,
    nombre_sensor,
    id_dispositivo_iot,
    dispositivo_nombre,
    valor,
    valor_crudo,
    valor_ajustado,
    unidad_medida,
    origen,
    estado_calidad,
    timestamp_captura,
    timestamp_envio,
    timestamp_procesamiento
FROM modulo3.vw_m03_telemetria_contextualizada
        """,
    ),

    # -----------------------------------------------------------------------
    # 14. Bitácora lecturas
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_02_bitacora_lecturas_sensores_mecanismos",
        """
SELECT
    id_lectura_sensor,
    nombre_sensor,
    sensor_activo,
    dispositivo_nombre,
    dispositivo_serial,
    infraestructura,
    finca,
    valor,
    unidad_medida,
    estado_lectura AS estado,
    origen_procesamiento AS mecanismo_origen,
    mecanismo_dato,
    estado_conectividad,
    estado_dispositivo,
    estado_transmision_mqtt,
    reintentos_mqtt,
    fecha_captura,
    fecha_envio,
    fecha_recepcion,
    latencia_transmision_ms,
    latencia_procesamiento_ms,
    latencia_total_ms,
    estado_vinculacion,
    mecanismo_vinculacion
FROM modulo3.vw_m03_lectura_contextualizada
        """,
    ),

    # -----------------------------------------------------------------------
    # 15. Estados dispositivos
    # -----------------------------------------------------------------------

    (
        "modulo3",
        "vw_m03_estados_dispositivos",
        """
SELECT
    id_telemetria,
    id_activo_biologico,
    identificador_activo,
    especie,
    estado_biologico,
    id_infraestructura,
    infraestructura,
    finca,
    tipo_variable,
    valor_infraestructura,
    fecha_ultima_captura,
    estado_ultima_telemetria,
    estado_vinculacion,
    mecanismo_vinculacion
FROM modulo3.vw_m03_activo_biologico_valor_infraestructura
        """,
    ),
]


# ---------------------------------------------------------------------------
# Orden de eliminación
#
# Una vista que depende de otra debe eliminarse primero.
# Por eso se utiliza el orden inverso.
# ---------------------------------------------------------------------------

DROP_ORDER = list(
    reversed(
        [
            (schema, name)
            for schema, name, _ in VIEW_DEFINITIONS
        ]
    )
)


def _drop_dependent_views() -> None:
    """
    Elimina todas las vistas afectadas antes de modificar
    modulo9.infraestructuras.tipo.
    """
    for schema, name in DROP_ORDER:
        op.execute(
            f"DROP VIEW IF EXISTS {schema}.{name};"
        )


def _create_dependent_views() -> None:
    """
    Recrea las vistas en el orden correcto de dependencias.
    """
    for schema, name, select_sql in VIEW_DEFINITIONS:
        op.execute(
            f"CREATE VIEW {schema}.{name} AS{select_sql};"
        )


# ---------------------------------------------------------------------------
# UPGRADE
# ---------------------------------------------------------------------------

def upgrade() -> None:

    # -----------------------------------------------------------------------
    # 1. Crear catálogo administrable
    # -----------------------------------------------------------------------

    op.create_table(
        "tipos_area",

        sa.Column(
            "id_tipo_area",
            sa.Integer,
            sa.Identity(start=1, increment=1),
            primary_key=True,
        ),

        sa.Column(
            "nombre",
            sa.String(30),
            nullable=False,
        ),

        sa.Column(
            "es_activo",
            sa.Boolean,
            nullable=False,
            server_default=sa.true(),
        ),

        sa.Column(
            "fecha_creacion",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.UniqueConstraint(
            "nombre",
            name="uq_tipo_area_nombre",
        ),

        schema="modulo9",
    )

    # -----------------------------------------------------------------------
    # 2. Datos iniciales
    # -----------------------------------------------------------------------

    op.bulk_insert(
        sa.table(
            "tipos_area",
            sa.column("nombre", sa.String),
            schema="modulo9",
        ),
        [
            {"nombre": nombre}
            for nombre in _TIPOS_DEFAULT
        ],
    )

    # -----------------------------------------------------------------------
    # 3. IMPORTANTE:
    #
    # Romper las dependencias antes de cambiar el tipo de la columna.
    # -----------------------------------------------------------------------

    _drop_dependent_views()

    # -----------------------------------------------------------------------
    # 4. Cambiar ENUM -> VARCHAR(30)
    # -----------------------------------------------------------------------

    op.alter_column(
        "infraestructuras",
        "tipo",
        type_=sa.String(30),
        schema="modulo9",
        existing_type=sa.Enum(
            *_TIPOS_ENUM,
            name="enum_tipo_infraestructura",
            schema="modulo9",
        ),
        postgresql_using="tipo::text",
    )

    # -----------------------------------------------------------------------
    # 5. Migrar valores existentes
    #
    # galpon       -> Galpón
    # corral       -> Corral
    # potrero      -> Potrero
    # estanque     -> Estanque
    # invernadero  -> Invernadero
    # -----------------------------------------------------------------------

    for viejo, nuevo in zip(
        _TIPOS_ENUM,
        _TIPOS_DEFAULT,
    ):
        op.execute(
            sa.text(
                """
                UPDATE modulo9.infraestructuras
                SET tipo = :nuevo
                WHERE tipo = :viejo
                """
            ).bindparams(
                nuevo=nuevo,
                viejo=viejo,
            )
        )

    # -----------------------------------------------------------------------
    # 5. Crear la clave foránea
    # -----------------------------------------------------------------------

    op.create_foreign_key(
        "fk_infraestructuras_tipo_area",
        "infraestructuras", "tipos_area",
        ["tipo"], ["nombre"],
        source_schema="modulo9", referent_schema="modulo9",
        onupdate="CASCADE",
    )

    # -----------------------------------------------------------------------
    # 6. Recrear todas las vistas
    # -----------------------------------------------------------------------

    _create_dependent_views()

    # -----------------------------------------------------------------------
    # 7. El ENUM antiguo se mantiene.
    #
    # No se elimina para evitar afectar otras dependencias desconocidas.
    # -----------------------------------------------------------------------


# ---------------------------------------------------------------------------
# DOWNGRADE
# ---------------------------------------------------------------------------

def downgrade() -> None:

    # -----------------------------------------------------------------------
    # 1. Eliminar la clave foránea.
    # -----------------------------------------------------------------------

    op.drop_constraint(
        "fk_infraestructuras_tipo_area",
        "infraestructuras",
        schema="modulo9",
        type_="foreignkey",
    )

    # -----------------------------------------------------------------------
    # 1. Eliminar vistas antes de volver a cambiar el tipo.
    # -----------------------------------------------------------------------

    _drop_dependent_views()

    # -----------------------------------------------------------------------
    # 2. Convertir nuevamente los valores canónicos a los valores del ENUM.
    # -----------------------------------------------------------------------

    for viejo, nuevo in zip(
        _TIPOS_ENUM,
        _TIPOS_DEFAULT,
    ):
        op.execute(
            sa.text(
                """
                UPDATE modulo9.infraestructuras
                SET tipo = :viejo
                WHERE tipo = :nuevo
                """
            ).bindparams(
                nuevo=nuevo,
                viejo=viejo,
            )
        )

    # -----------------------------------------------------------------------
    # 3. VARCHAR(30) -> ENUM
    # -----------------------------------------------------------------------

    op.alter_column(
        "infraestructuras",
        "tipo",
        type_=sa.Enum(
            *_TIPOS_ENUM,
            name="enum_tipo_infraestructura",
            schema="modulo9",
        ),
        schema="modulo9",
        existing_type=sa.String(30),
        postgresql_using=(
            "tipo::modulo9.enum_tipo_infraestructura"
        ),
    )

    # -----------------------------------------------------------------------
    # 4. Recrear vistas
    # -----------------------------------------------------------------------

    _create_dependent_views()

    # -----------------------------------------------------------------------
    # 5. Eliminar catálogo
    # -----------------------------------------------------------------------

    op.drop_table(
        "tipos_area",
        schema="modulo9",
    )