# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-92/RF-93: insumos y persistencia de revelaciones y estado de resultados |
# | 2026-11-09 | destroyerban | INC-M06-320-G24 RF-85 FA-4: la cosecha del 100 % deja el activo en cero e inicia su baja |
# | 2026-11-10 | Arekkazu | TC-DIS-257 RF-92/93: nombre de quien aprobó el informe y el estado de resultados |
# | 2026-11-11 | Arekkazu | USAB-M05-M06 T-01 RF-75..94: el activo sin identificador se nombra «Lote N», nunca null |
# | 2026-11-12 | Arekkazu | USAB-M05-M06 N-04 RF-92/93: estados e informes solo de los titulares de las fincas de quien consulta |
# | 2026-11-12 | LuisfNarvaez01 | INC-M06-359-G79 RF-93: excluir_activos en los movimientos del estado de resultados |
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G62 RF-92: conciliación con la baja total en cero y los ingresos de individuos sin costo |
# | 2026-11-13 | Arekkazu | INC-M06-061B-G57 RF-91/92 (RFC-027): 403 y no 404 al lector cuando el estado no le corresponde |
# | 2026-11-13 | Leandro | TC-M06-G61 RF-92: recuperar los supuestos al corte y la fuente de precio. |
# | 2026-11-13 | Arekkazu | INC-M06 RF-92/93 (RFC-027): 403 y no 404 al Revisor Fiscal en la descarga del informe y en el estado de resultados no aprobado |
# | 2026-11-13 | Arekkazu | TC-M06-G74 RF-93 FA-2: conciliación del estado de resultados con sus fuentes (hechos sin asiento) |
# | 2026-11-15 | Arekkazu | INC-M06-364-G71 RF-93: ingreso por venta de activos en el estado de resultados (sin asiento) |
# | 2026-11-15 | Arekkazu | TC-M06-G62/G64 RF-92: valores al cierre por período, asientos que el cierre trasladó y riesgos climáticos |
# | 2026-11-15 | Arekkazu | INC-M06-93-G44 RF-92/93: el nombre de quien aprobó sale aunque la RLS de usuarios lo oculte |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQL de :class:`ReporteRepository`."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.repositories.reporte_repository import ReporteRepository
from src.financial_valuation.infrastructure.repositories.sql import (
    CONSUMIDO_POR_COSECHA, a_json, alcance_periodo, con_nombres, escribir, fila, filas,
)
from src.shared.database import como_sistema
from src.shared.fechas import nombre_zona_usuario
from src.shared.nombre_activo import nombre_activo_sql

ES_BASE_C = "COALESCE((c.json_metodo_costo->>'es_producto')::boolean, false) = false"
CONSUMIDO_C = CONSUMIDO_POR_COSECHA.format(calculo="c.id_calculo_valor_razonable")  # RF-85 FA-4: vale 0
ALERTAS_CLIMATICAS = "('ESTRES_TERMICO', 'RIESGO_HIDRICO', 'FALLO_AMBIENTAL')"  # modulo3.enum_tipo_alerta


def _hasta(periodo: str, comparacion: str) -> str:
    """TC-M06-G62: el período ``periodo`` empieza antes (``<``) o no después (``<=``) que el del informe. Va por período
    y no por fecha: un hecho fechado dentro de un período ya cerrado entra al siguiente (RF-87 v1.1) y no cambia el
    valor con que cerró aquel."""
    return f"""(SELECT pc.fecha_inicio FROM modulo6.periodos_contables pc
                WHERE pc.id_periodo_contable = {periodo}) {comparacion} :i"""


# Líneas que el cierre trasladó al período siguiente (RF-91), con el período en que se midieron.
_TRASLADADAS = "unnest(CAST(:mov_lineas AS bigint[]), CAST(:mov_origen AS integer[])) AS m(id_linea, origen)"


def _costo_al(momento: str) -> str:
    """TC-M06-G62: valor al costo (RF-88: costo − depreciación − deterioro, sin bajar de cero) al inicio o al cierre
    del período: sin la depreciación ni el deterioro que se registraron después. Nulo si el activo no va al costo."""
    return f"""CASE WHEN vc.id_valoracion_por_costo IS NOT NULL THEN
        GREATEST(vc.costos_adquisicion - (vc.depreciacion_acumulada - post.dep_{momento})
                 - (vc.deterioro_acumulado - post.det_{momento}), 0) END"""


def _dado_de_baja(comparacion: str) -> str:
    """TC-M06-G62: el activo salió por una baja total en un período hasta el del informe. La baja total no deja un
    cálculo nuevo (la parcial sí, con el resto), así que su último cálculo no es su valor: vale 0. Que fue total lo
    dice la auditoría de la baja (``proporcion`` = 1), que es inmutable. La baja cuenta en el período en que se
    registró, aunque el cierre haya trasladado su asiento."""
    return f"""EXISTS (SELECT 1 FROM modulo6.lineas_asiento_nic41 lb LEFT JOIN {_TRASLADADAS} ON m.id_linea = lb.id_linea_asiento_nic41
        WHERE lb.id_activo_biologico = a.id_activo_biologico AND lb.tipo_hecho = 'BAJA_ACTIVO' AND NOT lb.es_reverso
          AND {_hasta("COALESCE(m.origen, lb.id_periodo_contable)", comparacion)}
          AND NOT EXISTS (SELECT 1 FROM modulo6.lineas_asiento_nic41 r
                          WHERE r.es_reverso AND r.tipo_hecho = lb.tipo_hecho AND r.id_activo_biologico = lb.id_activo_biologico
                            AND r.tabla_origen = lb.tabla_origen AND r.id_origen = lb.id_origen)
          AND EXISTS (SELECT 1 FROM modulo6.auditorias_financieras af
                      WHERE af.tipo_evento::text = 'BAJA_ACTIVO_REGISTRADA' AND af.id_referencia = lb.id_origen
                        AND af.id_activo_biologico = lb.id_activo_biologico
                        AND (af.datos_nuevos->>'proporcion')::numeric >= 1))"""

_FILTROS = (("id_especie", "l.id_especie = :id_especie"), ("id_activo_biologico", "l.id_activo_biologico = :id_activo_biologico"),
            ("id_infraestructura", "a.id_infraestructura = :id_infraestructura"), ("id_finca", "l.id_finca = :id_finca"))


# Nombre de quien aprobó (RF-92 paso 6 / RF-93): nulo mientras no se apruebe. Lo agrega con_nombres (INC-M06-93-G44).
_APROBADOR_ESTADO = {"id_usuario_aprobador": "nombre_aprobador"}
_APROBADOR_INFORME = {"id_contador_aprobador": "nombre_aprobador"}


class SqlAlchemyReporteRepository(ReporteRepository):
    """Implementación SQLAlchemy de ``ReporteRepository``."""
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- RF-93 ---------------------------------------------------------------------------------

    def movimientos(self, id_periodo_contable: int, filtros: dict) -> list[dict]:
        """Líneas REGISTRADAS del período con activo, especie, finca e infraestructura."""
        condiciones, params = ["l.id_periodo_contable = :p", "l.estado = 'REGISTRADA'"], {"p": id_periodo_contable}
        for campo, sql in _FILTROS:
            if filtros.get(campo):
                condiciones.append(sql)
                params[campo] = filtros[campo]
        if filtros.get("excluir_activos"):  # RF-93 FA-3/FA-4: activos excluidos del cierre
            condiciones.append("NOT (l.id_activo_biologico = ANY(:excluir_activos))")
            params["excluir_activos"] = list(filtros["excluir_activos"])
        return filas(self.db, f"""
            SELECT l.id_linea_asiento_nic41, COALESCE(l.tipo_hecho_corregido, l.tipo_hecho)::text AS tipo_hecho,
                   l.sentido::text AS sentido, l.valor, l.es_reverso, l.id_activo_biologico, {nombre_activo_sql()} AS activo,
                   l.id_especie, l.id_finca, a.id_infraestructura, l.id_comprobante_nic41,
                   eb.tipo::text AS tipo_baja, eb.valor_venta
            FROM modulo6.lineas_asiento_nic41 l
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = l.id_activo_biologico
            -- INC-M06-364-G71: la línea de una baja apunta a su evento; la venta trae lo recibido (RF-45).
            LEFT JOIN modulo2.eventos_bajas eb
              ON l.tabla_origen = 'procesamientos_eventos_m02' AND eb.id_evento = l.id_origen
            WHERE {' AND '.join(condiciones)}""", params)

    def hechos_sin_asiento(self, id_periodo_contable: int) -> list[dict]:
        """RF-93 FA-2: variaciones (RF-86) y productos agrícolas (RF-85) del período sin línea de asiento."""
        # La línea se busca por su origen, no por su período: el cierre traslada al siguiente las que excluye.
        return filas(self.db, f"""
            SELECT 'variaciones_valor_razonable' AS fuente, v.id_variacion_valor_razonable AS id_origen,
                   v.id_activo_biologico, {nombre_activo_sql('ab')} AS identificador, v.monto_variacion AS monto
            FROM modulo6.variaciones_valor_razonable v
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = v.id_activo_biologico
            WHERE v.id_periodo_contable = :p AND v.monto_variacion <> 0 AND NOT EXISTS (
                SELECT 1 FROM modulo6.lineas_asiento_nic41 l
                WHERE l.tabla_origen = 'variaciones_valor_razonable' AND l.id_origen = v.id_variacion_valor_razonable)
            UNION ALL
            SELECT 'reconocimientos_productos_agricolas', r.id_reconocimiento_producto_agricola,
                   r.id_activo_biologico, {nombre_activo_sql('ab')}, r.valor_producto
            FROM modulo6.reconocimientos_productos_agricolas r
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = r.id_activo_biologico
            WHERE r.id_periodo_contable = :p AND r.valor_producto <> 0 AND NOT EXISTS (
                SELECT 1 FROM modulo6.lineas_asiento_nic41 l
                WHERE l.tabla_origen = 'reconocimientos_productos_agricolas'
                  AND l.id_origen = r.id_reconocimiento_producto_agricola)
            ORDER BY 1, 2""", {"p": id_periodo_contable})

    def agregar_estado(self, datos: dict) -> int:
        """Guarda un estado de resultados y devuelve su id."""
        return escribir(self.db, """
            INSERT INTO modulo6.estados_resultados_periodo (id_periodo_contable, total_ingresos_transformacion,
                total_ingresos_precio_mercado, total_ingresos_cosecha, total_gastos_mantenimiento, total_bajas_deterioro,
                resultado_neto, estado, hash_consistencia, fecha_generacion, total_ingresos, total_gastos, json_componentes,
                json_filtros, version, id_usuario)
            VALUES (:p, :ing_tb, :ing_pm, :ing_cosecha, :gastos_mant, :bajas, :neto, 'GENERADO', :hash, now(), :ingresos,
                :gastos, CAST(:componentes AS jsonb), CAST(:filtros AS jsonb), :version, :u)
            RETURNING id_estado""", {**datos, "componentes": a_json(datos["componentes"]), "filtros": a_json(datos["filtros"])})

    def obtener_estado(self, id_estado: int) -> Optional[dict]:
        """Devuelve el estado de resultados, o ``None``."""
        estado = fila(self.db, f"""SELECT id_estado, id_periodo_contable, total_ingresos, total_gastos, resultado_neto, estado,
                                         hash_consistencia, fecha_generacion, json_componentes AS componentes,
                                         json_filtros AS filtros, version, id_usuario, id_usuario_aprobador, fecha_aprobacion
                                  FROM modulo6.estados_resultados_periodo er
                                  WHERE id_estado = :id AND {alcance_periodo('er.id_periodo_contable')}""", {"id": id_estado})
        return con_nombres(self.db, [estado], _APROBADOR_ESTADO)[0] if estado else None

    def aprobar_estado(self, id_estado: int, id_usuario: int) -> None:
        """Aprueba el estado de resultados."""
        escribir(self.db, """UPDATE modulo6.estados_resultados_periodo
                             SET estado = 'APROBADO', id_usuario_aprobador = :u, fecha_aprobacion = now()
                             WHERE id_estado = :id AND estado = 'GENERADO'""", {"id": id_estado, "u": id_usuario})

    def listar_estados(self, id_periodo_contable: int) -> list[dict]:
        """Lista los estados de resultados del periodo."""
        return filas(self.db, f"""SELECT id_estado, id_periodo_contable, total_ingresos, total_gastos, resultado_neto, estado,
                                        fecha_generacion, json_filtros AS filtros, version, fecha_aprobacion
                                 FROM modulo6.estados_resultados_periodo er
                                 WHERE id_periodo_contable = :p AND {alcance_periodo('er.id_periodo_contable')}
                                 ORDER BY version DESC""", {"p": id_periodo_contable})

    def siguiente_version_estado(self, id_periodo_contable: int) -> int:
        """Siguiente número de versión del estado de resultados."""
        return fila(self.db, """SELECT COALESCE(max(version), 0) + 1 AS v FROM modulo6.estados_resultados_periodo
                                WHERE id_periodo_contable = :p""", {"p": id_periodo_contable})["v"]

    # --- RF-92 ---------------------------------------------------------------------------------

    def datos_revelaciones(self, id_periodo_contable: int) -> dict:
        """Insumos de RF-92: activos, rollforward, supuestos, precios, costo, riesgos."""
        p = {"p": id_periodo_contable}
        periodo = fila(self.db, """SELECT id_periodo_contable, numero_id_tributaria, fecha_inicio, fecha_fin,
                                          tipo_cierre::text AS tipo_cierre FROM modulo6.periodos_contables
                                   WHERE id_periodo_contable = :p""", p)
        rango = {**p, "nit": periodo["numero_id_tributaria"], "i": periodo["fecha_inicio"], "f": periodo["fecha_fin"]}
        # TC-M06-G62: lo que el cierre trasladó al período siguiente lo dice su auditoría (RF-91), que el Contador
        # que genera el informe puede no ver: se leen solo los ids de las líneas.
        # ponytail: una auditoría con más de 64 KB (~400 líneas) queda truncada y sus líneas no se ven aquí; la
        # conciliación de esos activos saldría como advertencia. Guardar el período de origen en la línea si pasa.
        with como_sistema(self.db):
            movidas = filas(self.db, """
                SELECT (x->>'id_linea')::bigint AS id_linea, min(af.id_periodo_contable) AS origen
                FROM modulo6.auditorias_financieras af CROSS JOIN LATERAL jsonb_array_elements(af.datos_nuevos->'lineas') x
                WHERE af.tipo_evento = 'EXCLUSION_CIERRE_AUTORIZADA' AND af.id_periodo_contable IN (
                    SELECT id_periodo_contable FROM modulo6.periodos_contables WHERE numero_id_tributaria = :nit)
                GROUP BY 1""", rango)
        rango.update(mov_lineas=[m["id_linea"] for m in movidas], mov_origen=[m["origen"] for m in movidas])
        activos = filas(self.db, f"""
            SELECT a.id_activo_biologico, {nombre_activo_sql()} AS identificador, a.tipo::text AS tipo, e.id_especie, e.nombre AS especie,
                   ri.clasificacion::text AS clasificacion, ri.indicador_valoracion::text AS indicador_valoracion,
                   ri.origen_financiero::text AS origen_financiero, ri.costo_adquisicion,
                   ri.fecha_creacion::date AS fecha_reconocimiento, d.cantidad_actual, f.id_finca,
                   CASE WHEN {_dado_de_baja("<")} THEN 0 ELSE
                   (SELECT CASE WHEN {CONSUMIDO_C} THEN 0 ELSE c.valor_neto END FROM modulo6.calculos_valor_razonable c
                     WHERE c.id_activo_biologico = a.id_activo_biologico AND c.estado = 'CALCULADO' AND {ES_BASE_C}
                       AND {_hasta("c.id_periodo_contable", "<")}
                     ORDER BY c.fecha_calculo DESC, c.id_calculo_valor_razonable DESC LIMIT 1) END AS valor_inicio,
                   CASE WHEN {_dado_de_baja("<=")} THEN 0 ELSE
                   (SELECT CASE WHEN {CONSUMIDO_C} THEN 0 ELSE c.valor_neto END FROM modulo6.calculos_valor_razonable c
                     WHERE c.id_activo_biologico = a.id_activo_biologico AND c.estado = 'CALCULADO' AND {ES_BASE_C}
                       AND {_hasta("c.id_periodo_contable", "<=")}
                     ORDER BY c.fecha_calculo DESC, c.id_calculo_valor_razonable DESC LIMIT 1) END AS valor_cierre,
                   {_costo_al("cierre")} AS valor_contable_por_costo, {_costo_al("inicio")} AS valor_costo_inicio,
                   vc.razon_sin_mercado, vc.vida_util_meses, vc.depreciacion_acumulada - post.dep_cierre AS depreciacion_acumulada,
                   vc.deterioro_acumulado - post.det_cierre AS deterioro_acumulado, vc.costos_adquisicion AS costo_base
            FROM modulo6.reconocimientos_iniciales ri
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = ri.id_activo_biologico
            JOIN modulo9.especies e ON e.id_especie = a.id_especie
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d ON d.id_activo_biologico = a.id_activo_biologico
            LEFT JOIN modulo6.valoraciones_por_costos vc ON vc.id_activo_biologico = a.id_activo_biologico AND vc.es_activa
            LEFT JOIN LATERAL (  -- TC-M06-G62: depreciación y deterioro registrados desde el inicio / después del cierre
                SELECT COALESCE(sum(x.v) FILTER (WHERE x.dep AND x.tras_cierre), 0) AS dep_cierre,
                       COALESCE(sum(x.v) FILTER (WHERE NOT x.dep AND x.tras_cierre), 0) AS det_cierre,
                       COALESCE(sum(x.v) FILTER (WHERE x.dep AND x.desde_inicio), 0) AS dep_inicio,
                       COALESCE(sum(x.v) FILTER (WHERE NOT x.dep AND x.desde_inicio), 0) AS det_inicio
                FROM (SELECT CASE WHEN l.es_reverso THEN -l.valor ELSE l.valor END AS v,
                             COALESCE(l.tipo_hecho_corregido, l.tipo_hecho)::text LIKE 'DEPRECIACION%' AS dep,
                             NOT {_hasta("COALESCE(m.origen, l.id_periodo_contable)", "<=")} AS tras_cierre,
                             NOT {_hasta("COALESCE(m.origen, l.id_periodo_contable)", "<")} AS desde_inicio
                      FROM modulo6.lineas_asiento_nic41 l LEFT JOIN {_TRASLADADAS} ON m.id_linea = l.id_linea_asiento_nic41
                      WHERE vc.id_valoracion_por_costo IS NOT NULL AND l.id_activo_biologico = a.id_activo_biologico
                        AND COALESCE(l.tipo_hecho_corregido, l.tipo_hecho)::text ~ '^(DEPRECIACION|DETERIORO)') x
            ) post ON true
            WHERE ri.estado = 'CONFIRMADO' AND f.numero_id_tributaria = :nit AND ri.fecha_creacion::date <= :f
            ORDER BY e.nombre, a.identificador""", rango)
        movimientos = filas(self.db, """
            SELECT l.id_activo_biologico, COALESCE(l.tipo_hecho_corregido, l.tipo_hecho)::text AS tipo_hecho,
                   l.sentido::text AS sentido, l.es_reverso, sum(l.valor) AS valor
            FROM modulo6.lineas_asiento_nic41 l WHERE l.id_periodo_contable = :p
            GROUP BY 1, 2, 3, 4""", p)
        # TC-M06-G62: asientos que el cierre movió de período. Sale del informe el que se midió en este período y
        # quedó en otro (su efecto está en el valor al cierre, no en los movimientos); entra el que llegó de uno
        # anterior (su efecto ya estaba en el valor al inicio).
        trasladadas = filas(self.db, f"""
            SELECT l.id_activo_biologico, COALESCE(l.tipo_hecho_corregido, l.tipo_hecho)::text AS tipo_hecho,
                   l.sentido::text AS sentido, l.es_reverso, m.origen = :p AS sale, sum(l.valor) AS valor
            FROM {_TRASLADADAS} JOIN modulo6.lineas_asiento_nic41 l ON l.id_linea_asiento_nic41 = m.id_linea
            WHERE (m.origen = :p) <> (l.id_periodo_contable = :p)
            GROUP BY 1, 2, 3, 4, 5""", rango)
        # TC-M06-G62: ingresos de individuos sin costo (compra, donación, traslado) que subieron la base del activo.
        ingresos = filas(self.db, """
            SELECT c.id_activo_biologico, c.json_metodo_costo->'ingreso_individuos'->>'tipo_ingreso' AS tipo_ingreso,
                   sum((c.json_metodo_costo->'ingreso_individuos'->>'incremento')::numeric) AS valor
            FROM modulo6.calculos_valor_razonable c
            WHERE c.id_periodo_contable = :p AND c.estado = 'CALCULADO' AND c.json_metodo_costo ? 'ingreso_individuos'
            GROUP BY 1, 2""", p)
        precios = filas(self.db, """
            SELECT DISTINCT pm.id_precio_mercado, e.nombre AS especie, pm.categoria[1]::text AS categoria, pm.precio_unitario,
                   pm.unidad_medida, pm.fuente::text AS fuente, pm.fecha_vigencia, pm.evidencia, pm.justificacion
            FROM modulo6.calculos_valor_razonable c
            JOIN modulo6.precios_mercado pm ON pm.id_precio_mercado = c.id_precio_mercado
            JOIN modulo9.especies e ON e.id_especie = pm.id_especie
            WHERE c.id_periodo_contable = :p ORDER BY 2, 6""", p)
        supuestos = filas(self.db, f"""
            SELECT DISTINCT ON (c.id_activo_biologico)
                   c.id_activo_biologico, c.magnitud, c.unidad_magnitud, c.precio_unitario, c.valor_razonable_bruto,
                   c.valor_neto, c.metodo_costo::text AS metodo_costo, c.tiene_valor_estimado, c.json_metodo_costo,
                   m.supuestos_aplicados,
                   COALESCE(NULLIF(btrim(c.json_metodo_costo->>'fuente_precio'), ''),
                            NULLIF(btrim(m.supuestos_aplicados->>'fuente'), ''), pm.fuente::text) AS fuente
            FROM modulo6.calculos_valor_razonable c
            LEFT JOIN modulo6.precios_mercado pm ON pm.id_precio_mercado = c.id_precio_mercado
            LEFT JOIN LATERAL (
                SELECT supuestos_aplicados FROM modulo6.mediciones_posteriores mp
                 WHERE mp.id_calculo_actual = c.id_calculo_valor_razonable
                   AND mp.id_activo_biologico = c.id_activo_biologico
                   AND mp.id_periodo_contable = c.id_periodo_contable
                 ORDER BY mp.fecha_medicion DESC, mp.id_medicion_posterior DESC LIMIT 1
            ) m ON true
            WHERE c.id_activo_biologico = ANY(:activos) AND c.estado = 'CALCULADO'
              AND {ES_BASE_C} AND {_hasta("c.id_periodo_contable", "<=")}
            ORDER BY c.id_activo_biologico, c.fecha_calculo DESC, c.id_calculo_valor_razonable DESC
        """, {**rango, "activos": [a["id_activo_biologico"] for a in activos]})
        # TC-M06-G64: los riesgos climáticos son las alertas ambientales de Telemetría (RF-57); la descartada no fue
        # un riesgo. Los días se cuentan en la zona de quien genera el informe.
        riesgos = filas(self.db, f"""
            SELECT 'CLIMATICO' AS categoria, al.tipo_alerta::text AS tipo, count(*) AS cantidad
            FROM modulo3.alertas al LEFT JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = al.id_activo_biologico
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = COALESCE(al.id_infraestructura, a.id_infraestructura)
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            WHERE f.numero_id_tributaria = :nit AND al.tipo_alerta::text IN {ALERTAS_CLIMATICAS}
              AND al.estado_alerta <> 'DESCARTADA' AND (al.fecha_evento AT TIME ZONE :tz)::date BETWEEN :i AND :f
            GROUP BY 1, 2
            UNION ALL
            SELECT 'SANITARIO', es.tipo::text, count(*)
            FROM modulo2.eventos_sanitarios es JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            WHERE f.numero_id_tributaria = :nit AND (ea.fecha AT TIME ZONE :tz)::date BETWEEN :i AND :f GROUP BY 1, 2
            UNION ALL
            SELECT 'BAJA', eb.tipo::text, count(*)
            FROM modulo2.eventos_bajas eb JOIN modulo2.eventos_activos ea ON ea.id_eventos = eb.id_evento
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            WHERE f.numero_id_tributaria = :nit AND (ea.fecha AT TIME ZONE :tz)::date BETWEEN :i AND :f GROUP BY 1, 2
            UNION ALL
            SELECT 'MERCADO', 'PRECIO_ESTIMADO', count(*) FROM modulo6.calculos_valor_razonable
            WHERE id_periodo_contable = :p AND tiene_valor_estimado
            HAVING count(*) > 0""", {**rango, "tz": nombre_zona_usuario()})
        cierre = fila(self.db, """SELECT activos_excluidos, id_cierre FROM modulo6.ejecuciones_cierre_periodo
                                  WHERE id_periodo_contable = :p AND estado = 'COMPLETADO' ORDER BY id_cierre DESC LIMIT 1""", p)
        estado = fila(self.db, """SELECT resultado_neto FROM modulo6.estados_resultados_periodo
                                  WHERE id_periodo_contable = :p AND json_filtros = '{}'::jsonb
                                  ORDER BY version DESC LIMIT 1""", p)
        costos = fila(self.db, """SELECT COALESCE(sum(CASE WHEN es_reverso THEN -monto_costo ELSE monto_costo END), 0) AS total
                                  FROM modulo6.registros_costos WHERE id_periodo_contable = :p
                                    AND naturaleza_costo = 'MANTENIMIENTO' AND estado = 'REGISTRADO'""", p)
        return {"periodo": periodo, "activos": activos, "movimientos": movimientos, "trasladadas": trasladadas,
                "ingresos": ingresos, "precios": precios,
                "supuestos": supuestos, "riesgos": riesgos, "cierre": cierre,
                "resultado_neto_estado": estado["resultado_neto"] if estado else None,
                "costos_mantenimiento": costos["total"]}

    def agregar_informe(self, datos: dict) -> int:
        """Guarda un informe de revelaciones y devuelve su id."""
        return escribir(self.db, """
            INSERT INTO modulo6.informes_revelacion_nic41 (id_periodo_contable, version_informe, estado, contenido_jsonb,
                supuestos_valuacion, activos_sin_mercado_json, riesgos_identificados, hash_informe, id_usuario_solicitante)
            VALUES (:p, :version, 'BORRADOR', CAST(:contenido AS jsonb), CAST(:supuestos AS jsonb), CAST(:costo AS jsonb),
                CAST(:riesgos AS jsonb), :hash, :u)
            RETURNING id_informe""", {**datos, "contenido": a_json(datos["contenido"]), "supuestos": a_json(datos["supuestos"]),
                                      "costo": a_json(datos["costo"]), "riesgos": a_json(datos["riesgos"])})

    def obtener_informe(self, id_informe: int) -> Optional[dict]:
        """Devuelve el informe, o ``None``."""
        informe = fila(self.db, f"""SELECT i.id_informe, i.id_periodo_contable, i.version_informe, i.estado::text AS estado,
                                           i.contenido_jsonb AS contenido, i.hash_informe, i.id_contador_aprobador, i.fecha_aprobacion,
                                           i.razon_rechazo, i.id_usuario_solicitante, i.fecha_generacion
                                    FROM modulo6.informes_revelacion_nic41 i
                                    WHERE i.id_informe = :id AND {alcance_periodo('i.id_periodo_contable')}""", {"id": id_informe})
        return con_nombres(self.db, [informe], _APROBADOR_INFORME)[0] if informe else None

    def periodo_de_informe(self, id_informe: int) -> Optional[int]:
        """Período del informe aunque la RLS se lo oculte a quien consulta (RFC-027: 403 y no 404). Solo el id."""
        with como_sistema(self.db):
            f = fila(self.db, "SELECT id_periodo_contable FROM modulo6.informes_revelacion_nic41 WHERE id_informe = :id",
                     {"id": id_informe})
        return f["id_periodo_contable"] if f else None

    def periodo_de_estado(self, id_estado: int) -> Optional[int]:
        """Período del estado de resultados aunque la RLS se lo oculte a quien consulta (RFC-027). Solo el id."""
        with como_sistema(self.db):
            f = fila(self.db, "SELECT id_periodo_contable FROM modulo6.estados_resultados_periodo WHERE id_estado = :id",
                     {"id": id_estado})
        return f["id_periodo_contable"] if f else None

    def aprobar_informe(self, id_informe: int, id_usuario: int) -> None:
        """Aprueba y archiva la versión APROBADA anterior del período (RF-92 R4)."""
        informe = self.obtener_informe(id_informe)
        escribir(self.db, """UPDATE modulo6.informes_revelacion_nic41 SET estado = 'ARCHIVADO'
                             WHERE id_periodo_contable = :p AND estado = 'APROBADO'""", {"p": informe["id_periodo_contable"]})
        escribir(self.db, """UPDATE modulo6.informes_revelacion_nic41
                             SET estado = 'APROBADO', id_contador_aprobador = :u, fecha_aprobacion = now()
                             WHERE id_informe = :id AND estado = 'BORRADOR'""", {"id": id_informe, "u": id_usuario})

    def rechazar_informe(self, id_informe: int, razon: str) -> None:
        """Rechaza el informe con su razón."""
        escribir(self.db, """UPDATE modulo6.informes_revelacion_nic41 SET estado = 'RECHAZADO', razon_rechazo = :r
                             WHERE id_informe = :id AND estado = 'BORRADOR'""", {"id": id_informe, "r": razon})

    def listar_informes(self, id_periodo_contable: int) -> list[dict]:
        """Lista los informes del periodo."""
        informes = con_nombres(self.db, filas(self.db, f"""
            SELECT i.id_informe, i.version_informe, i.estado::text AS estado, i.fecha_generacion, i.fecha_aprobacion,
                   i.razon_rechazo, i.hash_informe, i.id_contador_aprobador
            FROM modulo6.informes_revelacion_nic41 i
            WHERE i.id_periodo_contable = :p AND {alcance_periodo('i.id_periodo_contable')}
            ORDER BY i.id_informe DESC""", {"p": id_periodo_contable}), _APROBADOR_INFORME)
        for informe in informes:  # el listado no expone ids de usuario
            del informe["id_contador_aprobador"]
        return informes

    def siguiente_version_informe(self, id_periodo_contable: int) -> int:
        """Siguiente número de versión del informe."""
        return fila(self.db, "SELECT count(*) + 1 AS v FROM modulo6.informes_revelacion_nic41 WHERE id_periodo_contable = :p",
                    {"p": id_periodo_contable})["v"]
