# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-92/RF-93: construcción del estado de resultados y del informe de revelaciones |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-302-G01 RF-82/RF-86: hecho RECONOCIMIENTO_DONACION |
# | 2026-11-10 | Arekkazu | INC-M06-344-G42 RF-93: desglose de los costos de mantenimiento por tipo |
# | 2026-11-12 | LuisfNarvaez01 | INC-M06-359-G79 RF-93: los activos excluidos del cierre salen de todos los componentes y los montos van con 4 decimales |
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G62 RF-92: la conciliación suma los ingresos de individuos sin costo y omite los activos dados de baja antes |
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G67 RF-92: estado por sección (COMPLETA, ADVERTENCIA o BLOQUEADA) con su fuente y motivo |
"""Constructores de los reportes del período. No hacen commit: los usan el cierre (RF-87 paso 8) y
los casos de uso de generación a pedido del Contador."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable, Optional

from src.financial_valuation.domain.repositories.costo_repository import CostoRepository
from src.financial_valuation.domain.repositories.reporte_repository import ReporteRepository
from src.financial_valuation.domain.services.consolidacion import (
    CostoPeriodo,
    MovimientoResultado,
    estado_resultados,
)
from src.financial_valuation.domain.services.nic41 import CERO, hash_sha256, q4

ETIQUETAS_PERIODO = {"MENSUAL": "M", "TRIMESTRAL": "Q", "ANUAL": "A"}

SECCIONES_INFORME = {
    "parr_41_43_descripcion": "Descripción de los grupos de activos (¶41-43)",
    "parr_40_ganancias_perdidas": "Ganancia o pérdida del período (¶40)",
    "parr_51_separacion_precio_transformacion": "Separación entre precio y transformación biológica (¶51)",
    "parr_50_conciliacion": "Conciliación del valor en libros (¶50)",
    "niif13_93_metodos_y_supuestos": "Técnicas y datos de medición (NIIF 13 ¶93)",
    "niif13_93_precios_referencia": "Precios de referencia utilizados (NIIF 13 ¶93)",
    "parr_49_restricciones_compromisos": "Restricciones, garantías y compromisos (¶49)",
    "parr_53_riesgos": "Riesgos climáticos, sanitarios y otros (¶53)",
    "parr_54_56_activos_al_costo": "Activos medidos al costo (¶54-56)",
    "exclusiones_cierre": "Activos excluidos del cierre",
    "alertas_consistencia": "Alertas de consistencia",
}

# RF-92 Restricción 6: si una fuente impide completar una sección obligatoria, la sección queda BLOQUEADA y el
# informe no se aprueba; en una voluntaria (NIC 41 ¶51 y ¶53 se recomiendan, no se exigen) es una ADVERTENCIA.
# Una inconsistencia que el Contador puede justificar (FA-2) es ADVERTENCIA aun en una obligatoria.
FUENTES_SECCION = {
    "parr_41_43_descripcion": (True, "Reconocimiento inicial de los activos"),
    "parr_40_ganancias_perdidas": (True, "Estado de resultados del período"),
    "parr_51_separacion_precio_transformacion": (False, "Mediciones del valor razonable"),
    "parr_50_conciliacion": (True, "Cierre del período"),
    "niif13_93_metodos_y_supuestos": (True, "Mediciones del valor razonable"),
    "niif13_93_precios_referencia": (True, "Precios de mercado"),
    "parr_49_restricciones_compromisos": (True, "Revelaciones ingresadas por el Contador"),
    "parr_53_riesgos": (False, "Eventos sanitarios y bajas de los activos"),
    "parr_54_56_activos_al_costo": (True, "Valoración por costo"),
}


def estado_secciones(problemas: dict[str, list[tuple[bool, str]]]) -> list[dict]:
    """Estado de cada sección: ``problemas`` = sección -> [(impide completarla, motivo legible)]."""
    estados = []
    for clave, (obligatoria, fuente) in FUENTES_SECCION.items():
        lista = problemas.get(clave) or []
        estado = ("BLOQUEADA" if obligatoria and any(critico for critico, _ in lista)
                  else "ADVERTENCIA" if lista else "COMPLETA")
        estados.append({"seccion": clave, "titulo": SECCIONES_INFORME[clave], "obligatoria": obligatoria,
                        "estado": estado, "fuente": fuente, "motivo": "; ".join(m for _, m in lista) or None})
    return estados


class ConstructorEstadoResultados:
    def __init__(self, reportes: ReporteRepository, costos: CostoRepository) -> None:
        self.reportes = reportes
        self.costos = costos

    def calcular(self, id_periodo_contable: int, filtros: dict, excluir_activos: Iterable[int] = ()) -> dict:
        """``excluir_activos``: activos excluidos del cierre (RF-93 FA-3/FA-4); quedan fuera de todos los
        componentes, no solo listados (INC-M06-359-G79)."""
        consulta = {**filtros, "excluir_activos": sorted(set(excluir_activos))} if excluir_activos else filtros
        movimientos = self.reportes.movimientos(id_periodo_contable, consulta)
        costos = self.costos.del_periodo(id_periodo_contable, consulta)
        er = estado_resultados(
            [MovimientoResultado(m["tipo_hecho"], m["sentido"], Decimal(m["valor"]), m["es_reverso"]) for m in movimientos],
            [CostoPeriodo(c["naturaleza_costo"], c["politica_capitalizacion"], Decimal(c["monto_costo"]), c["es_reverso"],
                          c["subtipo_costo"]) for c in costos],
        )
        # Montos con 4 decimales también cuando son cero: "0.0000", no "0" (INC-M06-359-G79).
        return {"componentes": {k: str(q4(v)) for k, v in er.componentes.items()},
                "desglose_costos_mantenimiento": {k: str(q4(v)) for k, v in er.desglose_mantenimiento.items()},
                "total_ingresos": q4(er.total_ingresos),
                "total_gastos": q4(er.total_gastos), "resultado_neto": q4(er.resultado_neto),
                "sin_actividad": [k for k, v in er.componentes.items() if v == 0], "lineas": len(movimientos),
                "costos": len(costos)}

    def guardar(self, id_periodo_contable: int, filtros: dict, id_usuario: int, excluidos: list) -> dict:
        ids_excluidos = sorted({e["id_activo_biologico"] for e in excluidos if e.get("id_activo_biologico")})
        calculo = self.calcular(id_periodo_contable, filtros, ids_excluidos)
        excluidos = self._con_montos(id_periodo_contable, filtros, excluidos)
        componentes = {**calculo["componentes"], "desglose_costos_mantenimiento": calculo["desglose_costos_mantenimiento"],
                       "activos_excluidos_cierre": excluidos}
        c = {k: Decimal(v) for k, v in calculo["componentes"].items()}
        version = self.reportes.siguiente_version_estado(id_periodo_contable)
        id_estado = self.reportes.agregar_estado({
            "p": id_periodo_contable,
            "ing_tb": c["ganancia_transformacion_biologica"], "ing_pm": c["ganancia_precio_mercado"],
            "ing_cosecha": c["ingresos_productos_agricolas"], "gastos_mant": c["costos_mantenimiento"],
            "bajas": c["bajas_activos"], "neto": calculo["resultado_neto"], "ingresos": calculo["total_ingresos"],
            "gastos": calculo["total_gastos"], "componentes": componentes, "filtros": filtros, "version": version,
            "u": id_usuario, "hash": hash_sha256({"componentes": componentes, "filtros": filtros}),
        })
        return {**calculo, "id_estado": id_estado, "version": version, "activos_excluidos_cierre": excluidos}

    def _con_montos(self, id_periodo_contable: int, filtros: dict, excluidos: list) -> list:
        """RF-93: cada activo excluido se lista con los montos que quedaron fuera del estado."""
        resultado = []
        for e in excluidos:
            fila = dict(e)
            if e.get("id_activo_biologico"):
                propio = self.calcular(id_periodo_contable, {**filtros, "id_activo_biologico": e["id_activo_biologico"]})
                fila["montos_excluidos"] = {
                    "componentes": {k: v for k, v in propio["componentes"].items() if Decimal(v) != 0},
                    "total_ingresos": str(propio["total_ingresos"]), "total_gastos": str(propio["total_gastos"]),
                    "resultado_neto": str(propio["resultado_neto"]),
                }
            resultado.append(fila)
        return resultado


class ConstructorInformeRevelaciones:
    def __init__(self, reportes: ReporteRepository) -> None:
        self.reportes = reportes

    def construir(self, id_periodo_contable: int, manuales: dict) -> dict:
        d = self.reportes.datos_revelaciones(id_periodo_contable)
        periodo = d["periodo"]
        mov_activo: dict[int, dict] = defaultdict(lambda: defaultdict(lambda: CERO))
        for m in d["movimientos"]:
            signo = -1 if m["es_reverso"] else 1
            mov_activo[m["id_activo_biologico"]][f"{m['tipo_hecho']}:{m['sentido']}"] += signo * Decimal(m["valor"])
        # TC-M06-G62: el ingreso de individuos sin costo sube el valor sin asentar líneas; entra a la conciliación
        # como compra o, si fue donación o traslado, como otro ingreso.
        ingresos: dict[int, dict] = defaultdict(lambda: {"compra": CERO, "otros": CERO})
        for i in d.get("ingresos") or []:
            ingresos[i["id_activo_biologico"]]["compra" if i["tipo_ingreso"] == "compra" else "otros"] += Decimal(i["valor"] or 0)
        rollforward, alertas, activos = [], [], []
        problemas: dict[str, list[tuple[bool, str]]] = defaultdict(list)  # RF-92 R6 (TC-M06-G67)
        for a in d["activos"]:
            mov = mov_activo.get(a["id_activo_biologico"], {})
            ingreso = ingresos.get(a["id_activo_biologico"], {"compra": CERO, "otros": CERO})
            inicio = Decimal(a["valor_inicio"] or 0)
            reconocido_en_periodo = a["fecha_reconocimiento"] >= periodo["fecha_inicio"]
            compras = Decimal(a["costo_adquisicion"] or 0) if reconocido_en_periodo and a["origen_financiero"] == "compra" else CERO
            compras += ingreso["compra"]
            nacimientos = sum((v for k, v in mov.items() if k.startswith(("RECONOCIMIENTO_NACIMIENTO", "RECONOCIMIENTO_DONACION"))), CERO)
            nacimientos += ingreso["otros"]
            diferencia = mov.get("RECONOCIMIENTO_DIFERENCIA:GANANCIA", CERO) - mov.get("RECONOCIMIENTO_DIFERENCIA:PERDIDA", CERO)
            tb = mov.get("VARIACION_VR_TB:GANANCIA", CERO) - mov.get("VARIACION_VR_TB:PERDIDA", CERO)
            pm = mov.get("VARIACION_VR_PM:GANANCIA", CERO) - mov.get("VARIACION_VR_PM:PERDIDA", CERO)
            cosechas = mov.get("PRODUCTO_AGRICOLA:TRASLADO", CERO)
            bajas = sum((v for k, v in mov.items() if k.startswith("BAJA_ACTIVO")), CERO)
            depreciacion = sum((v for k, v in mov.items() if k.startswith(("DEPRECIACION", "DETERIORO"))), CERO)
            es_costo = a["valor_contable_por_costo"] is not None
            cierre = Decimal(a["valor_contable_por_costo"] if es_costo else (a["valor_cierre"] or 0))
            calculado = inicio + compras + nacimientos + diferencia + tb + pm - cosechas - bajas - depreciacion
            if not (inicio or cierre or compras or mov):  # dado de baja antes del período: nada que conciliar
                continue
            activos.append(a)
            if es_costo and not a["vida_util_meses"]:
                problemas["parr_54_56_activos_al_costo"].append((True, (
                    f"El activo {a['identificador']} valorado por costo no tiene vida útil registrada; "
                    "no se puede revelar su depreciación.")))
            if not es_costo and a["valor_cierre"] is None:
                problemas["parr_50_conciliacion"].append((True, (
                    f"El activo {a['identificador']} no tiene un valor razonable calculado al cierre del período.")))
            elif not es_costo and abs(calculado - cierre) > 1:
                alertas.append({"campo": "rollforward", "id_activo_biologico": a["id_activo_biologico"],
                                "detalle": f"Conciliación {calculado:.2f} vs valor al cierre {cierre:.2f}"})
                problemas["parr_50_conciliacion"].append((False, (
                    f"La conciliación del activo {a['identificador']} da {calculado:.2f} y su valor al cierre es {cierre:.2f}.")))
            rollforward.append({"id_activo_biologico": a["id_activo_biologico"], "identificador": a["identificador"],
                                "especie": a["especie"], "valor_inicio": inicio, "compras": compras,
                                "nacimientos_y_otros_ingresos": nacimientos + diferencia,
                                "transformacion_biologica": tb, "precio_mercado": pm, "cosechas": cosechas,
                                "bajas": bajas, "depreciacion_y_deterioro": depreciacion, "valor_cierre": cierre})
        por_especie: dict[str, dict] = defaultdict(lambda: {"cantidad_activos": 0, "valor_cierre": CERO, "clasificaciones": set()})
        for fila_rf, a in zip(rollforward, activos):
            g = por_especie[a["especie"]]
            g["cantidad_activos"] += 1
            g["valor_cierre"] += fila_rf["valor_cierre"]
            g["clasificaciones"].add(a["clasificacion"])
        total_tb = sum((r["transformacion_biologica"] for r in rollforward), CERO)
        total_pm = sum((r["precio_mercado"] for r in rollforward), CERO)
        total_reconocimiento = sum((r["nacimientos_y_otros_ingresos"] for r in rollforward), CERO)
        if d["resultado_neto_estado"] is None:
            alertas.append({"campo": "estado_resultados", "detalle": "El estado de resultados del período no está generado."})
            problemas["parr_40_ganancias_perdidas"].append((False, "El estado de resultados del período no está generado."))
        if (total_tb or total_pm) and not d["supuestos"]:
            problemas["niif13_93_metodos_y_supuestos"].append((True, (
                "Hay variaciones de valor razonable en el período sin los datos de su medición.")))
        if d["supuestos"] and not d["precios"]:
            problemas["niif13_93_precios_referencia"].append((True, (
                "Las mediciones del período no tienen el precio de mercado que usaron.")))
        a_costo = [a for a in activos if a["valor_contable_por_costo"] is not None]
        contenido = {
            "parr_41_43_descripcion": [{"especie": k, "cantidad_activos": v["cantidad_activos"],
                                        "valor_cierre": v["valor_cierre"], "clasificacion": sorted(v["clasificaciones"])}
                                       for k, v in sorted(por_especie.items())],
            "parr_40_ganancias_perdidas": {"reconocimiento_inicial": total_reconocimiento,
                                           "transformacion_biologica": total_tb, "precio_mercado": total_pm,
                                           "total": total_reconocimiento + total_tb + total_pm},
            "parr_51_separacion_precio_transformacion": {"transformacion_biologica": total_tb, "precio_mercado": total_pm},
            "niif13_93_metodos_y_supuestos": d["supuestos"] or "datos insuficientes",
            "niif13_93_precios_referencia": d["precios"],
            "parr_50_conciliacion": rollforward,
            "parr_54_56_activos_al_costo": [{"id_activo_biologico": a["id_activo_biologico"], "identificador": a["identificador"],
                                             "especie": a["especie"], "razon": a["razon_sin_mercado"],
                                             "metodo_depreciacion": "Línea recta", "vida_util_meses": a["vida_util_meses"],
                                             "costo": a["costo_base"], "depreciacion_acumulada": a["depreciacion_acumulada"],
                                             "deterioro_acumulado": a["deterioro_acumulado"],
                                             "valor_contable": a["valor_contable_por_costo"],
                                             "rango_valor_razonable": "No determinable"} for a in a_costo],
            "parr_49_restricciones_compromisos": {
                "compromisos": manuales.get("compromisos_vigentes") or [],
                "activos_pignorados": manuales.get("activos_pignorados") or [],
                "declaracion_sin_novedad": bool(manuales.get("declaracion_sin_novedad")),
            },
            "parr_53_riesgos": d["riesgos"],
            "exclusiones_cierre": (d["cierre"] or {}).get("activos_excluidos") or [],
        }
        contenido["estado_secciones"] = estado_secciones(problemas)
        return {"contenido": contenido, "supuestos": d["supuestos"], "costo": contenido["parr_54_56_activos_al_costo"],
                "riesgos": d["riesgos"], "alertas_consistencia": alertas, "periodo": periodo}

    def guardar(self, id_periodo_contable: int, manuales: dict, id_usuario: int,
                justificacion_inconsistencias: Optional[str] = None) -> dict:
        informe = self.construir(id_periodo_contable, manuales)
        periodo = informe["periodo"]
        numero = self.reportes.siguiente_version_informe(id_periodo_contable)
        etiqueta = ETIQUETAS_PERIODO.get(periodo["tipo_cierre"], "M")
        np = {"M": f"M{periodo['fecha_fin']:%m}", "Q": f"Q{(periodo['fecha_fin'].month - 1) // 3 + 1}", "A": "A"}[etiqueta]
        version = f"{periodo['fecha_fin']:%Y}-{np}-V{numero}"
        contenido = {**informe["contenido"], "alertas_consistencia": informe["alertas_consistencia"],
                     "justificacion_inconsistencias": justificacion_inconsistencias}
        id_informe = self.reportes.agregar_informe({
            "p": id_periodo_contable, "version": version, "contenido": contenido, "supuestos": informe["supuestos"],
            "costo": informe["costo"], "riesgos": informe["riesgos"], "u": id_usuario, "hash": hash_sha256(contenido),
        })
        return {"id_informe": id_informe, "version_informe": version, "alertas_consistencia": informe["alertas_consistencia"],
                "estado_secciones": contenido["estado_secciones"]}
