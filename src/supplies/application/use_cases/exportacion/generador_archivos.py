# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77/RF-81: CSV, Excel y PDF             |
# | 2026-11-10 | Arekkazu         | CP088/CP111/TC-DIS-204 RF-77/80/81: PDF sin recorte, celdas con salto de línea, idioma y título; moneda legible |
# | 2026-11-11 | Arekkazu         | TC-DIS-204 RF-77: PDF etiquetado para lector de pantalla (encabezado, párrafos y tabla con TH/TD) |
# | 2026-11-12 | Arekkazu | TC-DIS-259/264 RF-92/93: Excel con encabezados en la fila 1 y título y totales en otra hoja |
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G70 RF-92: PDF/A-1b opcional para los documentos que se conservan |
# | 2026-11-20 | Arekkazu         | A11Y-M08 TC-DIS-288 RF-104: el árbol de etiquetas del PDF pasa a src/shared (lo usan los reportes) |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Generación de archivos de exportación de M05 (RF-77 y RF-81).

- CSV en bloques de 1.000 filas (RF-77 "chunking" para > 5.000 registros): el
  archivo se arma completo antes de entregarse, nunca parcial (E6c).
- PDF con encabezado (logo si existe, título y fecha de generación) y 25
  registros por página (RF-77 "paginación automática"). Las columnas se reparten
  el ancho útil de la hoja según su contenido y cada celda hace salto de línea:
  ninguna columna queda fuera de la página (CP088, CP111). Con más de 10 columnas
  la hoja pasa a A3 horizontal para que el texto siga legible. El archivo declara
  idioma (es-CO), título, autor y muestra el título en la ventana del lector.
  Va etiquetado (TC-DIS-204): título como H1, líneas como P, logo como Figure con
  texto alternativo y cada tabla con TR/TH/TD en orden de lectura; fondos y
  líneas de la tabla y el encabezado repetido en otra hoja se marcan como
  decoración (Artifact) para que el lector no los lea.
- Excel con la tabla en la hoja «Datos» (encabezados en negrita en la fila 1, fija
  al desplazarse, ancho de columna según el contenido) y el título, las líneas de
  encabezado y el pie en la hoja «Información».
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape
from typing import Iterable, Optional

from src.shared.celdas_seguras import proteger_libro, texto_seguro_csv
from src.shared.pdf_etiquetado import ArbolEtiquetas, etiquetado

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
    """Genera el documento en CSV."""
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(doc.columnas)
    for inicio in range(0, len(doc.filas), _BLOQUE_CSV):
        # Un texto libre (p. ej. la observación) se exporta como texto, nunca como fórmula.
        escritor.writerows([texto_seguro_csv(v) for v in _texto(f)] for f in doc.filas[inicio:inicio + _BLOQUE_CSV])
    return salida.getvalue().encode("utf-8")


def generar_excel(doc: Documento) -> bytes:
    """Genera el documento en Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    libro = Workbook()
    # TC-DIS-264/259: la primera hoja es la tabla, con los encabezados en la fila 1 (un lector de pantalla y
    # un filtro de Excel la leen como tabla); el título, el alcance y los totales van en «Información». El
    # nombre de la hoja no sale del título: Excel lo cortaba a 31 caracteres.
    hoja = libro.active
    hoja.title = "Datos"
    hoja.append(doc.columnas)
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for fila in doc.filas:
        hoja.append(_texto(fila))
    hoja.freeze_panes = "A2"
    for indice, ancho in enumerate(_anchos(doc), start=1):
        hoja.column_dimensions[hoja.cell(row=1, column=indice).column_letter].width = ancho
    info = libro.create_sheet("Información")
    info.append([doc.titulo])
    info["A1"].font = Font(bold=True)
    for linea in [*doc.encabezado, *doc.pie]:
        info.append([linea])
    info.column_dimensions["A"].width = min(100, max(len(str(x)) for x in [doc.titulo, *doc.encabezado, *doc.pie]) + 2)
    proteger_libro(libro)  # el texto exportado se guarda como texto, nunca como fórmula
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def generar_pdf(doc: Documento, generado: datetime, pdfa: bool = False) -> bytes:
    """``pdfa``: conformidad PDF/A-1b (fuentes incrustadas, perfil de color y metadatos XMP), para documentos
    que se conservan a largo plazo, como el informe de revelaciones NIC 41 (RNF-92-02)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A3, A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    _Parrafo, _Imagen = etiquetado(Paragraph), etiquetado(Image)
    fuente, negrita = "Helvetica", "Helvetica-Bold"
    if pdfa:
        from src.shared.pdfa import FUENTE, FUENTE_NEGRITA, registrar_fuentes

        registrar_fuentes()
        fuente, negrita = FUENTE, FUENTE_NEGRITA

    salida = io.BytesIO()
    hoja = landscape(A4 if len(doc.columnas) <= _COLUMNAS_A4 else A3)
    margen = 12 * mm
    plantilla = SimpleDocTemplate(
        salida, pagesize=hoja, leftMargin=margen, rightMargin=margen, topMargin=margen, bottomMargin=margen,
        title=doc.titulo, author=_AUTOR, creator=_AUTOR, subject=doc.titulo, lang="es-CO",
        initialFontName=fuente,
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], fontName=negrita)
    normal = ParagraphStyle("normal", parent=estilos["Normal"], fontName=fuente)
    tamano = 8 if len(doc.columnas) <= 8 else 7
    celda = ParagraphStyle("celda", parent=normal, fontSize=tamano, leading=tamano + 2, splitLongWords=1)
    cabecera = ParagraphStyle("cabecera", parent=celda, fontName=negrita, textColor=colors.white)
    estilo_tabla = TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), fuente),  # la tabla fija su propia fuente aunque el texto vaya en párrafos
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

    etiquetas = ArbolEtiquetas()
    raiz = etiquetas.documento

    def _p(texto: object, estilo, rol: Optional[str] = None) -> Paragraph:
        parrafo = _Parrafo(escape("" if texto is None else str(texto)).replace("\n", "<br/>"), estilo)
        if rol:
            parrafo._etiqueta = etiquetas.nuevo(rol, raiz)
        return parrafo

    elementos = []
    if doc.ruta_logo:
        logo = _Imagen(doc.ruta_logo, width=80, height=40, kind="proportional")
        logo._etiqueta = etiquetas.nuevo("Figure", raiz, alt="Logo de la finca")
        elementos.append(logo)
    elementos.append(_p(doc.titulo, titulo, "H1"))
    elementos.append(_p(f"Fecha de generación: {fecha_hora(generado)}", normal, "P"))
    for linea in doc.encabezado:
        elementos.append(_p(linea, normal, "P"))
    elementos.append(Spacer(1, 10))

    paginas = [doc.filas[i:i + FILAS_POR_PAGINA_PDF] for i in range(0, len(doc.filas), FILAS_POR_PAGINA_PDF)] or [[]]
    for numero, pagina in enumerate(paginas):
        if numero:
            elementos.append(PageBreak())
        filas = [[_p(c, cabecera) for c in doc.columnas], *([_p(v, celda) for v in _texto(f)] for f in pagina)]
        tabla = Table(filas, colWidths=anchos, repeatRows=1, renderCB=etiquetas.al_dibujar_tabla)
        tabla.setStyle(estilo_tabla)
        etiquetas.tabla(filas)
        elementos.append(tabla)

    if doc.pie:
        elementos.append(Spacer(1, 10))
        for linea in doc.pie:
            elementos.append(_p(linea, normal, "P"))

    def _ver_titulo(lienzo, _plantilla) -> None:
        lienzo.setViewerPreference("DisplayDocTitle", "true")  # el lector muestra el título, no el nombre del archivo

    plantilla._doSave = 0  # el árbol de etiquetas se escribe cuando ya existen todas las páginas
    plantilla.build(elementos, onFirstPage=_ver_titulo, onLaterPages=_ver_titulo)
    etiquetas.escribir(plantilla.canv)
    if pdfa:
        from src.shared.pdfa import aplicar_pdfa1b

        aplicar_pdfa1b(plantilla.canv)
    plantilla.canv.save()
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
