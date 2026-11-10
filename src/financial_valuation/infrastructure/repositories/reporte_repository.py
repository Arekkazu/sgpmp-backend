# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-92/RF-93: insumos y persistencia de revelaciones y estado de resultados |
# | 2026-11-09 | destroyerban | INC-M06-320-G24 RF-85 FA-4: la cosecha del 100 % deja el activo en cero e inicia su baja |
"""Implementación SQL de :class:`ReporteRepository`."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.repositories.reporte_repository import ReporteRepository
from src.financial_valuation.infrastructure.repositories.sql import CONSUMIDO_POR_COSECHA, a_json, escribir, fila, filas

ES_BASE_C = "COALESCE((c.json_metodo_costo->>'es_producto')::boolean, false) = false"
CONSUMIDO_C = CONSUMIDO_POR_COSECHA.format(calculo="c.id_calculo_valor_razonable")  # RF-85 FA-4: vale 0

_FILTROS = (("id_especie", "l.id_especie = :id_especie"), ("id_activo_biologico", "l.id_activo_biologico = :id_activo_biologico"),
            ("id_infraestructura", "a.id_infraestructura = :id_infraestructura"), ("id_finca", "l.id_finca = :id_finca"))


class SqlAlchemyReporteRepository(ReporteRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- RF-93 ---------------------------------------------------------------------------------

    def movimientos(self, id_periodo_contable: int, filtros: dict) -> list[dict]:
        condiciones, params = ["l.id_periodo_contable = :p", "l.estado = 'REGISTRADA'"], {"p": id_periodo_contable}
        for campo, sql in _FILTROS:
            if filtros.get(campo):
                condiciones.append(sql)
                params[campo] = filtros[campo]
        return filas(self.db, f"""
            SELECT l.id_linea_asiento_nic41, COALESCE(l.tipo_hecho_corregido, l.tipo_hecho)::text AS tipo_hecho,
                   l.sentido::text AS sentido, l.valor, l.es_reverso, l.id_activo_biologico, a.identificador AS activo,
                   l.id_especie, l.id_finca, a.id_infraestructura, l.id_comprobante_nic41
            FROM modulo6.lineas_asiento_nic41 l
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = l.id_activo_biologico
            WHERE {' AND '.join(condiciones)}""", params)

    def agregar_estado(self, datos: dict) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.estados_resultados_periodo (id_periodo_contable, total_ingresos_transformacion,
                total_ingresos_precio_mercado, total_ingresos_cosecha, total_gastos_mantenimiento, total_bajas_deterioro,
                resultado_neto, estado, hash_consistencia, fecha_generacion, total_ingresos, total_gastos, json_componentes,
                json_filtros, version, id_usuario)
            VALUES (:p, :ing_tb, :ing_pm, :ing_cosecha, :gastos_mant, :bajas, :neto, 'GENERADO', :hash, now(), :ingresos,
                :gastos, CAST(:componentes AS jsonb), CAST(:filtros AS jsonb), :version, :u)
            RETURNING id_estado""", {**datos, "componentes": a_json(datos["componentes"]), "filtros": a_json(datos["filtros"])})

    def obtener_estado(self, id_estado: int) -> Optional[dict]:
        return fila(self.db, """SELECT id_estado, id_periodo_contable, total_ingresos, total_gastos, resultado_neto, estado,
                                       hash_consistencia, fecha_generacion, json_componentes AS componentes,
                                       json_filtros AS filtros, version, id_usuario, id_usuario_aprobador, fecha_aprobacion
                                FROM modulo6.estados_resultados_periodo WHERE id_estado = :id""", {"id": id_estado})

    def aprobar_estado(self, id_estado: int, id_usuario: int) -> None:
        escribir(self.db, """UPDATE modulo6.estados_resultados_periodo
                             SET estado = 'APROBADO', id_usuario_aprobador = :u, fecha_aprobacion = now()
                             WHERE id_estado = :id AND estado = 'GENERADO'""", {"id": id_estado, "u": id_usuario})

    def listar_estados(self, id_periodo_contable: int) -> list[dict]:
        return filas(self.db, """SELECT id_estado, id_periodo_contable, total_ingresos, total_gastos, resultado_neto, estado,
                                        fecha_generacion, json_filtros AS filtros, version, fecha_aprobacion
                                 FROM modulo6.estados_resultados_periodo WHERE id_periodo_contable = :p
                                 ORDER BY version DESC""", {"p": id_periodo_contable})

    def siguiente_version_estado(self, id_periodo_contable: int) -> int:
        return fila(self.db, """SELECT COALESCE(max(version), 0) + 1 AS v FROM modulo6.estados_resultados_periodo
                                WHERE id_periodo_contable = :p""", {"p": id_periodo_contable})["v"]

    # --- RF-92 ---------------------------------------------------------------------------------

    def datos_revelaciones(self, id_periodo_contable: int) -> dict:
        p = {"p": id_periodo_contable}
        periodo = fila(self.db, """SELECT id_periodo_contable, numero_id_tributaria, fecha_inicio, fecha_fin,
                                          tipo_cierre::text AS tipo_cierre FROM modulo6.periodos_contables
                                   WHERE id_periodo_contable = :p""", p)
        rango = {**p, "nit": periodo["numero_id_tributaria"], "i": periodo["fecha_inicio"], "f": periodo["fecha_fin"]}
        activos = filas(self.db, f"""
            SELECT a.id_activo_biologico, a.identificador, a.tipo::text AS tipo, e.id_especie, e.nombre AS especie,
                   ri.clasificacion::text AS clasificacion, ri.indicador_valoracion::text AS indicador_valoracion,
                   ri.origen_financiero::text AS origen_financiero, ri.costo_adquisicion,
                   ri.fecha_creacion::date AS fecha_reconocimiento, d.cantidad_actual,
                   (SELECT CASE WHEN {CONSUMIDO_C} THEN 0 ELSE c.valor_neto END FROM modulo6.calculos_valor_razonable c
                     WHERE c.id_activo_biologico = a.id_activo_biologico AND c.estado = 'CALCULADO' AND {ES_BASE_C} AND c.fecha_calculo::date < :i
                     ORDER BY c.fecha_calculo DESC, c.id_calculo_valor_razonable DESC LIMIT 1) AS valor_inicio,
                   (SELECT CASE WHEN {CONSUMIDO_C} THEN 0 ELSE c.valor_neto END FROM modulo6.calculos_valor_razonable c
                     WHERE c.id_activo_biologico = a.id_activo_biologico AND c.estado = 'CALCULADO' AND {ES_BASE_C} AND c.fecha_calculo::date <= :f
                     ORDER BY c.fecha_calculo DESC, c.id_calculo_valor_razonable DESC LIMIT 1) AS valor_cierre,
                   vc.valor_contable_por_costo, vc.razon_sin_mercado, vc.vida_util_meses, vc.depreciacion_acumulada,
                   vc.deterioro_acumulado, vc.costos_adquisicion AS costo_base
            FROM modulo6.reconocimientos_iniciales ri
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = ri.id_activo_biologico
            JOIN modulo9.especies e ON e.id_especie = a.id_especie
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d ON d.id_activo_biologico = a.id_activo_biologico
            LEFT JOIN modulo6.valoraciones_por_costos vc ON vc.id_activo_biologico = a.id_activo_biologico AND vc.es_activa
            WHERE ri.estado = 'CONFIRMADO' AND f.numero_id_tributaria = :nit AND ri.fecha_creacion::date <= :f
            ORDER BY e.nombre, a.identificador""", rango)
        movimientos = filas(self.db, """
            SELECT l.id_activo_biologico, COALESCE(l.tipo_hecho_corregido, l.tipo_hecho)::text AS tipo_hecho,
                   l.sentido::text AS sentido, l.es_reverso, sum(l.valor) AS valor
            FROM modulo6.lineas_asiento_nic41 l WHERE l.id_periodo_contable = :p
            GROUP BY 1, 2, 3, 4""", p)
        precios = filas(self.db, """
            SELECT DISTINCT pm.id_precio_mercado, e.nombre AS especie, pm.categoria[1]::text AS categoria, pm.precio_unitario,
                   pm.unidad_medida, pm.fuente::text AS fuente, pm.fecha_vigencia, pm.evidencia, pm.justificacion
            FROM modulo6.calculos_valor_razonable c
            JOIN modulo6.precios_mercado pm ON pm.id_precio_mercado = c.id_precio_mercado
            JOIN modulo9.especies e ON e.id_especie = pm.id_especie
            WHERE c.id_periodo_contable = :p ORDER BY 2, 6""", p)
        supuestos = filas(self.db, """
            SELECT c.id_activo_biologico, c.magnitud, c.unidad_magnitud, c.precio_unitario, c.valor_razonable_bruto,
                   c.valor_neto, c.metodo_costo::text AS metodo_costo, c.tiene_valor_estimado, c.json_metodo_costo
            FROM modulo6.calculos_valor_razonable c
            WHERE c.id_periodo_contable = :p AND c.estado = 'CALCULADO'
              AND c.id_calculo_valor_razonable = (SELECT max(c2.id_calculo_valor_razonable) FROM modulo6.calculos_valor_razonable c2
                                                  WHERE c2.id_activo_biologico = c.id_activo_biologico
                                                    AND c2.id_periodo_contable = :p AND c2.estado = 'CALCULADO')""", p)
        riesgos = filas(self.db, """
            SELECT 'SANITARIO' AS categoria, es.tipo::text AS tipo, count(*) AS cantidad
            FROM modulo2.eventos_sanitarios es JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            WHERE f.numero_id_tributaria = :nit AND ea.fecha::date BETWEEN :i AND :f GROUP BY 1, 2
            UNION ALL
            SELECT 'BAJA', eb.tipo::text, count(*)
            FROM modulo2.eventos_bajas eb JOIN modulo2.eventos_activos ea ON ea.id_eventos = eb.id_evento
            JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = ea.id_activo_biologico
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            JOIN modulo9.fincas f ON f.id_finca = i.id_finca
            WHERE f.numero_id_tributaria = :nit AND ea.fecha::date BETWEEN :i AND :f GROUP BY 1, 2
            UNION ALL
            SELECT 'MERCADO', 'PRECIO_ESTIMADO', count(*) FROM modulo6.calculos_valor_razonable
            WHERE id_periodo_contable = :p AND tiene_valor_estimado
            HAVING count(*) > 0""", rango)
        cierre = fila(self.db, """SELECT activos_excluidos, id_cierre FROM modulo6.ejecuciones_cierre_periodo
                                  WHERE id_periodo_contable = :p AND estado = 'COMPLETADO' ORDER BY id_cierre DESC LIMIT 1""", p)
        estado = fila(self.db, """SELECT resultado_neto FROM modulo6.estados_resultados_periodo
                                  WHERE id_periodo_contable = :p AND json_filtros = '{}'::jsonb
                                  ORDER BY version DESC LIMIT 1""", p)
        costos = fila(self.db, """SELECT COALESCE(sum(CASE WHEN es_reverso THEN -monto_costo ELSE monto_costo END), 0) AS total
                                  FROM modulo6.registros_costos WHERE id_periodo_contable = :p
                                    AND naturaleza_costo = 'MANTENIMIENTO' AND estado = 'REGISTRADO'""", p)
        return {"periodo": periodo, "activos": activos, "movimientos": movimientos, "precios": precios,
                "supuestos": supuestos, "riesgos": riesgos, "cierre": cierre,
                "resultado_neto_estado": estado["resultado_neto"] if estado else None,
                "costos_mantenimiento": costos["total"]}

    def agregar_informe(self, datos: dict) -> int:
        return escribir(self.db, """
            INSERT INTO modulo6.informes_revelacion_nic41 (id_periodo_contable, version_informe, estado, contenido_jsonb,
                supuestos_valuacion, activos_sin_mercado_json, riesgos_identificados, hash_informe, id_usuario_solicitante)
            VALUES (:p, :version, 'BORRADOR', CAST(:contenido AS jsonb), CAST(:supuestos AS jsonb), CAST(:costo AS jsonb),
                CAST(:riesgos AS jsonb), :hash, :u)
            RETURNING id_informe""", {**datos, "contenido": a_json(datos["contenido"]), "supuestos": a_json(datos["supuestos"]),
                                      "costo": a_json(datos["costo"]), "riesgos": a_json(datos["riesgos"])})

    def obtener_informe(self, id_informe: int) -> Optional[dict]:
        return fila(self.db, """SELECT id_informe, id_periodo_contable, version_informe, estado::text AS estado,
                                       contenido_jsonb AS contenido, hash_informe, id_contador_aprobador, fecha_aprobacion,
                                       razon_rechazo, id_usuario_solicitante, fecha_generacion
                                FROM modulo6.informes_revelacion_nic41 WHERE id_informe = :id""", {"id": id_informe})

    def aprobar_informe(self, id_informe: int, id_usuario: int) -> None:
        informe = self.obtener_informe(id_informe)
        escribir(self.db, """UPDATE modulo6.informes_revelacion_nic41 SET estado = 'ARCHIVADO'
                             WHERE id_periodo_contable = :p AND estado = 'APROBADO'""", {"p": informe["id_periodo_contable"]})
        escribir(self.db, """UPDATE modulo6.informes_revelacion_nic41
                             SET estado = 'APROBADO', id_contador_aprobador = :u, fecha_aprobacion = now()
                             WHERE id_informe = :id AND estado = 'BORRADOR'""", {"id": id_informe, "u": id_usuario})

    def rechazar_informe(self, id_informe: int, razon: str) -> None:
        escribir(self.db, """UPDATE modulo6.informes_revelacion_nic41 SET estado = 'RECHAZADO', razon_rechazo = :r
                             WHERE id_informe = :id AND estado = 'BORRADOR'""", {"id": id_informe, "r": razon})

    def listar_informes(self, id_periodo_contable: int) -> list[dict]:
        return filas(self.db, """SELECT id_informe, version_informe, estado::text AS estado, fecha_generacion,
                                        fecha_aprobacion, razon_rechazo, hash_informe
                                 FROM modulo6.informes_revelacion_nic41 WHERE id_periodo_contable = :p
                                 ORDER BY id_informe DESC""", {"p": id_periodo_contable})

    def siguiente_version_informe(self, id_periodo_contable: int) -> int:
        return fila(self.db, "SELECT count(*) + 1 AS v FROM modulo6.informes_revelacion_nic41 WHERE id_periodo_contable = :p",
                    {"p": id_periodo_contable})["v"]
