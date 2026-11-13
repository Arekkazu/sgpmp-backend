# | Fecha      | Nombre         | Que se hizo                                                           |
# |------------|----------------|-----------------------------------------------------------------------|
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G62 RF-92: la conciliación suma los ingresos de individuos sin costo |
"""Informe de revelaciones NIC 41 (RF-92), sin base de datos.

- TC-M06-G62 (#1107): el ingreso de individuos a un lote por compra, donación o traslado sube el valor del
  activo sin asentar líneas; la conciliación (¶50) lo suma para que inicio + movimientos = cierre.
"""
from datetime import date
from decimal import Decimal as D

from src.financial_valuation.application.services.reportes import ConstructorInformeRevelaciones

PERIODO = {"id_periodo_contable": 7, "numero_id_tributaria": "900000001", "fecha_inicio": date(2026, 11, 1),
           "fecha_fin": date(2026, 11, 30), "tipo_cierre": "MENSUAL"}


def _activo(id_activo, inicio, cierre, **extra):
    return {"id_activo_biologico": id_activo, "identificador": f"BOV-{id_activo}", "tipo": "POBLACIONAL", "id_especie": 2,
            "especie": "Bovino", "clasificacion": "CONSUMO", "indicador_valoracion": "VALOR_RAZONABLE",
            "origen_financiero": "nacimiento", "costo_adquisicion": None, "fecha_reconocimiento": date(2026, 10, 3),
            "cantidad_actual": 10, "valor_inicio": inicio, "valor_cierre": cierre, "valor_contable_por_costo": None,
            "razon_sin_mercado": None, "vida_util_meses": None, "depreciacion_acumulada": None,
            "deterioro_acumulado": None, "costo_base": None, **extra}


class _Reportes:
    def __init__(self, activos, movimientos=(), ingresos=()):
        self.datos = {"periodo": PERIODO, "activos": list(activos), "movimientos": list(movimientos),
                      "ingresos": list(ingresos), "precios": [], "supuestos": [], "riesgos": [], "cierre": None,
                      "resultado_neto_estado": D("1"), "costos_mantenimiento": D("0")}

    def datos_revelaciones(self, id_periodo_contable):
        return self.datos


def _linea(id_activo, tipo, sentido, valor):
    return {"id_activo_biologico": id_activo, "tipo_hecho": tipo, "sentido": sentido, "es_reverso": False, "valor": D(valor)}


def test_ingreso_de_individuos_sin_costo_entra_a_la_conciliacion():
    reportes = _Reportes(
        [_activo(1, D("2600000"), D("2954796"))],
        [_linea(1, "VARIACION_VR_TB", "GANANCIA", "188980")],
        [{"id_activo_biologico": 1, "tipo_ingreso": "compra", "valor": D("120000")},
         {"id_activo_biologico": 1, "tipo_ingreso": "donacion", "valor": D("45816")}])

    informe = ConstructorInformeRevelaciones(reportes).construir(7, {"declaracion_sin_novedad": True})

    [fila] = informe["contenido"]["parr_50_conciliacion"]
    assert fila["compras"] == D("120000") and fila["nacimientos_y_otros_ingresos"] == D("45816")
    calculado = (fila["valor_inicio"] + fila["compras"] + fila["nacimientos_y_otros_ingresos"]
                 + fila["transformacion_biologica"] + fila["precio_mercado"] - fila["cosechas"] - fila["bajas"]
                 - fila["depreciacion_y_deterioro"])
    assert abs(calculado - fila["valor_cierre"]) <= D("0.01")
    assert informe["alertas_consistencia"] == []


def test_activo_dado_de_baja_antes_del_periodo_no_se_concilia_ni_se_cuenta():
    reportes = _Reportes([_activo(1, D("100"), D("100")), _activo(2, D("0"), D("0"))])

    contenido = ConstructorInformeRevelaciones(reportes).construir(7, {"declaracion_sin_novedad": True})["contenido"]

    assert [f["id_activo_biologico"] for f in contenido["parr_50_conciliacion"]] == [1]
    assert contenido["parr_41_43_descripcion"][0]["cantidad_activos"] == 1
