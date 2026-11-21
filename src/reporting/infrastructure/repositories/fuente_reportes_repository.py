# | Fecha      | Nombre   | Que se hizo                                                          |
# |------------|----------|----------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104/RF-106: consultas de solo lectura de reportes e historial |
# | 2026-11-19 | Arekkazu | M8-01/M8-07 RF-104/RF-106: predicciones en modo sombra y portafolio igual al NIC 41 |
"""Implementación SQLAlchemy de :class:`FuenteReportesRepository` (RF-104, RF-106).

Corre en la sesión de la instantánea (``REPEATABLE READ READ ONLY``) con la identidad de quien pidió el reporte:
la RLS de ``modulo2``/``modulo9`` ya acota lo que ve, y cada consulta filtra además por las fincas del alcance
(RF-104: «valida id_finca antes de ejecutar cualquier consulta, sin excepción»).

Mismas fuentes que las pantallas de cada módulo: los gastos como el detalle de M05, el valor del inventario como
M06 (último cálculo de valor razonable o, si el activo va por costo, su valor contable), la exportación contable
como M07 (solicitudes de integración y metadatos de respuesta).
"""
from __future__ import annotations

import os
from typing import Any, Optional

from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from src.financial_valuation.infrastructure.repositories.sql import alcance_titular, nombres_usuarios
from src.reporting.domain.repositories.fuente_reportes_repository import Fila, Fincas, FuenteReportesRepository
from src.shared.almacen_logos import DIRECTORIO_LOGOS, RUTA_PUBLICA_LOGOS
from src.shared.database import como_sistema
from src.shared.fechas import nombre_zona_usuario
from src.shared.nombre_activo import nombre_activo_sql

_NOMBRE = nombre_activo_sql("ab")
_SINIGAN = ("NULLIF(btrim(COALESCE(ab.atributos_dinamicos->>'sinigan', ab.atributos_dinamicos->>'identificacion_sinigan',"
            " ab.atributos_dinamicos->>'codigo_sinigan')), '')")
_ACTIVO = """
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
    JOIN modulo9.fincas f ON f.id_finca = i.id_finca
    LEFT JOIN modulo9.especies e ON e.id_especie = ab.id_especie"""
_EN_FINCAS = "(CAST(:fincas AS integer[]) IS NULL OR i.id_finca = ANY(:fincas))"
_ESPECIE = "(CAST(:especie AS integer) IS NULL OR ab.id_especie = :especie)"
_ACTIVO_ID = "(CAST(:activo AS integer) IS NULL OR ab.id_activo_biologico = :activo)"
_INFRA = "(CAST(:infra AS integer) IS NULL OR i.id_infraestructura = :infra)"
_ESTADO = "LEFT JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = ab.id_estado"
_FUERA = "('BAJA', 'CERRADO')"  # estados que ya no cuentan en el inventario
_POBLACION = ("LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp "
              "ON dp.id_activo_biologico = ab.id_activo_biologico")
# Valor del activo al cierre de un día: último cálculo de valor razonable y, si va por costo, su valor contable.
_VALOR_AL = """
    LEFT JOIN LATERAL (
        SELECT c.valor_neto FROM modulo6.calculos_valor_razonable c
        WHERE c.id_activo_biologico = ab.id_activo_biologico AND (c.fecha_calculo AT TIME ZONE :tz)::date <= {dia}
        ORDER BY c.fecha_calculo DESC LIMIT 1) vr ON true
    LEFT JOIN LATERAL (
        SELECT v.valor_contable_por_costo AS valor FROM modulo6.valoraciones_por_costos v
        WHERE v.id_activo_biologico = ab.id_activo_biologico AND (v.fecha_marcacion AT TIME ZONE :tz)::date <= {dia}
        ORDER BY v.es_activa DESC, v.fecha_marcacion DESC LIMIT 1) vc ON true"""

# Última baja del activo (tipo y fecha).
_BAJA = """
    LEFT JOIN LATERAL (
        SELECT eb.tipo::text AS tipo, ea.fecha FROM modulo2.eventos_bajas eb
        JOIN modulo2.eventos_activos ea ON ea.id_eventos = eb.id_evento
        WHERE ea.id_activo_biologico = ab.id_activo_biologico ORDER BY ea.fecha DESC LIMIT 1) bj ON true"""

_SQL_UBICAR = {
    "activo": text("SELECT ab.id_activo_biologico AS id, i.id_finca, ab.tipo::text AS tipo, est.nombre AS estado "
                   f"FROM modulo2.activos_biologicos ab {_ACTIVO} {_ESTADO} WHERE ab.id_activo_biologico = :id"),
    "infraestructura": text("SELECT id_infraestructura AS id, id_finca FROM modulo9.infraestructuras "
                            "WHERE id_infraestructura = :id"),
    "sensor": text("SELECT s.id_sensores AS id, i.id_finca FROM modulo9.sensores s "
                   "JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = s.id_dispositivo_iot "
                   "JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura "
                   "WHERE s.id_sensores = :id"),
    "finca": text("SELECT id_finca AS id, id_finca FROM modulo9.fincas WHERE id_finca = :id"),
    "especie": text("SELECT id_especie AS id, NULL::integer AS id_finca FROM modulo9.especies WHERE id_especie = :id"),
}

_SQL_NOMBRE_REFERENCIA = {
    "finca": text("SELECT nombre FROM modulo9.fincas WHERE id_finca = :id"),
    "especie": text("SELECT nombre FROM modulo9.especies WHERE id_especie = :id"),
    "activo": text(f"SELECT {_NOMBRE} FROM modulo2.activos_biologicos ab WHERE ab.id_activo_biologico = :id"),
    "infraestructura": text("SELECT i.nombre || ' · ' || f.nombre FROM modulo9.infraestructuras i "
                            "JOIN modulo9.fincas f ON f.id_finca = i.id_finca WHERE i.id_infraestructura = :id"),
    "sensor": text("SELECT COALESCE(s.nombre, 'Sensor') || ' · ' || d.serial FROM modulo9.sensores s "
                   "JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = s.id_dispositivo_iot "
                   "WHERE s.id_sensores = :id"),
}

_SQL_OPCIONES = {
    "finca": text("SELECT f.id_finca AS valor, f.nombre AS etiqueta FROM modulo9.fincas f "
                  "WHERE CAST(:fincas AS integer[]) IS NULL OR f.id_finca = ANY(:fincas) ORDER BY f.nombre"),
    "especie": text("SELECT id_especie AS valor, nombre AS etiqueta FROM modulo9.especies WHERE es_activo ORDER BY nombre"),
    "activo": text(f"""SELECT ab.id_activo_biologico AS valor, {_NOMBRE} || ' · ' || COALESCE(e.nombre, '') AS etiqueta
                       FROM modulo2.activos_biologicos ab {_ACTIVO} WHERE {_EN_FINCAS}
                       ORDER BY 2 LIMIT 1000"""),
    "lote": text(f"""SELECT ab.id_activo_biologico AS valor, {_NOMBRE} || ' · ' || COALESCE(e.nombre, '') AS etiqueta
                     FROM modulo2.activos_biologicos ab {_ACTIVO}
                     WHERE {_EN_FINCAS} AND ab.tipo::text = 'POBLACIONAL' ORDER BY 2 LIMIT 1000"""),
    "infraestructura": text(f"""SELECT i.id_infraestructura AS valor, i.nombre || ' · ' || f.nombre AS etiqueta
                                FROM modulo9.infraestructuras i JOIN modulo9.fincas f ON f.id_finca = i.id_finca
                                WHERE i.es_activo AND {_EN_FINCAS} ORDER BY 2"""),
    "sensor": text(f"""SELECT s.id_sensores AS valor, COALESCE(s.nombre, 'Sensor') || ' · ' || d.serial AS etiqueta
                       FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = s.id_dispositivo_iot
                       JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
                       WHERE s.es_activo AND {_EN_FINCAS} ORDER BY 2"""),
    "periodo": text(f"""SELECT pc.id_periodo_contable AS valor,
                              to_char(pc.fecha_inicio, 'DD/MM/YYYY') || ' a ' || to_char(pc.fecha_fin, 'DD/MM/YYYY')
                              || CASE pc.estado::text WHEN 'CERRADO' THEN ' · cerrado' WHEN 'ABIERTO' THEN ' · abierto'
                                 ELSE ' · en cierre' END
                              -- M8-09: de quién es cada período (varios titulares tienen el mismo mes)
                              || ' · ' || COALESCE((SELECT min(f.razon_social) FROM modulo9.fincas f
                                                    WHERE f.numero_id_tributaria = pc.numero_id_tributaria),
                                                   'NIT ' || pc.numero_id_tributaria, 'Sin titular registrado')
                              AS etiqueta,
                              pc.estado::text AS estado
                       FROM modulo6.periodos_contables pc
                       WHERE {alcance_titular('pc.numero_id_tributaria')}
                         AND (CAST(:fincas AS integer[]) IS NULL OR pc.numero_id_tributaria IN (
                              SELECT f.numero_id_tributaria FROM modulo9.fincas f WHERE f.id_finca = ANY(:fincas)))
                       ORDER BY pc.fecha_fin DESC LIMIT 120"""),
}

_SQL_PERIODO = text(f"""
    SELECT pc.id_periodo_contable, pc.fecha_inicio, pc.fecha_fin, pc.estado::text AS estado,
           pc.numero_id_tributaria AS nit, {alcance_titular('pc.numero_id_tributaria')} AS accesible
    FROM modulo6.periodos_contables pc WHERE pc.id_periodo_contable = :id
""")

_SQL_FINCAS = text("""
    SELECT f.id_finca, f.nombre, f.razon_social, f.numero_id_tributaria AS nit, f.dv
    FROM modulo9.fincas f WHERE CAST(:fincas AS integer[]) IS NULL OR f.id_finca = ANY(:fincas)
    ORDER BY f.nombre
""")

_SQL_FINCAS_TITULAR = text("""
    SELECT f.id_finca FROM modulo9.fincas f
    WHERE f.numero_id_tributaria = :nit AND (CAST(:fincas AS integer[]) IS NULL OR f.id_finca = ANY(:fincas))
""")

_SQL_LOGO = text("SELECT logo_path FROM modulo9.identidad_visuales WHERE id_finca = :f AND logo_path IS NOT NULL "
                 "ORDER BY version DESC LIMIT 1")

_SQL_INVENTARIO = text(f"""
    SELECT ab.id_activo_biologico, {_NOMBRE} AS identificador, e.nombre AS especie, di.raza, {_SINIGAN} AS sinigan,
           est.nombre AS estado, bj.tipo AS tipo_baja, ab.fecha_inicio_ciclo AS fecha_ingreso, ab.tipo::text AS tipo_activo,
           COALESCE(pe.peso, di.peso_inicial, dp.peso_promedio) AS peso_kg, cp.nombre AS etapa,
           COALESCE(dp.cantidad_actual, 1) AS cantidad,
           CASE WHEN vr.valor_neto IS NULL AND vc.valor IS NOT NULL THEN 'VALORACION_POR_COSTO'
                WHEN vr.valor_neto IS NOT NULL THEN 'VALOR_RAZONABLE' END AS metodo,
           COALESCE(vr.valor_neto, vc.valor) AS valor, f.nombre AS finca, i.id_finca
    FROM modulo2.activos_biologicos ab {_ACTIVO} {_ESTADO} {_POBLACION}
    LEFT JOIN modulo2.detalles_activos_individuales di ON di.id_activo_biologico = ab.id_activo_biologico
    {_BAJA}
    LEFT JOIN LATERAL (
        SELECT CASE WHEN ab.tipo::text = 'POBLACIONAL' THEN COALESCE(ec.nuevo_peso_promedio, ec.valor_medicion)
                    ELSE COALESCE(ec.valor_medicion, ec.nuevo_peso_promedio) END AS peso
        FROM modulo2.eventos_crecimeinto ec JOIN modulo2.eventos_activos ea ON ea.id_eventos = ec.id_evento
        WHERE ea.id_activo_biologico = ab.id_activo_biologico AND ec.tipo_medicion = 'PESO' AND ea.fecha <= :hasta
        ORDER BY ea.fecha DESC LIMIT 1) pe ON true
    LEFT JOIN LATERAL (
        SELECT cp.nombre FROM modulo2.gestiones_fases g
        JOIN modulo9.ciclos_productivos cp ON cp.id_ciclo_productivo = g.id_ciclo_productiva
        WHERE g.id_activo_biologico = ab.id_activo_biologico ORDER BY g.es_activa DESC, g.fecha_inicio DESC LIMIT 1
    ) cp ON true
    {_VALOR_AL.format(dia=':fin')}
    WHERE {_EN_FINCAS} AND {_ESPECIE}
      AND COALESCE(ab.fecha_inicio_ciclo, (ab.fecha_creacion AT TIME ZONE :tz)::date) <= :fin
      AND (bj.fecha IS NULL OR COALESCE(est.nombre, '') NOT IN {_FUERA} OR (bj.fecha AT TIME ZONE :tz)::date >= :inicio)
      AND (CAST(:estado AS text) IS NULL
           OR (:estado = 'ACTIVO' AND COALESCE(est.nombre, '') NOT IN {_FUERA})
           OR (:estado = 'VENDIDO' AND est.nombre = 'BAJA' AND bj.tipo = 'venta')
           OR (:estado = 'MUERTO' AND est.nombre = 'BAJA' AND bj.tipo = 'muerte'))
    ORDER BY f.nombre, e.nombre, identificador
""")

# Mismas reglas que el detalle de gastos de M05; OTROS = suministros del libro que no son alimento ni medicamento.
_SQL_COSTOS = text(f"""
    SELECT s.tipo, s.nombre, s.cantidad, s.unidad, s.costo_unitario, s.costo_total, s.fecha,
           {_NOMBRE} AS identificador, e.nombre AS especie, f.nombre AS finca, i.id_finca
    FROM (
        SELECT 'ALIMENTACION' AS tipo, COALESCE(ta.nombre, rca.tipo_alimento) AS nombre,
               rca.cantidad_suministrada AS cantidad, COALESCE(rca.tipo_unidad, ta.unidad_medida) AS unidad,
               rca.costo_unitario, rca.costo_total,
               COALESCE(rca.fecha_consumo, (rca.fecha_registro AT TIME ZONE :tz)::date) AS fecha, rca.id_activo_biologico
        FROM modulo5.registros_consumo_alimentos rca
        LEFT JOIN modulo5.tipos_alimentos ta ON ta.id_tipo_elemento = rca.id_tipo_alimento
        WHERE rca.estado_registro = 'VALIDADO'
        UNION ALL
        SELECT 'MEDICACION', rm.nombre_medicamento, rm.cantidad, rm.unidad_dosis, rm.costo_unitario_medicamento,
               rm.costo_total_medicamento, rm.fecha_aplicacion, rm.id_activo_biologico
        FROM modulo5.registros_medicamentos rm WHERE rm.estado_registro = 'VALIDADO'
        UNION ALL
        SELECT 'OTROS', COALESCE(NULLIF(btrim(rs.observacion), ''), initcap(replace(lower(rs.tipo_suministro), '_', ' ')),
                                 'Otro suministro'),
               rs.cantidad, rs.unidad_medida, rs.precio_unitario_resuelto, rs.costo_registro, rs.fecha_aplicacion,
               rs.id_activo_biologico
        FROM modulo5.registro_suministro rs
        WHERE COALESCE(rs.tipo_suministro, '') NOT IN ('ALIMENTO', 'MEDICAMENTO')
          AND rs.id_registro_rf75 IS NULL AND rs.id_registro_rf76 IS NULL
          AND COALESCE(rs.tipo_operacion, 'REGISTRO') <> 'ANULACION'
          AND NOT EXISTS (SELECT 1 FROM modulo5.registro_suministro c
                          WHERE c.id_registro_original = rs.id_registro_suministro)
    ) s
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = s.id_activo_biologico {_ACTIVO}
    WHERE (CAST(:inicio AS date) IS NULL OR s.fecha >= :inicio) AND s.fecha <= :fin
      AND {_EN_FINCAS} AND {_ESPECIE} AND {_ACTIVO_ID} AND (CAST(:tipo AS text) IS NULL OR s.tipo = :tipo)
    ORDER BY s.tipo, s.fecha, s.nombre
""")

_SQL_PRODUCCION = text(f"""
    SELECT m.id_activo_biologico, {_NOMBRE} AS identificador, ab.tipo::text AS tipo_activo, e.nombre AS especie,
           COALESCE(dp.cantidad_actual, 1) AS numero_animales, m.tipo_metrica, m.metrica, m.unidad, m.valor, m.fecha,
           gf.etapa, f.nombre AS finca
    FROM (
        SELECT ea.id_activo_biologico, COALESCE(mp.tipo_medicion, 'CONTEO') AS tipo_metrica,
               COALESCE(mp.nombre, 'Producción') AS metrica, mp.unidad_medida AS unidad, ep.cantidad AS valor, ea.fecha
        FROM modulo2.eventos_productivos ep JOIN modulo2.eventos_activos ea ON ea.id_eventos = ep.id_evento
        LEFT JOIN modulo9.metricas_produccion mp ON mp.id_metrica_produccion = ep.id_metrica_produccion
        UNION ALL
        SELECT ea.id_activo_biologico, 'PESO', 'Peso', COALESCE(ec.unidad_medida, 'kg'),
               COALESCE(ec.nuevo_peso_promedio, ec.valor_medicion), ea.fecha
        FROM modulo2.eventos_crecimeinto ec JOIN modulo2.eventos_activos ea ON ea.id_eventos = ec.id_evento
        WHERE ec.tipo_medicion = 'PESO'
    ) m
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = m.id_activo_biologico {_ACTIVO} {_POBLACION}
    LEFT JOIN LATERAL (
        SELECT cp.nombre AS etapa FROM modulo2.gestiones_fases g
        JOIN modulo9.ciclos_productivos cp ON cp.id_ciclo_productivo = g.id_ciclo_productiva
        WHERE g.id_activo_biologico = ab.id_activo_biologico AND g.fecha_inicio <= m.fecha
          AND (g.fecha_finalizacion IS NULL OR g.fecha_finalizacion >= m.fecha)
        ORDER BY g.fecha_inicio DESC LIMIT 1) gf ON true
    WHERE (CAST(:desde AS timestamptz) IS NULL OR m.fecha >= :desde) AND m.fecha <= :hasta
      AND {_EN_FINCAS} AND {_ESPECIE} AND {_ACTIVO_ID}
    ORDER BY f.nombre, e.nombre, identificador, m.metrica, m.fecha
""")

_SQL_CONVERSION = text(f"""
    SELECT {_NOMBRE} AS identificador, e.nombre AS especie, ri.fecha_inicio_periodo, ri.fecha_fin_periodo,
           ri.alimento_consumido_total_kg, ri.ganancia_peso_kg, ri.ca_calculado, f.nombre AS finca
    FROM modulo5.resultado_ica ri
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ri.id_activo_biologico {_ACTIVO}
    WHERE ri.es_vigente AND ri.fecha_fin_periodo >= :inicio AND ri.fecha_inicio_periodo <= :fin
      AND {_EN_FINCAS} AND {_ESPECIE} AND {_ACTIVO_ID}
    ORDER BY f.nombre, identificador, ri.fecha_inicio_periodo
""")

# Bajas de M02 y traslados a otra finca (salidas de M02 cuyo destino es un área de otra finca).
_SQL_SALIDAS = text(f"""
    SELECT s.id_activo_biologico, {_NOMBRE} AS identificador, {_SINIGAN} AS sinigan, e.nombre AS especie, s.tipo,
           s.fecha, s.motivo, s.valor_venta, s.destino, s.cantidad, fo.nombre AS finca, vr.valor_neto AS valor_referencia
    FROM (
        SELECT ea.id_activo_biologico, upper(eb.tipo::text) AS tipo, ea.fecha, NULLIF(btrim(eb.detalles), '') AS motivo,
               eb.valor_venta, NULLIF(btrim(eb.referencia_venta), '') AS destino, eb.cantidad_afectada AS cantidad,
               NULL::integer AS id_finca_origen
        FROM modulo2.eventos_bajas eb JOIN modulo2.eventos_activos ea ON ea.id_eventos = eb.id_evento
        UNION ALL
        SELECT mv.id_activo_biologico, 'TRASLADO', mv.fecha_transferencia, NULLIF(btrim(mv.motivo_transferencia), ''),
               NULL, fd.nombre, NULL, io.id_finca
        FROM modulo2.movimientos mv
        JOIN modulo9.infraestructuras io ON io.id_infraestructura = mv.id_infraestructura_origen
        JOIN modulo9.infraestructuras idest ON idest.id_infraestructura = mv.id_infraestructura_destino
        JOIN modulo9.fincas fd ON fd.id_finca = idest.id_finca
        WHERE mv.tipo::text = 'salida' AND io.id_finca <> idest.id_finca
    ) s
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = s.id_activo_biologico {_ACTIVO}
    JOIN modulo9.fincas fo ON fo.id_finca = COALESCE(s.id_finca_origen, i.id_finca)
    LEFT JOIN LATERAL (
        SELECT c.valor_neto FROM modulo6.calculos_valor_razonable c
        JOIN modulo6.periodos_contables pc ON pc.id_periodo_contable = c.id_periodo_contable
        WHERE c.id_activo_biologico = ab.id_activo_biologico AND pc.estado = 'CERRADO'
          AND pc.fecha_fin <= (s.fecha AT TIME ZONE :tz)::date
        ORDER BY pc.fecha_fin DESC, c.fecha_calculo DESC LIMIT 1) vr ON true
    WHERE s.fecha BETWEEN :desde AND :hasta AND {_ESPECIE}
      AND (CAST(:fincas AS integer[]) IS NULL OR fo.id_finca = ANY(:fincas))
    ORDER BY s.fecha, identificador
""")

_SQL_VALORACION_PERIODO = text(f"""
    SELECT ab.id_activo_biologico, {_NOMBRE} AS identificador, {_SINIGAN} AS sinigan, e.nombre AS especie,
           CASE WHEN vr.valor_neto IS NULL THEN 'VALORACION_POR_COSTO' ELSE 'VALOR_RAZONABLE' END AS metodo,
           vr.valor_neto AS valor_razonable, vc.valor AS costo_atribuido, COALESCE(va.total, 0) AS variacion,
           f.nombre AS finca
    FROM modulo6.periodos_contables p
    JOIN modulo2.activos_biologicos ab ON true {_ACTIVO}
    {_VALOR_AL.format(dia='p.fecha_fin')}
    LEFT JOIN LATERAL (
        SELECT sum(vv.monto_variacion) AS total FROM modulo6.variaciones_valor_razonable vv
        WHERE vv.id_activo_biologico = ab.id_activo_biologico AND vv.id_periodo_contable = p.id_periodo_contable
    ) va ON true
    WHERE p.id_periodo_contable = :periodo AND i.id_finca = ANY(:fincas)
      AND (vr.valor_neto IS NOT NULL OR vc.valor IS NOT NULL)
    ORDER BY f.nombre, e.nombre, identificador
""")

# Solicitudes de la integración contable del período: estado, confirmación, hash y monto del paquete.
_SQL_EXPORTACIONES = text("""
    SELECT s.id_integracion_solicitud, s.estado::text AS estado, s.fecha_comienzoo AS fecha_envio,
           s.fecha_finalizacion AS fecha_confirmacion, m.identificador_de_cambio AS confirmacion,
           m.sha256_sobre AS hash_paquete, (m.resumen->>'total_monto')::numeric AS monto,
           COALESCE((m.resumen->>'documentos_generados')::integer, d.total) AS activos, d.fallidos,
           ce.mensaje AS error
    FROM modulo7.integraciones_solicitudes s
    LEFT JOIN LATERAL (
        SELECT * FROM modulo7.metadatos_respuesta_aaef mr WHERE mr.id_integracion_solicitud = s.id_integracion_solicitud
        ORDER BY mr.fecha_creacion DESC LIMIT 1) m ON true
    LEFT JOIN modulo7.catalogo_errores_de_integracion ce ON ce.id_catalogo_error = s.id_error
    LEFT JOIN LATERAL (
        SELECT count(*) AS total, count(*) FILTER (WHERE dg.estado::text <> 'GENERATED') AS fallidos
        FROM modulo7.documentos_generados_aaef dg WHERE dg.id_integracion_solicitud = s.id_integracion_solicitud) d ON true
    WHERE s.id_periodo_contable = :periodo
    ORDER BY s.fecha_comienzoo
""")

_SQL_VARIACION = text(f"""
    SELECT ab.id_activo_biologico, {_NOMBRE} AS identificador, e.nombre AS especie, f.nombre AS finca,
           vb.valor_neto AS base_vr, cb.valor AS base_costo, vcmp.valor_neto AS comp_vr, ccmp.valor AS comp_costo,
           (bj.fecha IS NOT NULL AND (bj.fecha AT TIME ZONE :tz)::date <= pb.fecha_fin) AS dado_de_baja,
           EXISTS (SELECT 1 FROM modulo6.deterioros_activos d
                   JOIN modulo6.valoraciones_por_costos v ON v.id_valoracion_por_costo = d.id_valoracion_por_costo
                   WHERE v.id_activo_biologico = ab.id_activo_biologico
                     AND (d.fecha_registro AT TIME ZONE :tz)::date > pc.fecha_fin
                     AND (d.fecha_registro AT TIME ZONE :tz)::date <= pb.fecha_fin) AS deterioro
    FROM modulo6.periodos_contables pb
    JOIN modulo6.periodos_contables pc ON pc.id_periodo_contable = :comparacion
    JOIN modulo2.activos_biologicos ab ON true {_ACTIVO} {_BAJA}
    LEFT JOIN LATERAL (SELECT c.valor_neto FROM modulo6.calculos_valor_razonable c
        WHERE c.id_activo_biologico = ab.id_activo_biologico AND (c.fecha_calculo AT TIME ZONE :tz)::date <= pb.fecha_fin
        ORDER BY c.fecha_calculo DESC LIMIT 1) vb ON true
    LEFT JOIN LATERAL (SELECT c.valor_neto FROM modulo6.calculos_valor_razonable c
        WHERE c.id_activo_biologico = ab.id_activo_biologico AND (c.fecha_calculo AT TIME ZONE :tz)::date <= pc.fecha_fin
        ORDER BY c.fecha_calculo DESC LIMIT 1) vcmp ON true
    LEFT JOIN LATERAL (SELECT v.valor_contable_por_costo AS valor FROM modulo6.valoraciones_por_costos v
        WHERE v.id_activo_biologico = ab.id_activo_biologico AND (v.fecha_marcacion AT TIME ZONE :tz)::date <= pb.fecha_fin
        ORDER BY v.fecha_marcacion DESC LIMIT 1) cb ON true
    LEFT JOIN LATERAL (SELECT v.valor_contable_por_costo AS valor FROM modulo6.valoraciones_por_costos v
        WHERE v.id_activo_biologico = ab.id_activo_biologico AND (v.fecha_marcacion AT TIME ZONE :tz)::date <= pc.fecha_fin
        ORDER BY v.fecha_marcacion DESC LIMIT 1) ccmp ON true
    WHERE pb.id_periodo_contable = :base AND i.id_finca = ANY(:fincas)
      AND COALESCE(vb.valor_neto, cb.valor, vcmp.valor_neto, ccmp.valor) IS NOT NULL
    ORDER BY f.nombre, e.nombre, identificador
""")

# Eventos sanitarios de M02 y predicciones de M04 (riesgo bajo o mayor) del animal, en un solo listado.
_SQL_SANITARIOS = text(f"""
    SELECT s.*, {_NOMBRE} AS identificador, {_SINIGAN} AS sinigan, e.nombre AS especie, f.nombre AS finca
    FROM (
        SELECT ea.id_activo_biologico, 'M02' AS fuente, es.tipo::text AS tipo, ea.fecha,
               NULLIF(btrim(COALESCE(es.diagnostico, ea.descripcion)), '') AS descripcion,
               NULLIF(btrim(es.medicamento), '') AS medicamento, es.dosis, es.unidad_dosis,
               NULLIF(btrim(es.frecuencia::text), '') AS frecuencia, NULLIF(btrim(es.duracion::text), '') AS duracion,
               NULLIF(btrim(es.observaciones), '') AS resultado, ea.id_usuario AS id_veterinario,
               (SELECT r.nivel_riesgo FROM modulo4.resultados_inferencia r
                WHERE r.id_activo_biologico = ea.id_activo_biologico
                  AND r.fecha_inferencia BETWEEN ea.fecha - interval '7 days' AND ea.fecha
                ORDER BY r.fecha_inferencia DESC LIMIT 1) AS nivel_riesgo, NULL::numeric AS confianza,
               ea.id_eventos AS id_evento
        FROM modulo2.eventos_sanitarios es JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
        UNION ALL
        SELECT r.id_activo_biologico, 'M04', 'PREDICCION', r.fecha_inferencia, pt.nombre, NULL, NULL, NULL, NULL, NULL,
               rc.estado, rc.id_usuario_veterinario, r.nivel_riesgo, r.confianza_global, NULL::integer
        FROM modulo4.resultados_inferencia r
        LEFT JOIN modulo9.patologias pt ON pt.id_patologia = r.id_patologia
        LEFT JOIN LATERAL (
            SELECT rcl.estado_retroalimentacion::text AS estado, rcl.id_usuario_veterinario
            FROM modulo4.retroalimentaciones_clinicas rcl WHERE rcl.id_resultado_inferencia = r.id_resultado_inferencia
            ORDER BY rcl.fecha_retroalimentacion DESC LIMIT 1) rc ON true
        WHERE r.nivel_riesgo >= 1
    ) s
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = s.id_activo_biologico {_ACTIVO}
    WHERE (CAST(:desde AS timestamptz) IS NULL OR s.fecha >= :desde) AND s.fecha <= :hasta
      AND {_EN_FINCAS} AND {_ESPECIE} AND {_ACTIVO_ID}
    ORDER BY s.fecha, identificador
""")

_SQL_FICHA = text(f"""
    SELECT ab.id_activo_biologico, {_NOMBRE} AS identificador, {_SINIGAN} AS sinigan, e.nombre AS especie, di.raza,
           di.sexo, di.fecha_nacimeinto AS fecha_nacimiento, ab.fecha_inicio_ciclo AS fecha_ingreso,
           ab.id_usuario AS id_propietario, f.nombre AS finca, i.nombre AS area, ab.tipo::text AS tipo_activo,
           est.nombre AS estado, COALESCE(dp.cantidad_actual, 1) AS cantidad, i.id_finca
    FROM modulo2.activos_biologicos ab {_ACTIVO} {_ESTADO} {_POBLACION}
    LEFT JOIN modulo2.detalles_activos_individuales di ON di.id_activo_biologico = ab.id_activo_biologico
    WHERE ab.id_activo_biologico = :activo
""")

_SQL_VALORACION_ACTIVO = text(f"""
    SELECT pc.fecha_inicio, pc.fecha_fin, vr.valor_neto AS valor_razonable, vc.valor AS costo
    FROM modulo2.activos_biologicos ab {_ACTIVO}
    JOIN modulo6.periodos_contables pc ON pc.numero_id_tributaria = f.numero_id_tributaria AND pc.estado = 'CERRADO'
    {_VALOR_AL.format(dia='pc.fecha_fin')}
    WHERE ab.id_activo_biologico = :activo AND (vr.valor_neto IS NOT NULL OR vc.valor IS NOT NULL)
    ORDER BY pc.fecha_fin
""")

# «Activa»: la última predicción del animal en los últimos 7 días, si es de riesgo bajo o mayor.
_SQL_PREDICCIONES = text(f"""
    SELECT * FROM (
        SELECT DISTINCT ON (r.id_activo_biologico) r.id_activo_biologico, {_NOMBRE} AS identificador,
               {_SINIGAN} AS sinigan, e.nombre AS especie, r.nivel_riesgo, pt.nombre AS condicion, r.confianza_global,
               r.probabilidad_enfermedad, r.probabilidad_riesgo, r.fecha_inferencia, al.accion_sugerida, f.nombre AS finca
        FROM modulo4.resultados_inferencia r
        JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = r.id_activo_biologico {_ACTIVO}
        LEFT JOIN modulo9.patologias pt ON pt.id_patologia = r.id_patologia
        LEFT JOIN modulo3.alertas al ON al.id_alerta = r.id_alerta_generada
        WHERE r.fecha_inferencia >= now() - interval '7 days'
          AND (CAST(:desde AS timestamptz) IS NULL OR r.fecha_inferencia >= :desde)
          AND {_EN_FINCAS} AND {_ESPECIE} AND {_ACTIVO_ID}
        ORDER BY r.id_activo_biologico, r.fecha_inferencia DESC
    ) p WHERE p.nivel_riesgo >= 1
    ORDER BY p.nivel_riesgo DESC, p.confianza_global DESC NULLS LAST
""")

_SQL_MEDICAMENTOS = text(f"""
    SELECT s.*, {_NOMBRE} AS identificador, e.nombre AS especie, f.nombre AS finca, COALESCE(dp.cantidad_actual, 1) AS animales
    FROM (
        SELECT rm.id_activo_biologico, rm.nombre_medicamento AS nombre, rm.via_aplicacion AS via,
               rm.lote_medicameto AS lote, rm.fehca_vencimietno_lote AS vencimiento,
               COALESCE(rm.dosis_por_individuo, rm.cantidad) AS dosis, rm.unidad_dosis, rm.fecha_aplicacion,
               NULLIF(btrim(rm.nombre_veterinario), '') AS veterinario, rm.id_usuario_veterinario AS id_veterinario,
               rm.periodo_retiro_dias, rm.fecha_fin_retiro,
               CASE WHEN es.tipo::text = 'VACUNACION' THEN 'VACUNA'
                    WHEN strpos(lower(rm.nombre_medicamento || ' ' || COALESCE(rm.motivo_aplicacion, '')), 'parasit') > 0
                    THEN 'ANTIPARASITARIO' ELSE 'MEDICAMENTO' END AS tipo_insumo
        FROM modulo5.registros_medicamentos rm
        LEFT JOIN modulo2.eventos_sanitarios es ON es.id_evento = rm.id_evento_sanitario
        WHERE rm.estado_registro = 'VALIDADO'
        UNION ALL
        SELECT ea.id_activo_biologico, COALESCE(NULLIF(btrim(es.medicamento), ''), 'Vacuna'), NULL, NULL, NULL,
               es.dosis, es.unidad_dosis, (ea.fecha AT TIME ZONE :tz)::date, NULL, ea.id_usuario, NULL, NULL, 'VACUNA'
        FROM modulo2.eventos_sanitarios es JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
        WHERE es.tipo::text = 'VACUNACION'
          AND NOT EXISTS (SELECT 1 FROM modulo5.registros_medicamentos rm2 WHERE rm2.id_evento_sanitario = es.id_evento)
    ) s
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = s.id_activo_biologico {_ACTIVO} {_POBLACION}
    WHERE s.fecha_aplicacion BETWEEN :inicio AND :fin AND {_EN_FINCAS} AND {_ESPECIE} AND {_ACTIVO_ID}
    ORDER BY s.fecha_aplicacion, s.nombre
""")

_SQL_RETIROS = text(f"""
    SELECT {_NOMBRE} AS identificador, e.nombre AS especie, rm.nombre_medicamento AS medicamento,
           rm.fecha_aplicacion, rm.fecha_fin_retiro, f.nombre AS finca
    FROM modulo5.registros_medicamentos rm
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = rm.id_activo_biologico {_ACTIVO} {_ESTADO}
    WHERE rm.estado_registro = 'VALIDADO' AND rm.fecha_fin_retiro >= :hoy AND COALESCE(est.nombre, '') NOT IN {_FUERA}
      AND {_EN_FINCAS} AND {_ESPECIE} AND {_ACTIVO_ID}
    ORDER BY rm.fecha_fin_retiro, identificador
""")

_SQL_TELEMETRIA = text("""
    SELECT t.id_sensor, s.nombre AS sensor, v.nombre AS variable, COALESCE(t.valor_ajustado, t.valor_crudo) AS valor,
           COALESCE(NULLIF(t.unidad_medida, ''), v.unidad) AS unidad, t.timestamp_captura, est.estado,
           i.nombre AS area, f.nombre AS finca
    FROM modulo3.telemetrias t
    JOIN modulo9.sensores s ON s.id_sensores = t.id_sensor
    JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = t.id_dispositivo_iot
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
    JOIN modulo9.fincas f ON f.id_finca = i.id_finca
    LEFT JOIN modulo9.variables_ambientales v ON v.id_variable_ambiental = t.id_variable
    LEFT JOIN LATERAL (
        SELECT h.estado_nuevo::text AS estado FROM modulo3.historico_transiciones_dispositivos h
        WHERE h.id_dispositivo_iot = t.id_dispositivo_iot AND h.fecha_transicion <= t.timestamp_captura
        ORDER BY h.fecha_transicion DESC LIMIT 1) est ON true
    WHERE d.id_infraestructura = :infra AND t.timestamp_captura BETWEEN :desde AND :hasta
      AND (CAST(:sensor AS integer) IS NULL OR t.id_sensor = :sensor)
      AND (CAST(:patron AS text) IS NULL OR lower(v.nombre) LIKE :patron)
      AND upper(COALESCE(v.categoria_variable, '')) <> 'ANIMAL'
    ORDER BY t.timestamp_captura, s.nombre
""")

_SQL_DISPOSITIVOS = text("""
    SELECT d.id_dispositivo_iot, d.serial, td.nombre AS tipo, i.nombre AS area, f.nombre AS finca,
           CASE WHEN :es_hoy THEN ed.estado_actual::text ELSE tr.estado END AS estado,
           GREATEST(hb.ultimo, CASE WHEN :es_hoy THEN ed.fecha_ultimo_contacto END) AS ultimo_dato,
           d.fecha_creacion AS instalacion, mant.fecha AS mantenimiento, fw.version_firmware, des.total AS desconexiones
    FROM modulo9.dispositivos_iot d
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
    JOIN modulo9.fincas f ON f.id_finca = i.id_finca
    LEFT JOIN modulo9.tipos_dispositivo_iot td ON td.id_tipo_dispositivo = d.id_tipo_dispositivo
    LEFT JOIN modulo3.estados_dispositivos_iot ed ON ed.id_dispositivo_iot = d.id_dispositivo_iot
    LEFT JOIN LATERAL (
        SELECT h.estado_nuevo::text AS estado FROM modulo3.historico_transiciones_dispositivos h
        WHERE h.id_dispositivo_iot = d.id_dispositivo_iot AND h.fecha_transicion <= :corte
        ORDER BY h.fecha_transicion DESC LIMIT 1) tr ON true
    LEFT JOIN LATERAL (
        SELECT max(h.fecha_recepcion) AS ultimo FROM modulo3.heartbeats h
        WHERE h.id_dispositivo_iot = d.id_dispositivo_iot AND h.fecha_recepcion <= :corte) hb ON true
    LEFT JOIN LATERAL (
        SELECT max(h.fecha_transicion) AS fecha FROM modulo3.historico_transiciones_dispositivos h
        WHERE h.id_dispositivo_iot = d.id_dispositivo_iot AND h.estado_nuevo::text = 'EN_MANTENIMIENTO'
          AND h.fecha_transicion <= :corte) mant ON true
    LEFT JOIN LATERAL (
        SELECT h.version_firmware FROM modulo3.heartbeats h
        WHERE h.id_dispositivo_iot = d.id_dispositivo_iot AND h.fecha_recepcion <= :corte
          AND h.version_firmware IS NOT NULL
        ORDER BY h.fecha_recepcion DESC LIMIT 1) fw ON true
    LEFT JOIN LATERAL (
        SELECT count(*) AS total FROM modulo3.periodos_inactividad p
        WHERE p.id_dispositivo_iot = d.id_dispositivo_iot
          AND p.fecha_inicio BETWEEN :corte - interval '30 days' AND :corte) des ON true
    WHERE d.es_activo AND d.fecha_creacion <= :corte
      AND (CAST(:fincas AS integer[]) IS NULL OR i.id_finca = ANY(:fincas))
      AND (CAST(:infra AS integer) IS NULL OR i.id_infraestructura = :infra)
    ORDER BY f.nombre, i.nombre, d.serial
""")

_CALIBRACION_UNIDAD = ("(SELECT v.unidad FROM modulo9.variables_ambientales v "
                       "WHERE starts_with(lower(v.nombre), lower(s.categoria::text)) LIMIT 1)")

_SQL_CALIBRACIONES = text(f"""
    SELECT * FROM (
        SELECT c.id_calibracion, d.id_dispositivo_iot, d.serial, s.nombre AS sensor, s.categoria::text AS variable,
               c.fecha_calibracion,
               lag(c.valor_referencia) OVER (PARTITION BY c.id_sensor ORDER BY c.fecha_calibracion) AS antes,
               c.valor_referencia AS despues, c.ganancia, c.offset_calibracion, {_CALIBRACION_UNIDAD} AS unidad,
               c.id_usuario, NULLIF(btrim(c.observaciones), '') AS observaciones, i.nombre AS area, f.nombre AS finca,
               c.id_sensor, i.id_infraestructura
        FROM modulo9.calibraciones c
        JOIN modulo9.sensores s ON s.id_sensores = c.id_sensor
        JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = c.id_dispositivo_iot
        JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
        JOIN modulo9.fincas f ON f.id_finca = i.id_finca
        WHERE {_EN_FINCAS} AND {_INFRA}
    ) c
    WHERE c.fecha_calibracion BETWEEN :desde AND :hasta AND (CAST(:sensor AS integer) IS NULL OR c.id_sensor = :sensor)
    ORDER BY c.fecha_calibracion, c.serial
""")

_SQL_SIN_CALIBRAR = text(f"""
    SELECT d.serial, s.nombre AS sensor, s.categoria::text AS variable, ult.fecha AS ultima, i.nombre AS area,
           f.nombre AS finca
    FROM modulo9.sensores s
    JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = s.id_dispositivo_iot
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
    JOIN modulo9.fincas f ON f.id_finca = i.id_finca
    LEFT JOIN LATERAL (SELECT max(c.fecha_calibracion) AS fecha FROM modulo9.calibraciones c
                       WHERE c.id_sensor = s.id_sensores) ult ON true
    WHERE s.es_activo AND d.es_activo AND (ult.fecha IS NULL OR ult.fecha < :antes)
      AND {_EN_FINCAS} AND {_INFRA} AND (CAST(:sensor AS integer) IS NULL OR s.id_sensores = :sensor)
    ORDER BY ult.fecha NULLS FIRST, d.serial
""")

_SQL_ALERTAS = text("""
    SELECT a.id_alerta, d.id_dispositivo_iot, d.serial, a.tipo_alerta::text AS tipo_alerta, a.tipo_variable,
           a.valor, a.unidad, r.umbral_min, r.umbral_max, COALESCE(a.fecha_generacion, a.fecha_registro) AS fecha,
           a.severidad::text AS severidad, a.estado_alerta::text AS estado, a.fecha_resolucion,
           COALESCE(pi.duracion_min::numeric,
                    EXTRACT(EPOCH FROM (COALESCE(a.fecha_resolucion, now()) - COALESCE(a.fecha_generacion, a.fecha_registro)))
                    / 60) AS duracion_min,
           COALESCE(NULLIF(btrim(a.diagnostico), ''), NULLIF(btrim(a.motivo_descarte), '')) AS accion,
           i.nombre AS area, f.nombre AS finca
    FROM modulo3.alertas a
    LEFT JOIN modulo9.sensores s ON s.id_sensores = a.id_sensor
    LEFT JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = COALESCE(a.id_dispositivo_ioit, s.id_dispositivo_iot)
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = COALESCE(a.id_infraestructura, d.id_infraestructura)
    JOIN modulo9.fincas f ON f.id_finca = i.id_finca
    LEFT JOIN modulo3.reglas_alertas r ON r.id_regla_alertas = a.id_regla_alerta
    LEFT JOIN LATERAL (SELECT p.duracion_min FROM modulo3.periodos_inactividad p WHERE p.id_alerta = a.id_alerta
                       ORDER BY p.fecha_inicio DESC LIMIT 1) pi ON true
    WHERE (a.id_sensor IS NOT NULL OR a.id_dispositivo_ioit IS NOT NULL)
      AND COALESCE(a.fecha_generacion, a.fecha_registro) BETWEEN :desde AND :hasta
      AND (CAST(:fincas AS integer[]) IS NULL OR i.id_finca = ANY(:fincas))
      AND (CAST(:infra AS integer) IS NULL OR i.id_infraestructura = :infra)
    ORDER BY fecha, d.serial
""")

# --- Agregados: solo totales (RNF-11). --------------------------------------------------------

_SQL_ANIMALES_POR_ESPECIE = text(f"""
    SELECT f.nombre AS finca, e.nombre AS especie, sum(COALESCE(dp.cantidad_actual, 1)) AS animales
    FROM modulo2.activos_biologicos ab {_ACTIVO} {_ESTADO} {_POBLACION} {_BAJA}
    WHERE {_EN_FINCAS} AND COALESCE(ab.fecha_inicio_ciclo, (ab.fecha_creacion AT TIME ZONE :tz)::date) <= :fin
      AND (COALESCE(est.nombre, '') NOT IN {_FUERA} OR (bj.fecha AT TIME ZONE :tz)::date > :fin)
    GROUP BY f.nombre, e.nombre ORDER BY f.nombre, e.nombre
""")

# Mismo universo que la valoración NIC 41 del período: los activos con valor al corte, salvo los dados de baja
# hasta ese día. Un activo cerrado sin evento de baja sigue contando, como en el cálculo de M06 (M8-07).
_SQL_VALOR_PORTAFOLIO = text(f"""
    SELECT f.nombre AS finca, sum(COALESCE(vr.valor_neto, vc.valor)) AS valor,
           sum(vr.valor_neto) AS valor_razonable, sum(CASE WHEN vr.valor_neto IS NULL THEN vc.valor END) AS valor_costo
    FROM modulo2.activos_biologicos ab {_ACTIVO} {_ESTADO} {_BAJA}
    {_VALOR_AL.format(dia=':fin')}
    WHERE {_EN_FINCAS} AND (bj.fecha IS NULL OR (bj.fecha AT TIME ZONE :tz)::date > :fin)
      AND (vr.valor_neto IS NOT NULL OR vc.valor IS NOT NULL)
    GROUP BY f.nombre ORDER BY f.nombre
""")

_SQL_BAJAS_POR_TIPO = text(f"""
    SELECT f.nombre AS finca, upper(eb.tipo::text) AS tipo, sum(COALESCE(eb.cantidad_afectada, 1)) AS animales
    FROM modulo2.eventos_bajas eb JOIN modulo2.eventos_activos ea ON ea.id_eventos = eb.id_evento
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico {_ACTIVO}
    WHERE ea.fecha BETWEEN :desde AND :hasta AND {_EN_FINCAS}
    GROUP BY f.nombre, upper(eb.tipo::text) ORDER BY f.nombre, tipo
""")

_SQL_RIESGO_POR_NIVEL = text(f"""
    SELECT f.nombre AS finca, x.fuente, x.nivel_riesgo, count(*) AS total
    FROM (
        SELECT ea.id_activo_biologico, 'M02' AS fuente,
               (SELECT r.nivel_riesgo FROM modulo4.resultados_inferencia r
                WHERE r.id_activo_biologico = ea.id_activo_biologico
                  AND r.fecha_inferencia BETWEEN ea.fecha - interval '7 days' AND ea.fecha
                ORDER BY r.fecha_inferencia DESC LIMIT 1) AS nivel_riesgo
        FROM modulo2.eventos_sanitarios es JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
        WHERE ea.fecha BETWEEN :desde AND :hasta
        UNION ALL
        SELECT r.id_activo_biologico, 'M04', r.nivel_riesgo FROM modulo4.resultados_inferencia r
        WHERE r.fecha_inferencia BETWEEN :desde AND :hasta AND r.nivel_riesgo >= 1
    ) x
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = x.id_activo_biologico {_ACTIVO}
    WHERE {_EN_FINCAS}
    GROUP BY f.nombre, x.fuente, x.nivel_riesgo
""")

_SQL_RIESGO_ACTIVO = text(f"""
    SELECT p.finca, p.nivel_riesgo, count(*) AS animales FROM (
        SELECT DISTINCT ON (r.id_activo_biologico) f.nombre AS finca, r.nivel_riesgo
        FROM modulo4.resultados_inferencia r
        JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = r.id_activo_biologico {_ACTIVO}
        WHERE r.fecha_inferencia >= now() - interval '7 days' AND {_EN_FINCAS}
        ORDER BY r.id_activo_biologico, r.fecha_inferencia DESC
    ) p WHERE p.nivel_riesgo >= 1 GROUP BY p.finca, p.nivel_riesgo
""")

_SQL_DISPOSITIVOS_POR_ESTADO = text(f"""
    SELECT f.nombre AS finca, COALESCE(ed.estado_actual::text, 'DESCONOCIDO') AS estado, count(*) AS total
    FROM modulo9.dispositivos_iot d
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
    JOIN modulo9.fincas f ON f.id_finca = i.id_finca
    LEFT JOIN modulo3.estados_dispositivos_iot ed ON ed.id_dispositivo_iot = d.id_dispositivo_iot
    WHERE d.es_activo AND {_EN_FINCAS}
    GROUP BY f.nombre, COALESCE(ed.estado_actual::text, 'DESCONOCIDO') ORDER BY f.nombre
""")

_SQL_VARIACION_TOTAL = text(f"""
    SELECT COALESCE(sum(vv.monto_variacion), 0) FROM modulo6.variaciones_valor_razonable vv
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = vv.id_activo_biologico {_ACTIVO}
    WHERE vv.id_periodo_contable = :periodo AND i.id_finca = ANY(:fincas)
""")

_SQL_ULTIMO_CERRADO = text("""
    SELECT id_periodo_contable, fecha_inicio, fecha_fin FROM modulo6.periodos_contables
    WHERE numero_id_tributaria = :nit AND estado = 'CERRADO' AND fecha_fin <= :hasta
    ORDER BY fecha_fin DESC LIMIT 1
""")

# --- Historial predictivo (RF-106) -------------------------------------------------------------

_SQL_INFERENCIAS = text(f"""
    SELECT r.id_resultado_inferencia, r.fecha_inferencia, r.nivel_riesgo, r.confianza_global, pt.nombre AS condicion,
           r.tiene_alerta_generada, COALESCE(r.modo_sombra, false) AS modo_sombra
    FROM modulo4.resultados_inferencia r LEFT JOIN modulo9.patologias pt ON pt.id_patologia = r.id_patologia
    WHERE r.id_activo_biologico = :activo AND r.fecha_inferencia BETWEEN :desde AND :hasta
    ORDER BY r.fecha_inferencia
""")

# Las retroalimentaciones de las predicciones del rango (aunque se hayan registrado después).
_SQL_RETROALIMENTACIONES = text("""
    SELECT rc.id_retroalimentacion, rc.id_resultado_inferencia, rc.estado_retroalimentacion::text AS valoracion,
           rc.fecha_retroalimentacion, rc.id_usuario_veterinario, NULLIF(btrim(rc.observaciones_clinicas), '') AS observaciones
    FROM modulo4.retroalimentaciones_clinicas rc
    JOIN modulo4.resultados_inferencia r ON r.id_resultado_inferencia = rc.id_resultado_inferencia
    WHERE rc.id_activo_biologico = :activo AND r.fecha_inferencia BETWEEN :desde AND :hasta
      AND COALESCE(rc.estado_registro, 'VALIDO') NOT IN ('ANULADO', 'ANULADA')
    ORDER BY rc.fecha_retroalimentacion
""")

_SQL_PARAMETRO = text("SELECT COALESCE(valor_actual, valor_por_defecto) FROM modulo4.parametros_mlops "
                      "WHERE nombre_parametro = :n")


class SqlAlchemyFuenteReportesRepository(FuenteReportesRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def _filas(self, consulta: TextClause, params: dict[str, Any]) -> list[Fila]:
        return [dict(f._mapping) for f in self.db.execute(consulta, {"tz": nombre_zona_usuario(), **params})]

    # --- Referencias ---

    def nombre_referencia(self, tipo: str, id_referencia: int) -> Optional[str]:
        consulta = _SQL_NOMBRE_REFERENCIA.get("activo" if tipo == "lote" else tipo)
        return self.db.execute(consulta, {"id": id_referencia}).scalar() if consulta is not None else None

    def ubicar(self, tipo: str, id_referencia: int) -> Optional[Fila]:
        consulta = _SQL_UBICAR["activo" if tipo == "lote" else tipo]
        with como_sistema(self.db):  # 404 frente a 403: la RLS escondería la de otra finca
            filas = self._filas(consulta, {"id": id_referencia})
        return filas[0] if filas else None

    def opciones(self, tipo: str, fincas: Fincas) -> list[Fila]:
        return self._filas(_SQL_OPCIONES[tipo], {"fincas": fincas})

    def periodo(self, id_periodo: int) -> Optional[Fila]:
        filas = self._filas(_SQL_PERIODO, {"id": id_periodo})
        return filas[0] if filas else None

    def fincas(self, fincas: Fincas) -> list[Fila]:
        return self._filas(_SQL_FINCAS, {"fincas": fincas})

    def fincas_de_titular(self, nit: str, fincas: Fincas) -> list[int]:
        return [f["id_finca"] for f in self._filas(_SQL_FINCAS_TITULAR, {"nit": nit, "fincas": fincas})]

    def ruta_logo(self, id_finca: int) -> Optional[str]:
        logo = self.db.execute(_SQL_LOGO, {"f": id_finca}).scalar()
        if not logo or not logo.lower().endswith((".png", ".jpg", ".jpeg")):
            return None
        ruta = os.path.join(DIRECTORIO_LOGOS, logo.removeprefix(RUTA_PUBLICA_LOGOS).lstrip("/"))
        return ruta if os.path.isfile(ruta) else None

    def nombres_usuarios(self, ids: list[int]) -> dict[int, Optional[str]]:
        return nombres_usuarios(self.db, ids)

    # --- Productivos ---

    def inventario(self, *, fincas, inicio, fin, hasta, especie, estado):
        return self._filas(_SQL_INVENTARIO, {"fincas": fincas, "inicio": inicio, "fin": fin, "hasta": hasta,
                                             "especie": especie, "estado": estado})

    def costos(self, *, fincas, inicio, fin, especie, tipo, activo=None):
        return self._filas(_SQL_COSTOS, {"fincas": fincas, "inicio": inicio, "fin": fin, "especie": especie,
                                         "tipo": tipo, "activo": activo})

    def produccion(self, *, fincas, desde, hasta, especie, activo):
        return self._filas(_SQL_PRODUCCION, {"fincas": fincas, "desde": desde, "hasta": hasta, "especie": especie,
                                             "activo": activo})

    def conversion(self, *, fincas, inicio, fin, especie, activo):
        return self._filas(_SQL_CONVERSION, {"fincas": fincas, "inicio": inicio, "fin": fin, "especie": especie,
                                             "activo": activo})

    def salidas(self, *, fincas, desde, hasta, especie):
        return self._filas(_SQL_SALIDAS, {"fincas": fincas, "desde": desde, "hasta": hasta, "especie": especie})

    # --- Contables ---

    def valoracion_periodo(self, *, id_periodo, fincas):
        return self._filas(_SQL_VALORACION_PERIODO, {"periodo": id_periodo, "fincas": fincas})

    def exportaciones(self, id_periodo):
        return self._filas(_SQL_EXPORTACIONES, {"periodo": id_periodo})

    def variacion_periodos(self, *, base, comparacion, fincas):
        return self._filas(_SQL_VARIACION, {"base": base, "comparacion": comparacion, "fincas": fincas})

    # --- Sanitarios ---

    def eventos_sanitarios(self, *, fincas, desde, hasta, especie, activo):
        return self._filas(_SQL_SANITARIOS, {"fincas": fincas, "desde": desde, "hasta": hasta, "especie": especie,
                                             "activo": activo})

    def ficha(self, id_activo):
        filas = self._filas(_SQL_FICHA, {"activo": id_activo})
        return filas[0] if filas else None

    def valoracion_por_periodo(self, id_activo):
        return self._filas(_SQL_VALORACION_ACTIVO, {"activo": id_activo})

    def predicciones_activas(self, *, fincas, especie, activo, desde):
        return self._filas(_SQL_PREDICCIONES, {"fincas": fincas, "especie": especie, "activo": activo, "desde": desde})

    def medicamentos(self, *, fincas, inicio, fin, especie, activo):
        return self._filas(_SQL_MEDICAMENTOS, {"fincas": fincas, "inicio": inicio, "fin": fin, "especie": especie,
                                               "activo": activo})

    def retiros_vigentes(self, *, fincas, hoy, especie, activo):
        return self._filas(_SQL_RETIROS, {"fincas": fincas, "hoy": hoy, "especie": especie, "activo": activo})

    # --- IoT ---

    def telemetria(self, *, infraestructura, desde, hasta, sensor, patron_variable):
        return self._filas(_SQL_TELEMETRIA, {"infra": infraestructura, "desde": desde, "hasta": hasta,
                                             "sensor": sensor, "patron": patron_variable})

    def dispositivos(self, *, fincas, corte, es_hoy, infraestructura):
        return self._filas(_SQL_DISPOSITIVOS, {"fincas": fincas, "corte": corte, "es_hoy": es_hoy,
                                               "infra": infraestructura})

    def calibraciones(self, *, fincas, desde, hasta, sensor, infraestructura):
        return self._filas(_SQL_CALIBRACIONES, {"fincas": fincas, "desde": desde, "hasta": hasta, "sensor": sensor,
                                                "infra": infraestructura})

    def sensores_sin_calibrar(self, *, fincas, antes_de, sensor, infraestructura):
        return self._filas(_SQL_SIN_CALIBRAR, {"fincas": fincas, "antes": antes_de, "sensor": sensor,
                                               "infra": infraestructura})

    def alertas_sensores(self, *, fincas, desde, hasta, infraestructura):
        return self._filas(_SQL_ALERTAS, {"fincas": fincas, "desde": desde, "hasta": hasta,
                                          "infra": infraestructura})

    # --- Agregados ---

    def animales_por_especie(self, *, fincas, fin):
        return self._filas(_SQL_ANIMALES_POR_ESPECIE, {"fincas": fincas, "fin": fin})

    def valor_portafolio(self, *, fincas, fin):
        return self._filas(_SQL_VALOR_PORTAFOLIO, {"fincas": fincas, "fin": fin})

    def bajas_por_tipo(self, *, fincas, desde, hasta):
        return self._filas(_SQL_BAJAS_POR_TIPO, {"fincas": fincas, "desde": desde, "hasta": hasta})

    def costos_por_tipo(self, *, fincas, inicio, fin):
        totales: dict[tuple[str, str], Any] = {}
        for c in self.costos(fincas=fincas, inicio=inicio, fin=fin, especie=None, tipo=None):
            clave = (c["finca"], c["tipo"])
            totales[clave] = totales.get(clave, 0) + (c["costo_total"] or 0)
        return [{"finca": f, "tipo": t, "costo": v} for (f, t), v in sorted(totales.items())]

    def riesgo_por_nivel(self, *, fincas, desde, hasta):
        return self._filas(_SQL_RIESGO_POR_NIVEL, {"fincas": fincas, "desde": desde, "hasta": hasta})

    def animales_con_riesgo_activo(self, *, fincas):
        return self._filas(_SQL_RIESGO_ACTIVO, {"fincas": fincas})

    def dispositivos_por_estado(self, *, fincas):
        return self._filas(_SQL_DISPOSITIVOS_POR_ESTADO, {"fincas": fincas})

    def variacion_total_periodo(self, *, id_periodo, fincas):
        return self.db.execute(_SQL_VARIACION_TOTAL, {"tz": nombre_zona_usuario(), "periodo": id_periodo,
                                                      "fincas": fincas}).scalar()

    def ultimo_periodo_cerrado(self, *, nit, hasta):
        filas = self._filas(_SQL_ULTIMO_CERRADO, {"nit": nit, "hasta": hasta})
        return filas[0] if filas else None

    # --- Historial predictivo ---

    def _aislado(self, consulta: TextClause, params: dict[str, Any]) -> list[Fila]:
        """En un savepoint: si la consulta falla, las demás fuentes del historial siguen (RF-106 RNF-06)."""
        with self.db.begin_nested():
            return self._filas(consulta, params)

    def inferencias(self, *, activo, desde, hasta):
        return self._aislado(_SQL_INFERENCIAS, {"activo": activo, "desde": desde, "hasta": hasta})

    def retroalimentaciones(self, *, activo, desde, hasta):
        return self._aislado(_SQL_RETROALIMENTACIONES, {"activo": activo, "desde": desde, "hasta": hasta})

    def eventos_sanitarios_aislados(self, *, activo, desde, hasta):
        return self._aislado(_SQL_SANITARIOS, {"fincas": None, "desde": desde, "hasta": hasta, "especie": None,
                                               "activo": activo})

    def parametro(self, nombre):
        return self.db.execute(_SQL_PARAMETRO, {"n": nombre}).scalar()
