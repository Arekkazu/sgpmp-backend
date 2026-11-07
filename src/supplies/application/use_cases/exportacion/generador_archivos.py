# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77/RF-81: CSV, Excel y PDF             |
"""Generación de archivos de exportación de M05 (RF-77 y RF-81).

- CSV en bloques de 1.000 filas (RF-77 "chunking" para > 5.000 registros): el
  archivo se arma completo antes de entregarse, nunca parcial (E6c).
- PDF con encabezado (logo si existe, título y fecha de generación) y 25
  registros por página (RF-77 "paginación automática").
- Excel con encabezado en negrita.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

FILAS_POR_PAGINA_PDF = 25
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
    for celda in hoja[hoja.max_row]:
        celda.font = Font(bold=True)
    for fila in doc.filas:
        hoja.append(_texto(fila))
    if doc.pie:
        hoja.append([])
        for linea in doc.pie:
            hoja.append([linea])
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def generar_pdf(doc: Documento, generado: datetime) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    salida = io.BytesIO()
    plantilla = SimpleDocTemplate(salida, pagesize=landscape(A4), title=doc.titulo)
    estilos = getSampleStyleSheet()
    estilo_tabla = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ]
    )

    elementos = []
    if doc.ruta_logo:
        elementos.append(Image(doc.ruta_logo, width=80, height=40, kind="proportional"))
    elementos.append(Paragraph(doc.titulo, estilos["Title"]))
    elementos.append(Paragraph(f"Fecha de generación: {generado.isoformat(timespec='seconds')}", estilos["Normal"]))
    for linea in doc.encabezado:
        elementos.append(Paragraph(linea, estilos["Normal"]))
    elementos.append(Spacer(1, 10))

    paginas = [doc.filas[i:i + FILAS_POR_PAGINA_PDF] for i in range(0, len(doc.filas), FILAS_POR_PAGINA_PDF)] or [[]]
    for numero, pagina in enumerate(paginas):
        if numero:
            elementos.append(PageBreak())
        tabla = Table([doc.columnas, *(_texto(f) for f in pagina)], repeatRows=1)
        tabla.setStyle(estilo_tabla)
        elementos.append(tabla)

    if doc.pie:
        elementos.append(Spacer(1, 10))
        for linea in doc.pie:
            elementos.append(Paragraph(linea, estilos["Normal"]))
    plantilla.build(elementos)
    return salida.getvalue()


def _texto(fila: Iterable) -> list[str]:
    return ["" if v is None else str(v) for v in fila]
