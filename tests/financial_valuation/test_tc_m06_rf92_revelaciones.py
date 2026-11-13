# | Fecha      | Nombre         | Que se hizo                                                           |
# |------------|----------------|-----------------------------------------------------------------------|
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G62 RF-92: la conciliación suma los ingresos de individuos sin costo |
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G67 RF-92: estado por sección y aprobación bloqueada |
"""Informe de revelaciones NIC 41 (RF-92), sin base de datos.

- TC-M06-G62 (#1107): el ingreso de individuos a un lote por compra, donación o traslado sube el valor del
  activo sin asentar líneas; la conciliación (¶50) lo suma para que inicio + movimientos = cierre.
- TC-M06-G67 (#1110): el informe expone el estado de cada sección (Restricción 6) y una sección BLOQUEADA
  impide aprobarlo.
"""
from datetime import date
from decimal import Decimal as D

import pytest

from src.financial_valuation.application.services.reportes import FUENTES_SECCION, ConstructorInformeRevelaciones
from src.financial_valuation.application.use_cases.reportes.generar_informe_revelaciones_use_case import (
    GenerarInformeRevelacionesUseCase,
)
from src.shared.errors import BusinessRuleError

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


def _estados(contenido):
    return {s["seccion"]: s for s in contenido["estado_secciones"]}


def test_el_informe_expone_el_estado_de_cada_seccion():
    contenido = ConstructorInformeRevelaciones(_Reportes([_activo(1, D("100"), D("100"))])).construir(
        7, {"declaracion_sin_novedad": True})["contenido"]

    estados = _estados(contenido)
    assert set(estados) == set(FUENTES_SECCION)
    assert {s["estado"] for s in estados.values()} == {"COMPLETA"}
    assert all(s["titulo"] and s["fuente"] for s in estados.values())
    assert estados["parr_53_riesgos"]["obligatoria"] is False and estados["parr_50_conciliacion"]["obligatoria"] is True


def test_activo_al_costo_sin_vida_util_bloquea_su_seccion_y_cita_la_fuente():
    al_costo = _activo(9, None, None, valor_contable_por_costo=D("500000"), razon_sin_mercado="Sin mercado activo",
                       costo_base=D("600000"), depreciacion_acumulada=D("100000"), deterioro_acumulado=D("0"))
    reportes = _Reportes([al_costo])
    reportes.datos["resultado_neto_estado"] = None

    estados = _estados(ConstructorInformeRevelaciones(reportes).construir(7, {"declaracion_sin_novedad": True})["contenido"])

    costo = estados["parr_54_56_activos_al_costo"]
    assert costo["estado"] == "BLOQUEADA" and costo["fuente"] == "Valoración por costo"
    assert "BOV-9" in costo["motivo"] and "vida útil" in costo["motivo"]
    assert estados["parr_40_ganancias_perdidas"]["estado"] == "ADVERTENCIA"  # se justifica (FA-2), no bloquea


class _Informes:
    def __init__(self, contenido):
        self.informe = {"id_informe": 41, "id_periodo_contable": 219, "version_informe": "2026-M11-V1",
                        "estado": "BORRADOR", "contenido": contenido}
        self.aprobado = False

    def obtener_informe(self, id_informe):
        return self.informe

    def aprobar_informe(self, id_informe, id_usuario):
        self.aprobado = True


def test_una_seccion_bloqueada_impide_aprobar_el_informe():
    reportes = _Informes({"estado_secciones": [
        {"seccion": "parr_54_56_activos_al_costo", "titulo": "Activos medidos al costo (¶54-56)", "obligatoria": True,
         "estado": "BLOQUEADA", "fuente": "Valoración por costo", "motivo": "El activo BOV-9 no tiene vida útil registrada."}]})
    caso = GenerarInformeRevelacionesUseCase(db=None, periodos=None, reportes=reportes, constructor=None, auditoria=None)

    with pytest.raises(BusinessRuleError) as error:
        caso.resolver(41, True, None, 5)

    assert error.value.code == "INFORME_SECCIONES_BLOQUEADAS"
    assert "Activos medidos al costo" in error.value.message and "Valoración por costo" in error.value.message
    assert not reportes.aprobado
