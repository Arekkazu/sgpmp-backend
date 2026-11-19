# | Fecha      | Nombre   | Que se hizo                                                           |
# |------------|----------|-----------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: PDF carta (ReportLab) y Excel tipado (openpyxl) de reportes |
"""Render de un :class:`ContenidoReporte` a PDF o Excel (RF-104 Fase 3, CA-4, CA-11).

PDF (ReportLab): tamaño carta (horizontal si la tabla es ancha), letra de 10 puntos o más, encabezado con logo,
razón social, NIT, finca, período y fecha; «Página N de M» en cada página y, en la última, el sello del sistema
(y la firma del Contador en la valoración NIC 41). Las secciones van separadas por una línea con su nombre.

Excel (openpyxl): hoja «Resumen Ejecutivo» (encabezado, totales, tablas finales y advertencias) y «Datos
Detallados»; la ficha del animal y el ejecutivo llevan una hoja por sección. Montos y números como NUMBER con 2
decimales, fechas como DATE, sin celdas combinadas y la primera fila de cada hoja con los encabezados.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from typing import Any, Optional
from xml.sax.saxutils import escape

from src.reporting.domain.repositories.solicitud_reporte_repository import RenderizadorReportePort
from src.reporting.domain.reportes.contenido import (
    ENTERO,
    FECHA,
    FECHA_HORA,
    MONEDA,
    NUMERO,
    PORCENTAJE,
    SIN_DATO,
    ContenidoReporte,
    Tabla,
)
from src.reporting.domain.reportes.solicitud import EXCEL, PDF
from src.shared.fechas import en_zona_usuario

SELLO = "Generado por Sistema de Gestión Pecuaria Multiespecie — Universidad Surcolombiana"
_TIPOS = {PDF: "application/pdf", EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
_EXTENSIONES = {PDF: "pdf", EXCEL: "xlsx"}
_COLUMNAS_VERTICAL = 6
_FUENTE = 10  # CA-11: mínimo 10 puntos


def _miles(valor: Decimal, decimales: int) -> str:
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def texto_celda(valor: Any, tipo: str) -> str:
    """Valor de una celda como se lee en el PDF (formato colombiano: 1.639.000,00)."""
    if valor is None:
        return SIN_DATO
    if isinstance(valor, str):
        return valor
    if tipo == FECHA_HORA and isinstance(valor, datetime):
        return f"{en_zona_usuario(valor):%d/%m/%Y %H:%M}"
    if isinstance(valor, datetime):
        return f"{en_zona_usuario(valor):%d/%m/%Y}"
    if isinstance(valor, date):
        return f"{valor:%d/%m/%Y}"
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, (int, float, Decimal)):
        numero = Decimal(str(valor))
        if tipo == ENTERO:
            return _miles(numero, 0)
        if tipo == MONEDA:
            return f"$ {_miles(numero, 2)}"
        if tipo == PORCENTAJE:
            return f"{_miles(numero, 2)} %"
        return _miles(numero, 2)
    return str(valor)


class RenderizadorReportes(RenderizadorReportePort):

    def tipo_contenido(self, formato: str) -> str:
        return _TIPOS[formato]

    def extension(self, formato: str) -> str:
        return _EXTENSIONES[formato]

    def renderizar(self, contenido: ContenidoReporte, formato: str, ruta_logo: Optional[str]) -> bytes:
        return _pdf(contenido, ruta_logo) if formato == PDF else _excel(contenido)


# --- PDF ---------------------------------------------------------------------------------------

def _anchos_pdf(t: Tabla, ancho_util: float) -> list[float]:
    """Ancho de cada columna según su palabra más larga del título y lo típico de su contenido, para no partir
    palabras del encabezado."""
    pesos = []
    for c in t.columnas:
        palabra = max((len(p) for p in c.titulo.split()), default=4)
        contenido = [len(texto_celda(f.get(c.clave), c.tipo)) for f in t.filas[:50]]
        tipico = sorted(contenido)[len(contenido) // 2] if contenido else 4
        pesos.append(max(palabra + 1, min(tipico, 28), 5))
    total = sum(pesos)
    return [ancho_util * p / total for p in pesos]


def _lienzo(pie_final: list[str]):
    from reportlab.pdfgen import canvas

    class _Lienzo(canvas.Canvas):
        """Dos pasadas: primero se dibujan las páginas y al guardar se conoce el total («Página N de M»)."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._paginas: list[dict] = []

        def showPage(self):
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._paginas)
            for numero, estado in enumerate(self._paginas, start=1):
                self.__dict__.update(estado)
                ancho, _ = self._pagesize
                self.setFont("Helvetica", _FUENTE)
                self.drawRightString(ancho - 36, 22, f"Página {numero} de {total}")
                if numero == total:
                    for i, linea in enumerate(reversed(pie_final)):
                        self.drawString(36, 22 + i * 13, linea)
                super().showPage()
            super().save()

    return _Lienzo


def _pdf(contenido: ContenidoReporte, ruta_logo: Optional[str]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    tablas = contenido.resumen + ([contenido.detalle] if contenido.detalle else []) + contenido.finales + \
        [t for s in contenido.secciones for t in s.tablas]
    ancha = max((len(t.columnas) for t in tablas), default=0) > _COLUMNAS_VERTICAL
    pagina = landscape(letter) if ancha else letter
    estilos = getSampleStyleSheet()
    normal = ParagraphStyle("normal", parent=estilos["Normal"], fontSize=_FUENTE, leading=_FUENTE + 2)
    celda = ParagraphStyle("celda", parent=normal)
    cabecera = ParagraphStyle("cabecera", parent=normal, fontName="Helvetica-Bold", textColor=colors.white)
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], fontSize=16)
    subtitulo = ParagraphStyle("subtitulo", parent=estilos["Heading2"], fontSize=12)
    seccion = ParagraphStyle("seccion", parent=estilos["Heading2"], fontSize=13, spaceBefore=10)
    ancho_util = pagina[0] - 72

    def parrafo(texto: str, estilo=normal) -> Paragraph:
        return Paragraph(escape(texto), estilo)

    def tabla(t: Tabla) -> list:
        elementos: list = [parrafo(t.titulo, subtitulo)]
        datos = [[parrafo(c.titulo, cabecera) for c in t.columnas]]
        datos += [[parrafo(texto_celda(f.get(c.clave), c.tipo), celda) for c in t.columnas] for f in t.filas]
        if not t.filas:
            elementos.append(parrafo("Sin registros para los filtros elegidos."))
        else:
            grilla = Table(datos, colWidths=_anchos_pdf(t, ancho_util), repeatRows=1)
            grilla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f5d3a")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa79c")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f4f1")]),
            ]))
            elementos.append(grilla)
        if t.nota:
            elementos.append(parrafo(t.nota))
        elementos.append(Spacer(1, 10))
        return elementos

    historia: list = []
    if ruta_logo:
        try:
            historia.append(Image(ruta_logo, width=1.2 * inch, height=0.6 * inch, kind="proportional"))
        except Exception:
            pass  # un logo dañado no impide el reporte
    historia.append(parrafo("SIGAB · " + contenido.titulo, titulo))
    encabezado = Table([[parrafo(k, ParagraphStyle("k", parent=normal, fontName="Helvetica-Bold")), parrafo(v)]
                        for k, v in contenido.encabezado], colWidths=[ancho_util * 0.3, ancho_util * 0.7])
    encabezado.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    historia += [encabezado, Spacer(1, 8)]
    historia += [parrafo(a) for a in contenido.aclaraciones]
    for t in contenido.resumen:
        historia += tabla(t)
    if contenido.detalle:
        historia += tabla(contenido.detalle)
    for s in contenido.secciones:
        historia += [HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#2f5d3a")), parrafo(s.titulo, seccion)]
        historia += [parrafo(texto) for texto in s.textos]
        for t in s.tablas:
            historia += tabla(t)
    for t in contenido.finales:
        historia += tabla(t)
    if contenido.advertencias:
        historia.append(parrafo("Advertencias", subtitulo))
        historia += [parrafo(f"• {a}") for a in contenido.advertencias]
    if contenido.firma:
        historia.append(KeepTogether([Spacer(1, 18), parrafo("Firma electrónica", subtitulo),
                                      parrafo(contenido.firma)]))

    salida = io.BytesIO()
    documento = SimpleDocTemplate(salida, pagesize=pagina, leftMargin=36, rightMargin=36, topMargin=36,
                                  bottomMargin=60, title=contenido.titulo, author="SIGAB")
    documento.build(historia, canvasmaker=partial(_lienzo([SELLO])))
    return salida.getvalue()


# --- Excel -------------------------------------------------------------------------------------

_FORMATOS = {MONEDA: "#,##0.00", NUMERO: "#,##0.00", PORCENTAJE: "0.00", ENTERO: "0", FECHA: "yyyy-mm-dd",
             FECHA_HORA: "yyyy-mm-dd hh:mm"}


def _valor_excel(valor: Any, tipo: str) -> Any:
    """Montos y números como número; fechas como fecha (sin zona: Excel no la admite, va en la del usuario)."""
    if valor is None:
        return SIN_DATO
    if isinstance(valor, datetime):
        local = en_zona_usuario(valor).replace(tzinfo=None)
        return local.date() if tipo == FECHA else local
    if isinstance(valor, Decimal):
        return round(float(valor), 2)
    if isinstance(valor, float):
        return round(valor, 2)
    return valor


def _escribir_tabla(hoja, t: Tabla, fila: int, con_titulo: bool) -> int:
    from openpyxl.styles import Font

    if con_titulo:
        hoja.cell(row=fila, column=1, value=t.titulo).font = Font(bold=True)
        fila += 1
    for col, c in enumerate(t.columnas, start=1):
        hoja.cell(row=fila, column=col, value=c.titulo).font = Font(bold=True)
    for registro in t.filas:
        fila += 1
        for col, c in enumerate(t.columnas, start=1):
            valor = _valor_excel(registro.get(c.clave), c.tipo)
            celda = hoja.cell(row=fila, column=col, value=valor)
            if not isinstance(valor, str) and c.tipo in _FORMATOS:
                celda.number_format = _FORMATOS[c.tipo]
    if t.nota:
        fila += 1
        hoja.cell(row=fila, column=1, value=t.nota)
    return fila + 2


def _anchos(hoja) -> None:
    for columna in hoja.columns:
        largo = max((len(str(c.value)) for c in columna if c.value is not None), default=10)
        hoja.column_dimensions[columna[0].column_letter].width = min(max(largo + 2, 12), 60)


def _nombre_hoja(titulo: str, usados: set[str]) -> str:
    base = "".join(c for c in titulo if c not in "[]:*?/\\")[:31] or "Hoja"
    nombre, n = base, 2
    while nombre in usados:
        nombre = f"{base[:28]} {n}"
        n += 1
    usados.add(nombre)
    return nombre


def _excel(contenido: ContenidoReporte) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    libro = Workbook()
    resumen = libro.worksheets[0]
    resumen.title = "Resumen Ejecutivo"
    usados = {resumen.title}
    resumen.append(["Dato", "Valor"])
    for celda in resumen[1]:
        celda.font = Font(bold=True)
    resumen.append(["Reporte", contenido.titulo])
    for k, v in contenido.encabezado:
        resumen.append([k, v])
    fila = resumen.max_row + 2
    for texto in contenido.aclaraciones:
        resumen.cell(row=fila, column=1, value=texto)
        fila += 2
    for t in contenido.resumen + contenido.finales:
        fila = _escribir_tabla(resumen, t, fila, con_titulo=True)
    if contenido.advertencias:
        resumen.cell(row=fila, column=1, value="Advertencias").font = Font(bold=True)
        for a in contenido.advertencias:
            fila += 1
            resumen.cell(row=fila, column=1, value=a)
        fila += 2
    if contenido.firma:
        resumen.cell(row=fila, column=1, value="Firma electrónica").font = Font(bold=True)
        resumen.cell(row=fila + 1, column=1, value=contenido.firma)
    _anchos(resumen)

    if contenido.detalle is not None:
        hoja = libro.create_sheet(_nombre_hoja("Datos Detallados", usados))
        _escribir_tabla(hoja, contenido.detalle, 1, con_titulo=False)
        hoja.freeze_panes = "A2"
        _anchos(hoja)
    for s in contenido.secciones:
        hoja = libro.create_sheet(_nombre_hoja(s.titulo, usados))
        fila = 1
        if not s.tablas:
            hoja.append(["Dato", "Valor"])
            for texto in s.textos:
                hoja.append([s.titulo, texto])
        for i, t in enumerate(s.tablas):
            fila = _escribir_tabla(hoja, t, fila, con_titulo=i > 0)
        hoja.freeze_panes = "A2"
        _anchos(hoja)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
