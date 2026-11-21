# | Fecha      | Nombre   | Que se hizo                                                           |
# |------------|----------|-----------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: PDF carta (ReportLab) y Excel tipado (openpyxl) de reportes |
# | 2026-11-19 | Arekkazu | M08 RF-104 M8-12/M8-13: diseño de las plantillas V1.1, columnas sin partir palabras y fechas reales |
# | 2026-11-20 | Arekkazu | A11Y-M08 TC-DIS-288 RF-104: PDF etiquetado, con idioma, título visible en el lector y fuentes incrustadas |
"""Render de un :class:`ContenidoReporte` a PDF o Excel (RF-104 Fase 3, CA-4, CA-11).

PDF (ReportLab): tamaño carta (horizontal si la tabla es ancha), letra de 10 puntos o más y la estructura de las
plantillas V1.1 (ver ``_pdf``); el sello del sistema y «Página N de M» en el pie de cada página y la firma del
Contador en la valoración NIC 41. Va etiquetado (TC-DIS-288): título H1, secciones H2, subtítulos H3, textos P,
logo Figure y cada tabla de datos TR/TH/TD; marca, línea de firma, pie y fondos de tablas son decoración. Declara
idioma (es-CO), el lector muestra el título y no el nombre del archivo, y las fuentes van incrustadas (Vera).

Excel (openpyxl): hoja «Resumen Ejecutivo» (Campo | Valor | Tipo / Unidad | Observación: encabezado, parámetros e
indicadores; luego totales, tablas finales y advertencias) y «Datos Detallados»; la ficha del animal y el ejecutivo llevan una hoja por sección. Montos y números como NUMBER con 2
decimales, fechas como DATE, sin celdas combinadas y la primera fila de cada hoja con los encabezados.
"""
from __future__ import annotations

import io
import re
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
from src.shared.fechas import en_zona_usuario, etiqueta_zona
from src.shared.pdf_etiquetado import ArbolEtiquetas, artefacto, etiquetado
from src.shared.pdfa import FUENTE, FUENTE_NEGRITA, registrar_fuentes

SELLO = "Generado por Sistema de Gestión Pecuaria Multiespecie — Universidad Surcolombiana"
_TIPOS = {PDF: "application/pdf", EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
_EXTENSIONES = {PDF: "pdf", EXCEL: "xlsx"}
_COLUMNAS_VERTICAL = 6
_FUENTE = 10  # CA-11: mínimo 10 puntos
_FUENTE_TABLA = ("FONTNAME", (0, 0), (-1, -1), FUENTE)  # la tabla declara su fuente aunque el texto vaya en párrafos


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
# Estructura de las plantillas V1.1: marca, título, línea de autor, datos del titular en una fila, recuadro gris con
# datos de la exportación, «Parámetros de selección», avisos, «Análisis detallado de registros», tarjetas de
# «Resumen ejecutivo de indicadores», tablas finales, firma y pie con el sello y «Página N de M» en cada hoja.

_VERDE, _TINTA, _GRIS = "#2e8634", "#1f2a22", "#5f6d62"
_BORDE, _FONDO, _CABECERA = "#d9dfda", "#f4f6f4", "#eef2ee"
_AVISO_FONDO, _AVISO_BORDE = "#fff8e1", "#d9a400"
_EN_FILA = ("Razón social", "NIT", "Finca", "Rango de fechas", "Período contable", "Período base",
            "Período de comparación", "Fecha de corte")
_RENOMBRE_FILA = {"Rango de fechas": "Período"}
_PADDING = 3
_HOLGURA = 3  # redondeo de ReportLab: sin esto una cifra del ancho exacto baja de línea


def _palabras(texto: str) -> list[str]:
    return texto.split(" ")  # el espacio duro de «$ 1.000» no corta: va con su número


def _texto_pdf(valor: Any, tipo: str) -> str:
    return texto_celda(valor, tipo).replace("$ ", "$ ")


_NUMERICOS = (ENTERO, NUMERO, MONEDA, PORCENTAJE, FECHA, FECHA_HORA)
_PALABRA_TEXTO_MAXIMA = 70  # un código largo (QA-M06-G52-SANITARIO, una huella) sí puede bajar de línea


def _anchos_pdf(t: Tabla, ancho_util: float) -> list[float]:
    """Cada columna mide al menos la palabra más larga de su título y, si es de números o fechas, la cifra más larga
    (así no se parten, M8-12); lo que sobra se reparte según lo largo del contenido. Solo si ni así cabe, se encoge
    todo en proporción."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    registrar_fuentes()

    minimos, ajustados, extras, faltantes = [], [], [], []
    for c in t.columnas:
        textos = [_texto_pdf(f.get(c.clave), c.tipo) for f in t.filas[:200]]
        titulo = max((stringWidth(p, FUENTE_NEGRITA, _FUENTE) for p in _palabras(c.titulo)), default=0)
        palabra = max((stringWidth(p, FUENTE, _FUENTE) for x in textos for p in _palabras(x)), default=0)
        numerica = c.tipo in _NUMERICOS
        minimo = max(titulo, palabra if numerica else min(palabra, max(titulo, _PALABRA_TEXTO_MAXIMA))) + 2 * _PADDING \
            + _HOLGURA
        largos = sorted(stringWidth(x, FUENTE, _FUENTE) for x in textos)
        tipico = largos[len(largos) // 2] if largos else 0
        minimos.append(minimo)
        # Si la tabla no cabe, una columna de texto se conforma con la palabra de su título.
        ajustados.append(minimo if numerica else max(titulo, 28) + 2 * _PADDING + _HOLGURA)
        extras.append(max(min(tipico, 220) + 2 * _PADDING - minimo, 0))
        faltantes.append(max(min(palabra, 150) + 2 * _PADDING + _HOLGURA - ajustados[-1], 0))
    if sum(minimos) > ancho_util:
        # Lo que sobre va primero a que quepa la palabra más larga del contenido de cada columna.
        minimos, extras = ajustados, faltantes
    sobra = ancho_util - sum(minimos)
    if sobra <= 0:
        return [ancho_util * m / sum(minimos) for m in minimos]
    total_extra = sum(extras)
    if total_extra == 0:
        return [m + sobra / len(minimos) for m in minimos]
    reparto = min(sobra, total_extra)
    anchos = [m + reparto * e / total_extra for m, e in zip(minimos, extras)]
    resto = (sobra - reparto) / len(anchos)
    return [a + resto for a in anchos]


def _lienzo(sello: str, arbol: ArbolEtiquetas):
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas

    class _Lienzo(canvas.Canvas):
        """Dos pasadas: primero se dibujan las páginas y al guardar se conoce el total («Página N de M»)."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._paginas: list[dict] = []
            self.setViewerPreference("DisplayDocTitle", "true")  # el lector muestra el título, no el nombre del archivo

        def showPage(self):
            self._paginas.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._paginas)
            for numero, estado in enumerate(self._paginas, start=1):
                self.__dict__.update(estado)
                ancho, _ = self._pagesize
                self._code.append("/Artifact BMC")  # el pie se repite en cada página: el lector no lo lee
                self.setStrokeColor(colors.HexColor(_BORDE))
                self.line(36, 36, ancho - 36, 36)
                self.setFillColor(colors.HexColor(_GRIS))
                self.setFont(FUENTE, _FUENTE)
                self.drawString(36, 22, sello)
                self.drawRightString(ancho - 36, 22, f"Página {numero} de {total}")
                self._code.append("EMC")
                super().showPage()
            arbol.escribir(self)  # las páginas reales existen solo después del replay
            super().save()

    return _Lienzo


def _marca():
    """El ícono de SIGAB (el mismo del favicon del front) y el nombre del sistema."""
    from reportlab.lib import colors
    from reportlab.platypus import Flowable

    class _Marca(artefacto(Flowable)):
        def wrap(self, ancho, alto):
            return ancho, 26

        def draw(self):
            c, verde = self.canv, colors.HexColor(_VERDE)
            escala = 22 / 32
            c.saveState()
            c.translate(0, 24)
            c.scale(escala, -escala)  # coordenadas del SVG (y hacia abajo)
            c.setFillColor(verde)
            c.roundRect(0, 0, 32, 32, 7, stroke=0, fill=1)
            c.setStrokeColor(colors.white)
            c.setLineCap(1)
            c.setLineWidth(2.2)
            camino = c.beginPath()
            camino.moveTo(8, 22)
            camino.curveTo(8, 16, 12, 11, 16, 11)
            camino.curveTo(20, 11, 24, 16, 24, 22)
            c.drawPath(camino, stroke=1, fill=0)
            c.setFillColor(colors.white)
            c.circle(12, 17, 2.2, stroke=0, fill=1)
            c.circle(20, 17, 2.2, stroke=0, fill=1)
            c.setLineWidth(1.6)
            boca = c.beginPath()
            boca.moveTo(13, 21)
            boca.curveTo(13, 19.5, 14.3, 18.5, 16, 18.5)
            boca.curveTo(17.7, 18.5, 19, 19.5, 19, 21)
            c.drawPath(boca, stroke=1, fill=0)
            c.setStrokeColor(colors.HexColor("#a8d8a8"))
            c.line(10, 11, 8, 8)
            c.line(22, 11, 24, 8)
            c.restoreState()
            c.setFont(FUENTE_NEGRITA, 12)
            c.setFillColor(colors.HexColor(_TINTA))
            c.drawString(30, 8, "SIGAB")
            c.setFillColor(verde)
            c.drawString(30 + c.stringWidth("SIGAB ", FUENTE_NEGRITA, 12), 8, "Gestión Pecuaria Multiespecie")

    return _Marca()


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
    registrar_fuentes()  # PDF/UA: toda fuente va incrustada (las 14 estándar, como Helvetica, no lo están)
    normal = ParagraphStyle("normal", parent=estilos["Normal"], fontName=FUENTE, fontSize=_FUENTE, leading=_FUENTE + 3,
                            textColor=colors.HexColor(_TINTA))
    gris = ParagraphStyle("gris", parent=normal, textColor=colors.HexColor(_GRIS))
    cabecera = ParagraphStyle("cabecera", parent=normal, fontName=FUENTE_NEGRITA, textColor=colors.HexColor(_GRIS))
    titulo = ParagraphStyle("titulo", parent=normal, fontName=FUENTE_NEGRITA, fontSize=17, leading=21, spaceBefore=8,
                            spaceAfter=4)
    seccion = ParagraphStyle("seccion", parent=normal, fontName=FUENTE_NEGRITA, fontSize=12, leading=15,
                             spaceBefore=12, spaceAfter=6, keepWithNext=1)
    subtitulo = ParagraphStyle("subtitulo", parent=normal, fontName=FUENTE_NEGRITA, spaceBefore=6, spaceAfter=4,
                               keepWithNext=1)
    derecha = ParagraphStyle("derecha", parent=normal, alignment=2)
    cabecera_derecha = ParagraphStyle("cabecera_derecha", parent=cabecera, alignment=2)
    cifra = ParagraphStyle("cifra", parent=normal, fontName=FUENTE_NEGRITA, fontSize=14, leading=17,
                           textColor=colors.HexColor(_VERDE))
    ancho_util = pagina[0] - 72
    arbol = ArbolEtiquetas()
    _Parrafo = etiquetado(Paragraph)
    roles = {titulo.name: "H1", seccion.name: "H2", subtitulo.name: "H3"}

    def parrafo(texto: str, estilo=normal, etiquetar: bool = True, marcado: bool = False) -> Paragraph:
        """Párrafo con su etiqueta (H1/H2/H3 según el estilo, P el resto); las celdas de datos van sin etiqueta."""
        if not etiquetar:
            return Paragraph(escape(texto), estilo)
        p = _Parrafo(texto if marcado else escape(texto), estilo)
        p._etiqueta = arbol.nuevo(roles.get(estilo.name, "P"), arbol.documento)
        return p

    def caja(contenido_caja, fondo: str, borde: str) -> Table:
        recuadro = Table([[contenido_caja]], colWidths=[ancho_util], cornerRadii=[5, 5, 5, 5],
                         renderCB=arbol.al_dibujar_maqueta)
        recuadro.setStyle(TableStyle([_FUENTE_TABLA, ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fondo)),
                                      ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(borde)),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                      ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        return recuadro

    def tabla(t: Tabla, con_titulo: bool = True) -> list:
        elementos: list = [parrafo(t.titulo, subtitulo)] if con_titulo else []
        if not t.filas:
            elementos.append(parrafo("Sin registros para los filtros elegidos.", gris))
        else:
            montos = [c.tipo in (ENTERO, NUMERO, MONEDA, PORCENTAJE) for c in t.columnas]
            datos = [[parrafo(c.titulo, cabecera_derecha if m else cabecera, etiquetar=False)
                      for c, m in zip(t.columnas, montos)]]
            datos += [[Paragraph(escape(_texto_pdf(f.get(c.clave), c.tipo)),
                                 derecha if m and not isinstance(f.get(c.clave), str) else normal)
                       for c, m in zip(t.columnas, montos)] for f in t.filas]
            grilla = Table(datos, colWidths=_anchos_pdf(t, ancho_util), repeatRows=1, renderCB=arbol.al_dibujar_tabla)
            arbol.tabla(datos)
            grilla.setStyle(TableStyle([_FUENTE_TABLA,
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_CABECERA)),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor(_BORDE)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), _PADDING), ("RIGHTPADDING", (0, 0), (-1, -1), _PADDING),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elementos.append(grilla)
        if t.nota:
            elementos.append(parrafo(t.nota, gris))
        elementos.append(Spacer(1, 8))
        return elementos

    def tarjetas() -> list:
        por_fila = 4 if len(contenido.indicadores) % 4 == 0 else 3
        ancho = (ancho_util - 10 * (por_fila - 1)) / por_fila
        celdas = []
        for ind in contenido.indicadores:
            tarjeta = Table([[parrafo(ind.etiqueta.upper(), gris)], [parrafo(texto_celda(ind.valor, ind.tipo), cifra)]],
                            colWidths=[ancho - 2], cornerRadii=[6, 6, 6, 6], renderCB=arbol.al_dibujar_maqueta)
            tarjeta.setStyle(TableStyle([_FUENTE_TABLA, ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(_BORDE)),
                                         ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, 0), 9),
                                         ("BOTTOMPADDING", (0, -1), (-1, -1), 10)]))
            celdas.append(tarjeta)
        filas = [celdas[i:i + por_fila] for i in range(0, len(celdas), por_fila)]
        filas[-1] += [""] * (por_fila - len(filas[-1]))
        rejilla = Table(filas, colWidths=[ancho + 10] * por_fila, hAlign="LEFT", renderCB=arbol.al_dibujar_maqueta)
        rejilla.setStyle(TableStyle([_FUENTE_TABLA,
                                     ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                     ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return [parrafo("Resumen ejecutivo de indicadores", seccion), rejilla, Spacer(1, 8)]

    datos = dict(contenido.encabezado)
    marca: Any = _marca()
    if ruta_logo:
        try:
            logo = etiquetado(Image)(ruta_logo, width=1.2 * inch, height=0.5 * inch, kind="proportional")
            marca = Table([[marca, logo]], colWidths=[ancho_util - 1.3 * inch, 1.3 * inch],
                          renderCB=arbol.al_dibujar_maqueta)
            logo._etiqueta = arbol.nuevo("Figure", arbol.documento, alt="Logo de la finca")
            marca.setStyle(TableStyle([_FUENTE_TABLA,
                                       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                                       ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        except Exception:
            marca = _marca()  # un logo dañado no impide el reporte
    historia: list = [marca, parrafo(contenido.titulo, titulo)]
    meta = [f"Fecha de generación: {datos['Fecha de generación']}"] if "Fecha de generación" in datos else []
    if contenido.generado_por:
        meta.append(f"Generado por: {contenido.generado_por}")
    meta.append("Estado: Generado")
    historia.append(parrafo(" · ".join(meta), gris))
    en_fila = [(k, v) for k, v in contenido.encabezado if k in _EN_FILA]
    aparte = [(k, v) for k, v in contenido.encabezado if k not in _EN_FILA and k != "Fecha de generación"]
    historia += [Spacer(1, 6), parrafo("&nbsp;&nbsp;&nbsp;&nbsp;".join(
        f'<font color="{_GRIS}">{escape(_RENOMBRE_FILA.get(k, k))}</font> {escape(v)}' for k, v in en_fila), marcado=True)]
    if aparte:
        celdas = [parrafo(f'<font color="{_GRIS}">{escape(k)}</font><br/>{escape(v)}', marcado=True) for k, v in aparte]
        recuadro = Table([celdas], colWidths=[(ancho_util - 20) / len(celdas)] * len(celdas),
                         renderCB=arbol.al_dibujar_maqueta)
        recuadro.setStyle(TableStyle([_FUENTE_TABLA,
                                      ("LEFTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        historia += [Spacer(1, 8), caja(recuadro, _FONDO, _BORDE)]
    for texto in contenido.aclaraciones:
        historia += [Spacer(1, 8), caja(parrafo(texto, gris), _FONDO, _BORDE)]
    if contenido.parametros:
        historia.append(parrafo("Parámetros de selección", seccion))
        lista = Table([[parrafo(f'<font color="{_VERDE}">•</font>&nbsp;&nbsp;<font color="{_GRIS}">'
                                f'{escape(k)}:</font> <b>{escape(v)}</b>', marcado=True)] for k, v in contenido.parametros],
                      colWidths=[ancho_util], renderCB=arbol.al_dibujar_maqueta)
        lista.setStyle(TableStyle([_FUENTE_TABLA, ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor(_BORDE)),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 3),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        historia.append(lista)
    for aviso in contenido.advertencias:
        historia += [Spacer(1, 8), caja(parrafo(f"<b>Advertencia:</b> {escape(aviso)}", marcado=True),
                                        _AVISO_FONDO, _AVISO_BORDE)]
    if contenido.detalle:
        historia.append(parrafo("Análisis detallado de registros", seccion))
        historia += tabla(contenido.detalle, con_titulo=False)
    for s in contenido.secciones:
        historia.append(parrafo(s.titulo, seccion))
        historia += [parrafo(texto) for texto in s.textos]
        for t in s.tablas:
            historia += tabla(t, con_titulo=len(s.tablas) > 1)
    if contenido.indicadores:
        historia += tarjetas()
    for t in contenido.resumen + [t for t in contenido.finales if t not in contenido.resumen]:
        historia += tabla(t)
    if contenido.firma:
        historia.append(KeepTogether([
            Spacer(1, 26), artefacto(HRFlowable)(width=2.4 * inch, thickness=0.8, color=colors.HexColor(_TINTA), hAlign="LEFT"),
            parrafo("Firma electrónica del Contador", gris), parrafo(contenido.firma)]))

    salida = io.BytesIO()
    documento = SimpleDocTemplate(salida, pagesize=pagina, leftMargin=36, rightMargin=36, topMargin=30,
                                  bottomMargin=54, title=contenido.titulo, author="SIGAB", lang="es-CO",
                                  initialFontName=FUENTE)
    documento.build(historia, canvasmaker=partial(_lienzo(SELLO, arbol)))
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


_UNIDAD = {MONEDA: "COP", PORCENTAJE: "%", ENTERO: "Número", NUMERO: "Número", FECHA: "Fecha",
           FECHA_HORA: "Fecha y hora"}
_RANGO = re.compile(r"^(\d{2}/\d{2}/\d{4}) a (\d{2}/\d{2}/\d{4})")


def _filas_resumen(contenido: ContenidoReporte) -> list[list[Any]]:
    """Hoja «Resumen Ejecutivo» como la plantilla: Campo | Valor | Tipo / Unidad | Observación. La fecha de
    generación y los extremos de cada período van como fechas de Excel, no como texto (CA-4, M8-13)."""
    filas: list[list[Any]] = [["Campo", "Valor", "Tipo / Unidad", "Observación"],
                              ["Reporte", contenido.titulo, "Texto", ""]]
    if contenido.generado is not None:
        local = en_zona_usuario(contenido.generado)
        filas.append(["Fecha de generación", local.replace(tzinfo=None), "Fecha y hora",
                      f"Hora local ({etiqueta_zona(local)})"])
    if contenido.generado_por:
        filas.append(["Generado por", contenido.generado_por, "Texto", "Usuario que pidió el reporte"])
    filas.append(["Estado del reporte", "Generado", "Texto", ""])
    for campo, valor in contenido.encabezado:
        if campo == "Fecha de generación" and contenido.generado is not None:
            continue
        rango = _RANGO.match(valor)
        if rango:
            inicio, fin = (datetime.strptime(x, "%d/%m/%Y").date() for x in rango.groups())
            filas += [[f"{campo} (inicio)", inicio, "Fecha", valor], [f"{campo} (fin)", fin, "Fecha", ""]]
        else:
            filas.append([campo, valor, "Texto", ""])
    filas += [[campo, valor, "Texto", "Parámetro de selección"] for campo, valor in contenido.parametros]
    filas += [[i.etiqueta, _valor_excel(i.valor, i.tipo), _UNIDAD.get(i.tipo, "Texto") if not isinstance(i.valor, str)
               else "Texto", "Indicador"] for i in contenido.indicadores]
    return filas


def _excel(contenido: ContenidoReporte) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    libro = Workbook()
    resumen = libro.worksheets[0]
    resumen.title = "Resumen Ejecutivo"
    usados = {resumen.title}
    for fila_campo in _filas_resumen(contenido):
        resumen.append(fila_campo)
        _, valor, unidad, _ = fila_campo
        formato = {"Fecha": "yyyy-mm-dd", "Fecha y hora": "yyyy-mm-dd hh:mm", "COP": "#,##0.00", "%": "0.00",
                   "Número": "#,##0.##"}.get(unidad)
        if formato and not isinstance(valor, str):
            resumen.cell(row=resumen.max_row, column=2).number_format = formato
    for celda in resumen[1]:
        celda.font = Font(bold=True)
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
