"""Vistas modulo2

Revision ID: d3d166092570
Revises: 32389a6e5686
Create Date: 2026-10-11 07:54:45.997374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3d166092570'
down_revision: Union[str, Sequence[str], None] = '32389a6e5686'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # =====================================================================
    # 1. VISTAS DE LISTADO Y GESTIÓN BASE (RF-33, RF-34, RF-35, RF-36)
    # =====================================================================
    op.execute("""
    -- RF-33 / RF-51: Listado general de activos biológicos registrados en el sistema.
    CREATE OR REPLACE VIEW modulo2.vw_rf33_activos_biologicos_listado AS
     SELECT ab.id_activo_biologico,
        ab.identificador,
        lower((ab.identificador)::text) AS identificador_normalizado,
        ab.id_especie,
        e.nombre AS especie,
        ab.id_infraestructura,
        i.nombre AS infraestructura,
        ab.tipo,
        ab.fecha_inicio_ciclo,
        ab.id_estado,
        eab.nombre AS estado,
        ab.descripcion,
        ab.origen_financiero,
        ab.costo_adquisicion,
        ab.atributos_dinamicos,
        ab.id_usuario,
        ab.fecha_creacion
       FROM (((modulo2.activos_biologicos ab
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)))
         JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = ab.id_infraestructura)))
         JOIN modulo2.estados_activos_biologicos eab ON ((eab.id_estado_activo_biologico = ab.id_estado)));

    -- RF-34 / RF-48: Historial de movimientos y transferencias de infraestructura de un activo.
    CREATE OR REPLACE VIEW modulo2.vw_rf34_movimientos_activo AS
     SELECT m.id_movimiento,
        m.id_activo_biologico,
        ab.identificador,
        m.tipo AS tipo_movimiento,
        m.id_infraestructura_origen,
        i_origen.nombre AS infraestructura_origen,
        m.id_infraestructura_destino,
        i_destino.nombre AS infraestructura_destino,
        f_origen.id_finca AS id_finca_origen,
        f_origen.nombre AS finca_origen,
        f_destino.id_finca AS id_finca_destino,
        f_destino.nombre AS finca_destino,
        m.fecha_transferencia,
        m.fecha_fin,
        m.fecha_registro,
        m.id_usuario,
        concat_ws(' '::text, u.nombre, u.apellidos) AS usuario_responsable
       FROM ((((((modulo2.movimientos m
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = m.id_activo_biologico)))
         JOIN modulo9.infraestructuras i_origen ON ((i_origen.id_infraestructura = m.id_infraestructura_origen)))
         JOIN modulo9.infraestructuras i_destino ON ((i_destino.id_infraestructura = m.id_infraestructura_destino)))
         JOIN modulo9.fincas f_origen ON ((f_origen.id_finca = i_origen.id_finca)))
         JOIN modulo9.fincas f_destino ON ((f_destino.id_finca = i_destino.id_finca)))
         JOIN modulo1.usuarios u ON ((u.id_usuario = m.id_usuario)));

    -- RF-35: Ficha de datos específicos para activos de tipo INDIVIDUAL.
    -- Nota: Se usa 'fecha_nacimeinto' (sic) del DDL, alias a 'fecha_nacimiento' para consistencia.
    CREATE OR REPLACE VIEW modulo2.vw_rf35_activos_individuales AS
     SELECT ab.id_activo_biologico,
        ab.identificador,
        dai.raza,
        dai.sexo,
        dai.fecha_nacimeinto AS fecha_nacimiento,
        dai.peso_inicial,
        ab.id_especie,
        e.nombre AS especie,
        ab.id_infraestructura,
        i.nombre AS infraestructura,
        ab.id_estado,
        eab.nombre AS estado,
        ab.descripcion,
        ab.fecha_creacion
       FROM ((((modulo2.activos_biologicos ab
         JOIN modulo2.detalles_activos_individuales dai ON ((dai.id_activo_biologico = ab.id_activo_biologico)))
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)))
         JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = ab.id_infraestructura)))
         JOIN modulo2.estados_activos_biologicos eab ON ((eab.id_estado_activo_biologico = ab.id_estado)))
      WHERE (ab.tipo = 'INDIVIDUAL'::modulo2.enum_activo_biologico_tipo);

    -- RF-36 / RF-52: Ficha de datos específicos y métricas para activos de tipo POBLACIONAL.
    CREATE OR REPLACE VIEW modulo2.vw_rf52_auditoria_activos_poblacionales AS
     SELECT ab.id_activo_biologico,
        ab.identificador AS identificador_lote,
        e.nombre AS especie,
        i.nombre AS infraestructura,
        eab.nombre AS estado,
        dp.cantidad_inicial,
        dp.cantidad_actual,
        dp.peso_promedio,
        dp.biomasa_total,
        dp.densidad,
        ab.descripcion,
        ab.fecha_creacion,
        ab.id_usuario
       FROM ((((modulo2.activos_biologicos ab
         JOIN modulo2.detalles_activos_biologicos_poblacionales dp ON ((dp.id_activo_biologico = ab.id_activo_biologico)))
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)))
         JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = ab.id_infraestructura)))
         JOIN modulo2.estados_activos_biologicos eab ON ((eab.id_estado_activo_biologico = ab.id_estado)))
      WHERE (ab.tipo = 'POBLACIONAL'::modulo2.enum_activo_biologico_tipo);
    """)

    # =====================================================================
    # 2. VISTAS DE CICLO PRODUCTIVO Y FASES (RF-37, RF-38)
    # =====================================================================
    op.execute("""
    -- RF-37: Estado actual de la fase productiva de un activo (filtra solo la activa).
    CREATE OR REPLACE VIEW modulo2.vw_rf37_estado_fase_actual AS
     SELECT gf.id_gestion_fases,
        gf.id_activo_biologico,
        ab.identificador,
        gf.id_ciclo_productiva,
        cp.nombre AS ciclo_actual,
        gf.fecha_inicio,
        gf.fecha_finalizacion,
        gf.es_activa,
        gf.id_usuario
       FROM ((modulo2.gestiones_fases gf
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = gf.id_activo_biologico)))
         JOIN modulo9.ciclos_productivos cp ON ((cp.id_ciclo_productivo = gf.id_ciclo_productiva)))
      WHERE gf.es_activa IS TRUE;

    -- RF-37: Secuencia completa de fases productivas con ordenamiento lógico.
    CREATE OR REPLACE VIEW modulo2.vw_rf37_fases_productivas_secuencia AS
     SELECT row_number() OVER (PARTITION BY gf.id_activo_biologico, gf.id_gestion_fases ORDER BY cpb.id_ciclos_productivo_biologico) AS paso,
        gf.id_gestion_fases,
        gf.id_activo_biologico,
        ab.identificador AS identificador_activo,
        e.id_especie,
        e.nombre AS especie,
        cp.id_ciclo_productivo,
        cp.nombre AS ciclo_productivo,
        cpb.id_ciclos_productivo_biologico AS orden_secuencia,
        cb.id_ciclo_biologico,
        cb.nombre AS fase,
        cb.descripcion,
        cb.duracion_dias,
        CASE
            WHEN gf.es_activa THEN 'Ciclo activo'::text
            ELSE 'Ciclo cerrado'::text
        END AS estado_ciclo,
        gf.fecha_inicio,
        gf.fecha_finalizacion,
        gf.es_activa
       FROM (((((modulo2.gestiones_fases gf
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = gf.id_activo_biologico)))
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)))
         JOIN modulo9.ciclos_productivos cp ON ((cp.id_ciclo_productivo = gf.id_ciclo_productiva)))
         JOIN modulo9.ciclos_productivos_biologicos cpb ON ((cpb.id_ciclo_productivo = cp.id_ciclo_productivo)))
         JOIN modulo9.ciclos_biologicos cb ON (((cb.id_ciclo_biologico = cpb.id_ciclo_biologico) AND (cb.id_especie = ab.id_especie))));

    -- RF-37 / RF-52: Historial de transiciones de fases con usuario involucrado.
    CREATE OR REPLACE VIEW modulo2.vw_rf37_historial_fases AS
     SELECT row_number() OVER (PARTITION BY gf.id_activo_biologico, gf.id_gestion_fases ORDER BY cpb.id_ciclos_productivo_biologico) AS paso,
        gf.id_gestion_fases,
        gf.id_activo_biologico,
        ab.identificador AS identificador_activo,
        cb.id_ciclo_biologico,
        cb.nombre AS fase,
        gf.id_ciclo_productiva,
        cp.nombre AS ciclo_productivo,
        gf.id_usuario,
        concat_ws(' '::text, u.nombre, u.apellidos) AS usuario_involucrado,
        gf.fecha_inicio,
        gf.fecha_finalizacion,
        gf.es_activa
       FROM (((((modulo2.gestiones_fases gf
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = gf.id_activo_biologico)))
         JOIN modulo9.ciclos_productivos cp ON ((cp.id_ciclo_productivo = gf.id_ciclo_productiva)))
         JOIN modulo9.ciclos_productivos_biologicos cpb ON ((cpb.id_ciclo_productivo = cp.id_ciclo_productivo)))
         JOIN modulo9.ciclos_biologicos cb ON (((cb.id_ciclo_biologico = cpb.id_ciclo_biologico) AND (cb.id_especie = ab.id_especie))))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = gf.id_usuario)));

    -- RF-38 / RF-52: Auditoría específica de cierres de ciclo productivo, vinculando con cambios de estado.
    CREATE OR REPLACE VIEW modulo2.vw_rf52_auditoria_cierres_ciclo_productivo AS
     SELECT gf.id_gestion_fases,
        gf.id_activo_biologico,
        ab.identificador,
        cp.nombre AS ciclo_productivo,
        gf.fecha_finalizacion,
        h.id_historico_estado_activo,
        ea_ant.nombre AS estado_anterior,
        ea_nvo.nombre AS estado_nuevo,
        h.motivo_cambio,
        h.modulo_origen,
        concat_ws(' '::text, u.nombre, u.apellidos) AS usuario_responsable
       FROM ((((((modulo2.gestiones_fases gf
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = gf.id_activo_biologico)))
         JOIN modulo9.ciclos_productivos cp ON ((cp.id_ciclo_productivo = gf.id_ciclo_productiva)))
         LEFT JOIN modulo2.historicos_estados_activos h ON (((h.id_activo_biologico = gf.id_activo_biologico) AND (((h.modulo_origen)::text = 'RF-38'::text) OR ((gf.fecha_finalizacion IS NOT NULL) AND (h.fecha_cambio >= (gf.fecha_finalizacion - '00:05:00'::interval)) AND (h.fecha_cambio <= (gf.fecha_finalizacion + '00:05:00'::interval)))))))
         LEFT JOIN modulo2.estados_activos_biologicos ea_ant ON ((ea_ant.id_estado_activo_biologico = h.id_estado_anterior)))
         LEFT JOIN modulo2.estados_activos_biologicos ea_nvo ON ((ea_nvo.id_estado_activo_biologico = h.id_estado_nuevo)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = COALESCE(h.id_usuario, gf.id_usuario))))
      WHERE (gf.fecha_finalizacion IS NOT NULL);
    """)

    # =====================================================================
    # 3. VISTAS DE EVENTOS BIOLÓGICOS Y HISTORIAL (RF-39, RF-40, RF-41, RF-42, RF-43, RF-45, RF-46)
    # =====================================================================
    op.execute("""
    -- RF-39 / RF-46: Vista unificada que clasifica el tipo de evento biológico registrado.
    CREATE OR REPLACE VIEW modulo2.vw_rf39_historial_eventos_activo AS
     SELECT ea.id_eventos,
        ea.id_activo_biologico,
        ab.identificador,
        ea.fecha,
        ea.descripcion,
        ea.id_usuario,
        concat_ws(' '::text, u.nombre, u.apellidos) AS usuario_responsable,
        CASE
            WHEN (ec.id_evento IS NOT NULL) THEN 'CRECIMIENTO'::text
            WHEN (es.id_evento IS NOT NULL) THEN 'SANITARIO'::text
            WHEN (ep.id_evento IS NOT NULL) THEN 'PRODUCTIVO'::text
            WHEN (eb.id_evento IS NOT NULL) THEN 'BAJA'::text
            WHEN (er.id_evento_reproductivo IS NOT NULL) THEN 'REPRODUCTIVO'::text
            ELSE 'GENERAL'::text
        END AS tipo_evento
       FROM (((((((modulo2.eventos_activos ea
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         LEFT JOIN modulo2.eventos_crecimeinto ec ON ((ec.id_evento = ea.id_eventos)))
         LEFT JOIN modulo2.eventos_sanitarios es ON ((es.id_evento = ea.id_eventos)))
         LEFT JOIN modulo2.eventos_productivos ep ON ((ep.id_evento = ea.id_eventos)))
         LEFT JOIN modulo2.eventos_bajas eb ON ((eb.id_evento = ea.id_eventos)))
         LEFT JOIN modulo2.eventos_reproductivos er ON ((er.id_evento_reproductivo = ea.id_eventos)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)));

    -- RF-40 / RF-46: Detalle de eventos de crecimiento (peso, talla, biomasa).
    CREATE OR REPLACE VIEW modulo2.vw_rf46_eventos_crecimiento AS
     SELECT 'CRECIMIENTO'::text AS categoria,
        ea.id_eventos,
        ea.fecha,
        ea.id_activo_biologico,
        ab.identificador,
        ea.descripcion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario,
        'modulo2'::text AS modulo_origen,
        ec.tipo_medicion,
        ec.valor_medicion,
        ec.unidad_medida,
        ec.tipo_agregacion,
        ec.frecuencia
       FROM (((modulo2.eventos_activos ea
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         JOIN modulo2.eventos_crecimeinto ec ON ((ec.id_evento = ea.id_eventos)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)));

    -- RF-41 / RF-46: Detalle de eventos sanitarios (diagnóstico, tratamiento, preventivo).
    -- Se agregaron 'tipo', 'duracion' y 'observaciones' del DDL para cumplir plenamente con RF-41.
    CREATE OR REPLACE VIEW modulo2.vw_rf46_eventos_sanitarios AS
     SELECT 'SANITARIO'::text AS categoria,
        ea.id_eventos,
        ea.fecha,
        ea.id_activo_biologico,
        ab.identificador,
        ea.descripcion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario,
        'modulo2'::text AS modulo_origen,
        es.tipo,
        es.diagnostico,
        es.medicamento,
        es.dosis,
        es.unidad_dosis,
        es.frecuencia,
        es.duracion,
        es.observaciones
       FROM (((modulo2.eventos_activos ea
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         JOIN modulo2.eventos_sanitarios es ON ((es.id_evento = ea.id_eventos)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)));

    -- RF-42 / RF-46: Detalle de eventos reproductivos y relaciones genealógicas.
    CREATE OR REPLACE VIEW modulo2.vw_rf46_eventos_reproductivos AS
     SELECT 'REPRODUCTIVO'::text AS categoria,
        ea.id_eventos,
        ea.fecha,
        ea.id_activo_biologico,
        ab.identificador,
        ea.descripcion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario,
        'modulo2'::text AS modulo_origen,
        er.categoria AS categoria_reproductiva,
        er.id_padre,
        er.id_madre,
        er.resultado,
        er.numero_cria
       FROM (((modulo2.eventos_activos ea
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         JOIN modulo2.eventos_reproductivos er ON ((er.id_evento_reproductivo = ea.id_eventos)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)));

    -- RF-43 / RF-46: Detalle de eventos productivos (producción de leche, carne, huevos, etc.).
    CREATE OR REPLACE VIEW modulo2.vw_rf46_eventos_productivos AS
     SELECT 'PRODUCTIVO'::text AS categoria,
        ea.id_eventos,
        ea.fecha,
        ea.id_activo_biologico,
        ab.identificador,
        ea.descripcion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario,
        'modulo2'::text AS modulo_origen,
        ep.cantidad,
        ep.condiciones,
        ep.id_metrica_produccion,
        mp.nombre AS metrica_produccion,
        ep.id_ciclo_productivo,
        cp.nombre AS ciclo_productivo
       FROM (((((modulo2.eventos_activos ea
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         JOIN modulo2.eventos_productivos ep ON ((ep.id_evento = ea.id_eventos)))
         LEFT JOIN modulo9.metricas_produccion mp ON ((mp.id_metrica_produccion = ep.id_metrica_produccion)))
         LEFT JOIN modulo9.ciclos_productivos cp ON ((cp.id_ciclo_productivo = ep.id_ciclo_productivo)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)));

    -- RF-45 / RF-46: Detalle de eventos de baja (muerte, venta, descarte).
    CREATE OR REPLACE VIEW modulo2.vw_rf46_eventos_bajas AS
     SELECT 'BAJA'::text AS categoria,
        ea.id_eventos,
        ea.fecha,
        ea.id_activo_biologico,
        ab.identificador,
        ea.descripcion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario,
        'modulo2'::text AS modulo_origen,
        eb.tipo,
        eb.cantidad_afectada,
        eb.detalles,
        ab.id_estado
       FROM (((modulo2.eventos_activos ea
         JOIN modulo2.eventos_bajas eb ON ((eb.id_evento = ea.id_eventos)))
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)));

    -- RF-46: Historial completo unificado (UNION ALL) de TODAS las categorías de eventos del activo.
    CREATE OR REPLACE VIEW modulo2.vw_rf46_historial_completo_activo AS
     SELECT h.fecha_cambio AS fecha_evento,
        h.id_activo_biologico,
        ab.identificador,
        'ESTADO'::text AS categoria,
        (ea_ant.nombre)::text AS detalle_1,
        (ea_nvo.nombre)::text AS detalle_2,
        h.motivo_cambio AS observacion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
       FROM ((((modulo2.historicos_estados_activos h
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = h.id_activo_biologico)))
         JOIN modulo2.estados_activos_biologicos ea_ant ON ((ea_ant.id_estado_activo_biologico = h.id_estado_anterior)))
         JOIN modulo2.estados_activos_biologicos ea_nvo ON ((ea_nvo.id_estado_activo_biologico = h.id_estado_nuevo)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = h.id_usuario)))
    UNION ALL
     SELECT COALESCE(gf.fecha_finalizacion, gf.fecha_inicio) AS fecha_evento,
        gf.id_activo_biologico,
        ab.identificador,
        'FASE_PRODUCTIVA'::text AS categoria,
        (cp.nombre)::text AS detalle_1,
        CASE WHEN gf.es_activa THEN 'Activa'::text ELSE 'Finalizada'::text END AS detalle_2,
        (((('duracion_dias='::text || cp.duracion_dias) || ', es_activa='::text) || gf.es_activa) || ', fecha_finalizacion='::text) || COALESCE((gf.fecha_finalizacion)::text, 'NULL'::text) AS observacion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
       FROM (((modulo2.gestiones_fases gf
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = gf.id_activo_biologico)))
         JOIN modulo9.ciclos_productivos cp ON ((cp.id_ciclo_productivo = gf.id_ciclo_productiva)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = gf.id_usuario)))
    UNION ALL
     SELECT ea.fecha AS fecha_evento, ea.id_activo_biologico, ab.identificador, 'SANITARIO'::text AS categoria,
        es.diagnostico AS detalle_1, (es.medicamento)::text AS detalle_2, ea.descripcion AS observacion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
       FROM (((modulo2.eventos_activos ea JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         JOIN modulo2.eventos_sanitarios es ON ((es.id_evento = ea.id_eventos))) LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)))
    UNION ALL
     SELECT ea.fecha AS fecha_evento, ea.id_activo_biologico, ab.identificador, 'CRECIMIENTO'::text AS categoria,
        (ec.tipo_medicion)::text AS detalle_1, ((ec.valor_medicion || ' '::text) || (ec.unidad_medida)::text) AS detalle_2, ea.descripcion AS observacion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
       FROM (((modulo2.eventos_activos ea JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         JOIN modulo2.eventos_crecimeinto ec ON ((ec.id_evento = ea.id_eventos))) LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)))
    UNION ALL
     SELECT ea.fecha AS fecha_evento, ea.id_activo_biologico, ab.identificador, 'PRODUCTIVO'::text AS categoria,
        COALESCE(mp.nombre, ((ep.id_metrica_produccion)::text)::character varying) AS detalle_1,
        (ep.cantidad || COALESCE((' '::text || (mp.unidad_medida)::text), ''::text)) AS detalle_2, ea.descripcion AS observacion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
       FROM ((((modulo2.eventos_activos ea JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         JOIN modulo2.eventos_productivos ep ON ((ep.id_evento = ea.id_eventos)))
         LEFT JOIN modulo9.metricas_produccion mp ON ((mp.id_metrica_produccion = ep.id_metrica_produccion))) LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)))
    UNION ALL
     SELECT ea.fecha AS fecha_evento, ea.id_activo_biologico, ab.identificador, 'REPRODUCTIVO'::text AS categoria,
        (er.categoria)::text AS detalle_1, (er.resultado)::text AS detalle_2, ea.descripcion AS observacion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
       FROM (((modulo2.eventos_activos ea JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         JOIN modulo2.eventos_reproductivos er ON ((er.id_evento_reproductivo = ea.id_eventos))) LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)))
    UNION ALL
     SELECT (lower(iz.rango_fecha))::timestamp with time zone AS fecha_evento, iz.id_activo_biologico, ab.identificador, 'INDICADOR'::text AS categoria,
        (iz.tipo)::text AS detalle_1, (upper(iz.rango_fecha))::text AS detalle_2, (iz.paramtros_calculo)::text AS observacion,
        NULL::text AS usuario_responsable
       FROM (modulo2.indicadores_zootecnicos iz JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = iz.id_activo_biologico)))
    UNION ALL
     SELECT ea.fecha AS fecha_evento, ea.id_activo_biologico, ab.identificador, 'INGRESO'::text AS categoria,
        (ei.tipo)::text AS detalle_1, (ei.cantidad_ingresada)::text AS detalle_2,
        COALESCE(ea.descripcion, ei.detalles) AS observacion,
        COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario_responsable
       FROM (((modulo2.eventos_activos ea JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = ea.id_activo_biologico)))
         JOIN modulo2.eventos_ingresos ei ON ((ei.id_evento = ea.id_eventos))) LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)));
    """)

    # =====================================================================
    # 4. VISTAS DE FICHA INTEGRAL, INDICADORES E INFRAESTRUCTURA (RF-47, RF-48, RF-51)
    # =====================================================================
    op.execute("""
    -- RF-47: Ficha integral del activo, consolidando datos en tiempo real con LATERAL joins.
    CREATE OR REPLACE VIEW modulo2.vw_rf47_ficha_integral_activo AS
     SELECT ab.id_activo_biologico,
        ab.identificador AS codigo,
        ab.tipo,
        e.nombre AS especie,
        (ab.fecha_creacion)::date AS fecha_registro,
        (CURRENT_DATE - (ab.fecha_creacion)::date) AS dias_en_sistema,
        est.nombre AS estado_actual,
        i.nombre AS infraestructura_asociada,
        fase_activa.nombre AS fase_productiva_activa,
        di.raza,
        di.sexo,
        (di.fecha_nacimeinto)::date AS fecha_nacimiento,
        COALESCE(ult_peso.valor_medicion, di.peso_inicial, dp.peso_promedio) AS peso_actual,
        COALESCE(ult_peso.unidad_medida, 'kg'::character varying) AS unidad_peso,
        (ult_peso.fecha)::date AS fecha_ultimo_peso,
        dp.cantidad_actual,
        dp.biomasa_total
       FROM (((((((modulo2.activos_biologicos ab
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)))
         JOIN modulo2.estados_activos_biologicos est ON ((est.id_estado_activo_biologico = ab.id_estado)))
         JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = ab.id_infraestructura)))
         LEFT JOIN modulo2.detalles_activos_individuales di ON ((di.id_activo_biologico = ab.id_activo_biologico)))
         LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp ON ((dp.id_activo_biologico = ab.id_activo_biologico)))
         LEFT JOIN LATERAL ( SELECT cp2.nombre
                FROM (modulo2.gestiones_fases gf
                  JOIN modulo9.ciclos_productivos cp2 ON ((cp2.id_ciclo_productivo = gf.id_ciclo_productiva)))
               WHERE ((gf.id_activo_biologico = ab.id_activo_biologico) AND (gf.es_activa IS TRUE))
               ORDER BY gf.id_gestion_fases DESC
              LIMIT 1) fase_activa ON (true))
         LEFT JOIN LATERAL ( SELECT ea.fecha, ec.valor_medicion, ec.unidad_medida
                FROM (modulo2.eventos_activos ea
                  JOIN modulo2.eventos_crecimeinto ec ON ((ec.id_evento = ea.id_eventos)))
               WHERE ((ea.id_activo_biologico = ab.id_activo_biologico) AND (lower((ec.tipo_medicion)::text) ~~ '%peso%'::text))
               ORDER BY ea.fecha DESC, ea.id_eventos DESC
              LIMIT 1) ult_peso ON (true));

    -- RF-47 / RF-51: Indicadores zootécnicos calculados y almacenados por activo.
    CREATE OR REPLACE VIEW modulo2.vw_rf47_indicadores_zootecnicos_activo AS
     SELECT iz.id_indicador_zootecnico,
        iz.id_activo_biologico,
        ab.identificador AS identificador_activo,
        e.id_especie,
        e.nombre AS especie,
        iz.tipo AS tipo_indicador,
        lower(iz.rango_fecha) AS fecha_inicio,
        upper(iz.rango_fecha) AS fecha_fin,
        iz.rango_fecha,
        iz.paramtros_calculo
       FROM ((modulo2.indicadores_zootecnicos iz
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = iz.id_activo_biologico)))
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)));

    -- RF-34 / RF-48: Infraestructura actual asociada al activo.
    CREATE OR REPLACE VIEW modulo2.vw_rf48_infraestructura_actual_activo AS
     SELECT ab.id_activo_biologico,
        ab.identificador,
        ab.id_infraestructura,
        i.nombre AS infraestructura_actual
       FROM (modulo2.activos_biologicos ab
         JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = ab.id_infraestructura)));
    """)

    # =====================================================================
    # 5. VISTAS DE INTEGRACIÓN IoT Y AUDITORÍA TRANSVERSAL (RF-49, RF-50, RF-52)
    # =====================================================================
    op.execute("""
    -- RF-49: Asociaciones vigentes entre activos biológicos y sensores IoT.
    CREATE OR REPLACE VIEW modulo2.vw_rf49_asociaciones_sensores_activos AS
     SELECT aas.id_asociacion_activo_sensor,
        aas.id_sensor,
        s.nombre AS sensor,
        d.serial AS dispositivo_serial,
        i.nombre AS infraestructura_sensor,
        aas.id_usuario,
        aas.fecha_inicio,
        aas.fecha_fin,
        aas.motivo,
        aas.id_activo_biologico,
        ab.identificador,
        aas.tipo
       FROM ((((modulo2.asociaciones_activos_sensores aas
         JOIN modulo9.sensores s ON ((s.id_sensores = aas.id_sensor)))
         JOIN ( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
                d0.serial,
                d0.descripcion,
                d0.es_activo,
                d0.fecha_creacion,
                COALESCE(saa.id_infraestructura, ab_1.id_infraestructura) AS id_infraestructura
               FROM (((modulo9.dispositivos_iot d0
                 LEFT JOIN modulo9.sensores s_1 ON ((s_1.id_dispositivo_iot = d0.id_dispositivo_iot)))
                 LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s_1.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
                 LEFT JOIN modulo2.activos_biologicos ab_1 ON ((ab_1.id_dispositivo_iot = d0.id_dispositivo_iot)))
              ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d ON ((d.id_dispositivo_iot = s.id_dispositivo_iot)))
         JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = d.id_infraestructura)))
         LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = aas.id_activo_biologico)));

    -- RF-50 / RF-52: Resumen de acceso y actividad de módulos analíticos sobre el activo.
    CREATE OR REPLACE VIEW modulo2.vw_rf52_auditoria_acceso_modulos_analiticos AS
     SELECT ab.id_activo_biologico,
        ab.identificador,
        ab.tipo,
        e.nombre AS especie,
        est.nombre AS estado_actual,
        i.nombre AS infraestructura_actual,
        ab.fecha_creacion,
        count(DISTINCT ea.id_eventos) AS total_eventos,
        count(DISTINCT iz.id_indicador_zootecnico) AS total_indicadores,
        max(ea.fecha) AS fecha_ultimo_evento
       FROM (((((modulo2.activos_biologicos ab
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)))
         JOIN modulo2.estados_activos_biologicos est ON ((est.id_estado_activo_biologico = ab.id_estado)))
         JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = ab.id_infraestructura)))
         LEFT JOIN modulo2.eventos_activos ea ON ((ea.id_activo_biologico = ab.id_activo_biologico)))
         LEFT JOIN modulo2.indicadores_zootecnicos iz ON ((iz.id_activo_biologico = ab.id_activo_biologico)))
      GROUP BY ab.id_activo_biologico, ab.identificador, ab.tipo, e.nombre, est.nombre, i.nombre, ab.fecha_creacion;

    -- RF-35 / RF-52: Auditoría específica de la creación y datos de activos individuales.
    CREATE OR REPLACE VIEW modulo2.vw_rf52_auditoria_activos_individuales AS
     SELECT ab.id_activo_biologico,
        ab.identificador,
        dai.raza,
        dai.sexo,
        dai.fecha_nacimeinto AS fecha_nacimiento,
        dai.peso_inicial,
        e.nombre AS especie,
        i.nombre AS infraestructura,
        eab.nombre AS estado,
        ab.fecha_creacion,
        ab.descripcion,
        ab.id_usuario
       FROM ((((modulo2.activos_biologicos ab
         JOIN modulo2.detalles_activos_individuales dai ON ((dai.id_activo_biologico = ab.id_activo_biologico)))
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)))
         JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = ab.id_infraestructura)))
         JOIN modulo2.estados_activos_biologicos eab ON ((eab.id_estado_activo_biologico = ab.id_estado)))
      WHERE (ab.tipo = 'INDIVIDUAL'::modulo2.enum_activo_biologico_tipo);

    -- RF-33 / RF-51: Vista de auditoría de activos registrados (base para trazabilidad).
    CREATE OR REPLACE VIEW modulo2.vw_rf51_auditoria_activos_registrados AS
     SELECT ab.id_activo_biologico,
        ab.identificador,
        ab.tipo,
        e.nombre AS especie,
        i.nombre AS infraestructura,
        ab.fecha_inicio_ciclo,
        eab.nombre AS estado,
        ab.descripcion,
        ab.origen_financiero,
        ab.costo_adquisicion,
        ab.fecha_creacion,
        ab.id_usuario
       FROM (((modulo2.activos_biologicos ab
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)))
         JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = ab.id_infraestructura)))
         JOIN modulo2.estados_activos_biologicos eab ON ((eab.id_estado_activo_biologico = ab.id_estado)));

    -- RF-37 / RF-52: Auditoría de fases de ciclo productivo gestionadas.
    CREATE OR REPLACE VIEW modulo2.vw_rf52_auditoria_fases_ciclo_productivo AS
     SELECT gf.id_gestion_fases,
        gf.id_activo_biologico,
        ab.identificador AS identificador_activo,
        e.nombre AS especie,
        cp.id_ciclo_productivo,
        cp.nombre AS ciclo_productivo,
        gf.fecha_inicio,
        gf.fecha_finalizacion,
        gf.es_activa,
        gf.id_usuario,
        concat_ws(' '::text, u.nombre, u.apellidos) AS usuario_responsable
       FROM ((((modulo2.gestiones_fases gf
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = gf.id_activo_biologico)))
         JOIN modulo9.especies e ON ((e.id_especie = ab.id_especie)))
         JOIN modulo9.ciclos_productivos cp ON ((cp.id_ciclo_productivo = gf.id_ciclo_productiva)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = gf.id_usuario)));

    -- RF-48 / RF-52: Auditoría de transferencias internas entre infraestructuras.
    CREATE OR REPLACE VIEW modulo2.vw_rf52_auditoria_transferencias_internas AS
     SELECT m.id_movimiento,
        m.id_activo_biologico,
        ab.identificador,
        m.id_usuario,
        concat_ws(' '::text, u.nombre, u.apellidos) AS usuario_responsable,
        m.fecha_transferencia,
        m.tipo,
        m.id_infraestructura_origen,
        io.nombre AS infraestructura_origen,
        m.id_infraestructura_destino,
        ides.nombre AS infraestructura_destino,
        m.fecha_registro
       FROM ((((modulo2.movimientos m
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = m.id_activo_biologico)))
         JOIN modulo1.usuarios u ON ((u.id_usuario = m.id_usuario)))
         JOIN modulo9.infraestructuras io ON ((io.id_infraestructura = m.id_infraestructura_origen)))
         JOIN modulo9.infraestructuras ides ON ((ides.id_infraestructura = m.id_infraestructura_destino)));
   
    RF-35 / RF-44: Historial de cambios de estado del activo, mostrando estado anterior, nuevo, motivo y usuario responsable.
    CREATE OR REPLACE VIEW modulo2.vw_rf35_historial_estados_activo AS
     SELECT h.id_historico_estado_activo,
        h.id_activo_biologico,
        ab.identificador,
        h.id_estado_anterior,
        ea_ant.nombre AS estado_anterior,
        h.id_estado_nuevo,
        ea_nvo.nombre AS estado_nuevo,
        h.fecha_cambio,
        h.motivo_cambio,
        h.modulo_origen,
        h.id_usuario,
        concat_ws(' '::text, u.nombre, u.apellidos) AS usuario_responsable
       FROM ((((modulo2.historicos_estados_activos h
         JOIN modulo2.activos_biologicos ab ON ((ab.id_activo_biologico = h.id_activo_biologico)))
         JOIN modulo2.estados_activos_biologicos ea_ant ON ((ea_ant.id_estado_activo_biologico = h.id_estado_anterior)))
         JOIN modulo2.estados_activos_biologicos ea_nvo ON ((ea_nvo.id_estado_activo_biologico = h.id_estado_nuevo)))
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = h.id_usuario)));

    -- RF-38 / RF-39: Vista base de eventos de activos, asociando el evento con el usuario que lo registró.
    CREATE OR REPLACE VIEW modulo2.vw_rf38_eventos_activo AS
     SELECT ea.id_eventos,
        ea.id_activo_biologico,
        ea.fecha,
        ea.descripcion,
        ea.id_usuario,
        concat_ws(' '::text, u.nombre, u.apellidos) AS registrado_por
       FROM (modulo2.eventos_activos ea
         LEFT JOIN modulo1.usuarios u ON ((u.id_usuario = ea.id_usuario)));
    
    """)

    

    # =====================================================================
    # 6. COMENTARIOS DE VISTAS (Trazabilidad de Requerimientos)
    # =====================================================================
    op.execute("""
    COMMENT ON VIEW modulo2.vw_rf33_activos_biologicos_listado IS 'RF-33, RF-51: Listado general de activos biológicos con sus atributos base, especie, infraestructura y estado.';
    COMMENT ON VIEW modulo2.vw_rf34_movimientos_activo IS 'RF-34, RF-48: Historial completo de movimientos y transferencias de infraestructura de un activo, incluyendo fincas de origen y destino.';
    COMMENT ON VIEW modulo2.vw_rf35_activos_individuales IS 'RF-35: Ficha de datos específicos (raza, sexo, fecha nacimiento, peso inicial) exclusivamente para activos de tipo INDIVIDUAL.';
    COMMENT ON VIEW modulo2.vw_rf35_historial_estados_activo IS 'RF-35, RF-44: Historial de cambios de estado del activo, mostrando estado anterior, nuevo, motivo y usuario responsable.';
    COMMENT ON VIEW modulo2.vw_rf37_estado_fase_actual IS 'RF-37: Muestra únicamente la fase productiva que se encuentra actualmente ACTIVA para un activo biológico.';
    COMMENT ON VIEW modulo2.vw_rf37_fases_productivas_secuencia IS 'RF-37: Secuencia ordenada de fases productivas, mostrando el paso, duración y estado del ciclo para trazabilidad del flujo.';
    COMMENT ON VIEW modulo2.vw_rf37_historial_fases IS 'RF-37, RF-52: Historial de transiciones de fases con el usuario involucrado, permitiendo auditoría de cambios de etapa.';
    COMMENT ON VIEW modulo2.vw_rf38_eventos_activo IS 'RF-38, RF-39: Vista base de eventos de activos, asociando el evento con el usuario que lo registró.';
    COMMENT ON VIEW modulo2.vw_rf39_historial_eventos_activo IS 'RF-39, RF-46: Vista unificada que clasifica dinámicamente el tipo de evento biológico (crecimiento, sanitario, productivo, baja, reproductivo).';
    COMMENT ON VIEW modulo2.vw_rf46_eventos_bajas IS 'RF-45, RF-46: Detalle de eventos de baja, incluyendo tipo de baja, cantidad afectada y estado resultante del activo.';
    COMMENT ON VIEW modulo2.vw_rf46_eventos_crecimiento IS 'RF-40, RF-46: Detalle de mediciones de crecimiento (peso, talla, biomasa), incluyendo tipo de agregación y frecuencia.';
    COMMENT ON VIEW modulo2.vw_rf46_eventos_productivos IS 'RF-43, RF-46: Detalle de producción registrada (leche, carne, huevos), vinculada con la métrica de producción y ciclo productivo.';
    COMMENT ON VIEW modulo2.vw_rf46_eventos_reproductivos IS 'RF-42, RF-46: Detalle de eventos reproductivos, incluyendo categoría, resultados y relaciones genealógicas (padre/madre).';
    COMMENT ON VIEW modulo2.vw_rf46_eventos_sanitarios IS 'RF-41, RF-46: Detalle de intervenciones sanitarias, incluyendo diagnóstico, medicamento, dosis, frecuencia, duración y observaciones.';
    COMMENT ON VIEW modulo2.vw_rf46_historial_completo_activo IS 'RF-46: Vista maestra (UNION ALL) que consolida cronológicamente TODAS las categorías de eventos y cambios del ciclo de vida del activo.';
    COMMENT ON VIEW modulo2.vw_rf47_ficha_integral_activo IS 'RF-47: Ficha integral de solo lectura que consolida en tiempo real identificación, estado, fase, ubicación, peso actual y métricas poblacionales.';
    COMMENT ON VIEW modulo2.vw_rf47_indicadores_zootecnicos_activo IS 'RF-47, RF-51: Indicadores zootécnicos calculados y almacenados, exponiendo el rango de fecha y parámetros de cálculo.';
    COMMENT ON VIEW modulo2.vw_rf48_infraestructura_actual_activo IS 'RF-34, RF-48: Consulta rápida de la infraestructura productiva donde se encuentra actualmente el activo.';
    COMMENT ON VIEW modulo2.vw_rf49_asociaciones_sensores_activos IS 'RF-49: Asociaciones vigentes entre activos biológicos y sensores IoT, resolviendo el dispositivo y la infraestructura del sensor.';
    COMMENT ON VIEW modulo2.vw_rf51_auditoria_activos_registrados IS 'RF-33, RF-51: Vista de auditoría base de activos registrados, útil para trazabilidad de origen financiero y costos.';
    COMMENT ON VIEW modulo2.vw_rf52_auditoria_acceso_modulos_analiticos IS 'RF-50, RF-52: Resumen de actividad y acceso de módulos analíticos, contabilizando total de eventos e indicadores por activo.';
    COMMENT ON VIEW modulo2.vw_rf52_auditoria_activos_individuales IS 'RF-35, RF-52: Auditoría específica de la creación y datos base de activos de tipo INDIVIDUAL.';
    COMMENT ON VIEW modulo2.vw_rf52_auditoria_activos_poblacionales IS 'RF-36, RF-52: Auditoría específica de métricas de activos POBLACIONALES (cantidad inicial/actual, biomasa, densidad).';
    COMMENT ON VIEW modulo2.vw_rf52_auditoria_cierres_ciclo_productivo IS 'RF-38, RF-52: Auditoría de cierres de ciclo, vinculando la finalización de la fase con el cambio de estado del activo.';
    COMMENT ON VIEW modulo2.vw_rf52_auditoria_fases_ciclo_productivo IS 'RF-37, RF-52: Auditoría de la gestión de fases del ciclo productivo, mostrando usuario responsable y fechas.';
    COMMENT ON VIEW modulo2.vw_rf52_auditoria_transferencias_internas IS 'RF-48, RF-52: Auditoría de movimientos y transferencias internas, mostrando infraestructuras de origen y destino con usuario responsable.';
    COMMENT ON VIEW modulo2.vw_rf35_historial_estados_activo IS 'RF-35, RF-44: Historial de cambios de estado del activo, mostrando estado anterior, nuevo, motivo y usuario responsable.';
    COMMENT ON VIEW modulo2.vw_rf38_eventos_activo IS 'RF-38, RF-39: Vista base de eventos de activos, asociando el evento con el usuario que lo registró.';
    """)


def downgrade() -> None:
    views_to_drop = [
        'vw_rf52_auditoria_transferencias_internas',
        'vw_rf52_auditoria_fases_ciclo_productivo',
        'vw_rf52_auditoria_cierres_ciclo_productivo',
        'vw_rf52_auditoria_activos_poblacionales',
        'vw_rf52_auditoria_activos_individuales',
        'vw_rf52_auditoria_acceso_modulos_analiticos',
        'vw_rf51_auditoria_activos_registrados',
        'vw_rf49_asociaciones_sensores_activos',
        'vw_rf48_infraestructura_actual_activo',
        'vw_rf47_indicadores_zootecnicos_activo',
        'vw_rf47_ficha_integral_activo',
        'vw_rf46_historial_completo_activo',
        'vw_rf46_eventos_sanitarios',
        'vw_rf46_eventos_reproductivos',
        'vw_rf46_eventos_productivos',
        'vw_rf46_eventos_crecimiento',
        'vw_rf46_eventos_bajas',
        'vw_rf39_historial_eventos_activo',
        'vw_rf38_eventos_activo',
        'vw_rf37_historial_fases',
        'vw_rf37_fases_productivas_secuencia',
        'vw_rf37_estado_fase_actual',
        'vw_rf35_historial_estados_activo',
        'vw_rf35_activos_individuales',
        'vw_rf34_movimientos_activo',
        'vw_rf33_activos_biologicos_listado'
    ]
    
    for view in views_to_drop:
        op.execute(f"DROP VIEW IF EXISTS modulo2.{view};")