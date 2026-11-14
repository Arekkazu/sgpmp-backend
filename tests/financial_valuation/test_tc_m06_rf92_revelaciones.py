# | Fecha      | Nombre         | Que se hizo                                                           |
# |------------|----------------|-----------------------------------------------------------------------|
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G62 RF-92: la conciliación suma los ingresos de individuos sin costo |
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G67 RF-92: estado por sección y aprobación bloqueada |
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G70 RF-92: el PDF del informe aprobado es PDF/A-1b |
# | 2026-11-13 | Arekkazu | Lote M05/M06 13-11: el activo de prueba trae su finca (supuestos por activo de #1119) |
"""Informe de revelaciones NIC 41 (RF-92), sin base de datos.

- TC-M06-G62 (#1107): el ingreso de individuos a un lote por compra, donación o traslado sube el valor del
  activo sin asentar líneas; la conciliación (¶50) lo suma para que inicio + movimientos = cierre.
- TC-M06-G67 (#1110): el informe expone el estado de cada sección (Restricción 6) y una sección BLOQUEADA
  impide aprobarlo.
- TC-M06-G70 (#1108): el PDF del informe aprobado declara y cumple PDF/A-1b (RNF-92-02).
"""
import io
import re
from datetime import date
from decimal import Decimal as D

import pytest

from src.financial_valuation.application.services.reportes import FUENTES_SECCION, ConstructorInformeRevelaciones
from src.financial_valuation.application.use_cases.reportes.exportar_reporte_use_case import ExportarReporteUseCase
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
            "cantidad_actual": 10, "id_finca": 1, "valor_inicio": inicio, "valor_cierre": cierre, "valor_contable_por_costo": None,
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
    caso = GenerarInformeRevelacionesUseCase(db=None, periodos=None, reportes=reportes, constructor=None, auditoria=None,
                                             notificador=None)

    with pytest.raises(BusinessRuleError) as error:
        caso.resolver(41, True, None, 5)

    assert error.value.code == "INFORME_SECCIONES_BLOQUEADAS"
    assert "Activos medidos al costo" in error.value.message and "Valoración por costo" in error.value.message
    assert not reportes.aprobado


def test_el_pdf_del_informe_aprobado_es_pdf_a_1b():
    from PIL import ImageCms

    reportes = _Informes({"parr_49_restricciones_compromisos": {"declaracion_sin_novedad": True},
                          "estado_secciones": [{"seccion": "parr_53_riesgos", "estado": "COMPLETA"}]})
    reportes.informe.update(estado="APROBADO", hash_informe="abc123", fecha_aprobacion=None)

    pdf, tipo, _, _ = ExportarReporteUseCase(periodos=None, reportes=reportes).informe(41, "pdf")

    assert tipo == "application/pdf" and pdf.startswith(b"%PDF-1.4\n%")
    assert b"<pdfaid:part>1</pdfaid:part>" in pdf and b"<pdfaid:conformance>B</pdfaid:conformance>" in pdf
    assert b"/S /GTS_PDFA1" in pdf and re.search(rb"/ID\s*\[", pdf)
    assert b"Helvetica" not in pdf and b"/FontFile2" in pdf  # todas las fuentes incrustadas
    assert not any(k in pdf for k in (b"/SMask", b"/Encrypt", b"/Group"))  # sin transparencias ni cifrado
    metadatos = re.search(rb"<<([^>]*?/Type /Metadata[^>]*?)>>\s*stream", pdf).group(1)
    assert b"/Filter" not in metadatos
    perfil = re.search(rb"<<\s*/Length (\d+) /N 3\s*>>\s*stream\n", pdf)
    icc = pdf[perfil.end():perfil.end() + int(perfil.group(1))]
    assert icc[8] == 2 and icc[12:20] == b"mntrRGB "  # ICC versión 2, monitor RGB
    assert ImageCms.ImageCmsProfile(io.BytesIO(icc)).profile.xcolor_space.strip() == "RGB"
    fecha = re.search(rb"/CreationDate \(D:(\d{14})", pdf).group(1).decode()
    assert f"<xmp:CreateDate>{fecha[:4]}-{fecha[4:6]}-{fecha[6:8]}T{fecha[8:10]}:{fecha[10:12]}".encode() in pdf
