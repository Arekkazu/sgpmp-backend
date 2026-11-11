# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77/RF-81: CSV, Excel y PDF             |
# | 2026-11-10 | Arekkazu         | CP088/CP111/TC-DIS-204 RF-77/80/81: PDF sin recorte, celdas con salto de línea, idioma y título; moneda legible |
"""Generación de archivos de exportación de M05 (RF-77 y RF-81).

- CSV en bloques de 1.000 filas (RF-77 "chunking" para > 5.000 registros): el
  archivo se arma completo antes de entregarse, nunca parcial (E6c).
- PDF con encabezado (logo si existe, título y fecha de generación) y 25
  registros por página (RF-77 "paginación automática"). Las columnas se reparten
  el ancho útil de la hoja según su contenido y cada celda hace salto de línea:
  ninguna columna queda fuera de la página (CP088, CP111). Con más de 10 columnas
  la hoja pasa a A3 horizontal para que el texto siga legible. El archivo declara
  idioma (es-CO), título, autor y muestra el título en la ventana del lector.
- Excel con encabezado en negrita, ancho de columna según el contenido y la fila
  de encabezados fija al desplazarse.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape
from typing import Iterable, Optional

FILAS_POR_PAGINA_PDF = 25
_COLUMNAS_A4 = 10  # más columnas que esto no caben legibles en A4 horizontal
_AUTOR = "SIGAB"
_BLOQUE_CSV = 1000


@dataclass
class Documento:
    """Contenido tabular a exportar, igual para los tres formatos."""

    titulo: str
    columnas: list[str]
    filas: list[list]
    encabezado: list[str] = field(default_factory=list)  # líneas bajo el título (activo, rango...)
    pie: list[str] = field(default_factory=list)  # subtotales, firma...
    ruta_logo: Optional[str] = None


def generar_csv(doc: Documento) -> bytes:
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(doc.columnas)
    for inicio in range(0, len(doc.filas), _BLOQUE_CSV):
        escritor.writerows(_texto(f) for f in doc.filas[inicio:inicio + _BLOQUE_CSV])
    return salida.getvalue().encode("utf-8")


def generar_excel(doc: Documento) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    libro = Workbook()
    hoja = libro.active
    hoja.title = doc.titulo[:31]
    for linea in [doc.titulo, *doc.encabezado]:
        hoja.append([linea])
    hoja.append([])
    hoja.append(doc.columnas)
    fila_encabezado = hoja.max_row
    for celda in hoja[fila_encabezado]:
        celda.font = Font(bold=True)
    for fila in doc.filas:
        hoja.append(_texto(fila))
    hoja.freeze_panes = hoja.cell(row=fila_encabezado + 1, column=1)
    for indice, ancho in enumerate(_anchos(doc), start=1):
        hoja.column_dimensions[hoja.cell(row=fila_encabezado, column=indice).column_letter].width = ancho
    if doc.pie:
        hoja.append([])
        for linea in doc.pie:
            hoja.append([linea])
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def generar_pdf(doc: Documento, generado: datetime) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A3, A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    salida = io.BytesIO()
    hoja = landscape(A4 if len(doc.columnas) <= _COLUMNAS_A4 else A3)
    margen = 12 * mm
    plantilla = SimpleDocTemplate(
        salida, pagesize=hoja, leftMargin=margen, rightMargin=margen, topMargin=margen, bottomMargin=margen,
        title=doc.titulo, author=_AUTOR, creator=_AUTOR, subject=doc.titulo, lang="es-CO",
    )
    estilos = getSampleStyleSheet()
    tamano = 8 if len(doc.columnas) <= 8 else 7
    celda = ParagraphStyle("celda", parent=estilos["Normal"], fontSize=tamano, leading=tamano + 2, splitLongWords=1)
    cabecera = ParagraphStyle("cabecera", parent=celda, fontName="Helvetica-Bold", textColor=colors.white)
    estilo_tabla = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]
    )
    # El ancho útil se reparte según el contenido de cada columna: nada se sale de la hoja.
    util = hoja[0] - 2 * margen
    pesos = _anchos(doc)
    anchos = [util * p / sum(pesos) for p in pesos] if pesos else None

    def _p(texto: object, estilo) -> Paragraph:
        return Paragraph(escape("" if texto is None else str(texto)).replace("\n", "<br/>"), estilo)

    elementos = []
    if doc.ruta_logo:
        elementos.append(Image(doc.ruta_logo, width=80, height=40, kind="proportional"))
    elementos.append(Paragraph(escape(doc.titulo), estilos["Title"]))
    elementos.append(_p(f"Fecha de generación: {fecha_hora(generado)}", estilos["Normal"]))
    for linea in doc.encabezado:
        elementos.append(_p(linea, estilos["Normal"]))
    elementos.append(Spacer(1, 10))

    encabezados = [_p(c, cabecera) for c in doc.columnas]
    paginas = [doc.filas[i:i + FILAS_POR_PAGINA_PDF] for i in range(0, len(doc.filas), FILAS_POR_PAGINA_PDF)] or [[]]
    for numero, pagina in enumerate(paginas):
        if numero:
            elementos.append(PageBreak())
        tabla = Table([encabezados, *([_p(v, celda) for v in _texto(f)] for f in pagina)], colWidths=anchos, repeatRows=1)
        tabla.setStyle(estilo_tabla)
        elementos.append(tabla)

    if doc.pie:
        elementos.append(Spacer(1, 10))
        for linea in doc.pie:
            elementos.append(_p(linea, estilos["Normal"]))

    def _ver_titulo(lienzo, _plantilla) -> None:
        lienzo.setViewerPreference("DisplayDocTitle", "true")  # el lector muestra el título, no el nombre del archivo

    plantilla.build(elementos, onFirstPage=_ver_titulo, onLaterPages=_ver_titulo)
    return salida.getvalue()


def _anchos(doc: Documento) -> list[float]:
    """Peso de cada columna: su palabra más larga nunca se parte y el texto típico de sus filas cabe en pocas líneas.

    El texto típico es el percentil 90 de las primeras 200 filas (una celda enorme no se lleva la hoja), con tope 40.
    """
    muestras = doc.filas[:200]
    pesos = []
    for i, columna in enumerate(doc.columnas):
        textos = [str(f[i]) for f in muestras if i < len(f) and f[i] is not None]
        largos = sorted(len(t) for t in textos)
        tipico = largos[int(len(largos) * 0.9)] if largos else 0
        palabra = max((len(p) for t in textos for p in t.split() if len(p) <= 24), default=0)
        palabra_titulo = max((len(p) for p in columna.split()), default=0) * 1.2  # el encabezado va en negrita
        pesos.append(max(7, palabra + 1, palabra_titulo + 1, min(40, max(len(columna), tipico) * 0.7)))
    return pesos


def moneda(valor: object) -> str:
    """«$ 322.000» o «$ 1.234,50» (pesos colombianos); vacío si no hay valor."""
    if valor is None or valor == "":
        return ""
    try:
        numero = Decimal(str(valor))
    except InvalidOperation:
        return str(valor)
    negativo = numero < 0
    entero, _, decimales = f"{abs(numero):.2f}".partition(".")
    texto = f"{int(entero):,}".replace(",", ".") + ("" if decimales == "00" else f",{decimales}")
    return f"{'−' if negativo else ''}$ {texto}"


def numero(valor: object, decimales: int = 2) -> str:
    """Cantidad con separadores de Colombia, sin ceros sobrantes: «1.250,5»."""
    if valor is None or valor == "":
        return ""
    try:
        n = Decimal(str(valor))
    except InvalidOperation:
        return str(valor)
    entero, _, frac = f"{abs(n):.{decimales}f}".partition(".")
    frac = frac.rstrip("0")
    return f"{'-' if n < 0 else ''}{int(entero):,}".replace(",", ".") + (f",{frac}" if frac else "")


def fecha(valor: object) -> str:
    """Día en formato dd/mm/aaaa; acepta ``date``, ``datetime`` o texto ISO."""
    if valor is None or valor == "":
        return ""
    if isinstance(valor, datetime):
        return fecha_hora(valor)
    if isinstance(valor, date):
        return f"{valor:%d/%m/%Y}"
    try:
        return fecha(datetime.fromisoformat(str(valor))) if "T" in str(valor) else f"{date.fromisoformat(str(valor)[:10]):%d/%m/%Y}"
    except ValueError:
        return str(valor)


def fecha_hora(valor: datetime) -> str:
    """Instante en la hora del usuario con su zona: «10/11/2026 22:15 (UTC-05:00)»."""
    from src.shared.fechas import en_zona_usuario, etiqueta_zona

    local = en_zona_usuario(valor) if valor.tzinfo else valor
    return f"{local:%d/%m/%Y %H:%M} ({etiqueta_zona(local)})" if valor.tzinfo else f"{local:%d/%m/%Y %H:%M}"


def legible(valor: object, etiquetas: Optional[dict] = None) -> str:
    """Valor de catálogo en palabras: primero la etiqueta conocida; si no hay, «VALOR_CRUDO» → «Valor crudo»."""
    if valor is None or valor == "":
        return ""
    texto = str(valor)
    if etiquetas and texto in etiquetas:
        return etiquetas[texto]
    return texto.replace("_", " ").capitalize() if texto.isupper() else texto


def _texto(fila: Iterable) -> list[str]:
    return ["" if v is None else str(v) for v in fila]
