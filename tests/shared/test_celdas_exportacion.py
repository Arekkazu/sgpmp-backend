"""Las exportaciones a CSV y Excel guardan el texto libre como texto, nunca como fórmula."""
import csv
import io
import zipfile

from openpyxl import Workbook, load_workbook

from src.shared.celdas_seguras import proteger_libro, texto_seguro_csv
from src.supplies.application.use_cases.exportacion.generador_archivos import (
    Documento,
    generar_csv,
    generar_excel,
)

_CARGA = '=SUM(A1,A2)'


def test_csv_antepone_apostrofo_al_texto_peligroso():
    for valor in (_CARGA, "+1+1", "-1+cmd|' /C calc'!A0", "@SUM(1,1)", "\t=1", "\r=1"):
        assert texto_seguro_csv(valor) == "'" + valor


def test_csv_no_toca_numeros_ni_texto_normal():
    for valor in ("-12,5", "-1.000.000", "+3", "1e-3", "-4%", "Vacuna aftosa", "", "a=b"):
        assert texto_seguro_csv(valor) == valor
    assert texto_seguro_csv(-5) == -5
    assert texto_seguro_csv(None) is None


def test_proteger_libro_deja_el_texto_igual_pero_como_texto():
    libro = Workbook()
    libro.active["A1"] = _CARGA
    libro.create_sheet("Otra")["B2"] = "=1+1"
    proteger_libro(libro)
    salida = io.BytesIO()
    libro.save(salida)
    leido = load_workbook(io.BytesIO(salida.getvalue()))
    assert leido.worksheets[0]["A1"].value == _CARGA
    assert leido.worksheets[0]["A1"].data_type == "s"
    assert leido.worksheets[1]["B2"].data_type == "s"
    with zipfile.ZipFile(io.BytesIO(salida.getvalue())) as z:
        hojas = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("xl/worksheets/"))
    assert "<f>" not in hojas


def _documento() -> Documento:
    return Documento(titulo="Historial", columnas=["Insumo", "Observación", "Costo"],
                     filas=[["Vacuna", _CARGA, "-1.500,00"]])


def test_generador_m05_m06_csv_neutraliza():
    filas = list(csv.reader(io.StringIO(generar_csv(_documento()).decode("utf-8"))))
    assert filas[1] == ["Vacuna", "'" + _CARGA, "-1.500,00"]


def test_generador_m05_m06_excel_sin_formulas():
    contenido = generar_excel(_documento())
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        hojas = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("xl/worksheets/"))
    assert "<f>" not in hojas
    assert load_workbook(io.BytesIO(contenido))["Datos"]["B2"].value == _CARGA


def test_reporte_m08_excel_sin_formulas():
    from src.reporting.domain.reportes.contenido import Columna, ContenidoReporte, Tabla
    from src.reporting.domain.reportes.solicitud import EXCEL
    from src.reporting.infrastructure.adapters.renderizador_reportes import RenderizadorReportes

    contenido = ContenidoReporte(
        titulo="Costos", encabezado=[("Finca", "La Esperanza")],
        resumen=[Tabla("Resumen", [Columna("c", "Concepto")], [{"c": _CARGA}])],
        detalle=Tabla("Detalle", [Columna("x", "Observación")], [{"x": _CARGA}]))
    archivo = RenderizadorReportes().renderizar(contenido, EXCEL, None)
    with zipfile.ZipFile(io.BytesIO(archivo)) as z:
        hojas = "".join(z.read(n).decode() for n in z.namelist() if n.startswith("xl/worksheets/"))
    assert "<f>" not in hojas
    assert load_workbook(io.BytesIO(archivo))["Datos Detallados"]["A2"].value == _CARGA
