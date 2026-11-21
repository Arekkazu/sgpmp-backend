# | Fecha      | Nombre   | Que se hizo                                                                 |
# |------------|----------|-----------------------------------------------------------------------------|
# | 2026-11-20 | Arekkazu | A11Y-M08 TC-DIS-288 RF-104: árbol de etiquetas compartido (antes en M05) y decoración marcada como Artifact |
"""PDF etiquetado (estructura y orden de lectura para lector de pantalla) con ReportLab, que no lo escribe solo.

Nació en la exportación de Suministros (TC-DIS-204) y lo usan también los reportes (TC-DIS-288). Uso:

- :class:`ArbolEtiquetas`: ``nuevo(rol, padre)`` crea un elemento (H1, P, Figure…) y ``tabla(filas)`` la tabla
  TR/TH/TD de una ``Table`` cuyas celdas son ``Paragraph``; esa tabla lleva ``renderCB=arbol.al_dibujar_tabla``.
  Una tabla que solo maqueta (recuadros, tarjetas) lleva ``renderCB=arbol.al_dibujar_maqueta``: sus fondos y
  líneas son decoración y su contenido conserva sus propias etiquetas. ``escribir(lienzo)`` va cuando ya existen
  todas las páginas y antes de ``save``.
- :func:`etiquetado`: subclase de un flowable que, con ``_etiqueta``, encierra su dibujo en contenido marcado.
- :func:`artefacto`: subclase de un flowable que se dibuja como decoración (el lector no la lee).
"""
from __future__ import annotations

from typing import Optional


class ArbolEtiquetas:
    """Árbol de etiquetas del PDF (estructura que lee un lector de pantalla); reportlab no lo escribe solo.

    Cada flowable etiquetado abre una secuencia de contenido marcado (``BDC``) con su MCID al dibujarse;
    al final ``escribir`` arma StructTreeRoot, ParentTree y MarkInfo con las páginas ya creadas.
    """

    def __init__(self) -> None:
        self.documento = self.nuevo("Document", None)
        self.por_pagina: dict[int, list[dict]] = {}
        self.celdas: dict[int, dict] = {}  # id del Paragraph de la celda -> su TH/TD

    def nuevo(self, rol: str, padre: Optional[dict], **extra) -> dict:
        elemento = {"rol": rol, "padre": padre, "hijos": [], "marcas": [], "arbol": self, **extra}
        if padre is not None:
            padre["hijos"].append(elemento)
        return elemento

    def abrir(self, lienzo, elemento: dict) -> None:
        pagina = lienzo.getPageNumber()
        marcas = self.por_pagina.setdefault(pagina, [])
        elemento["marcas"].append((pagina, len(marcas)))
        lienzo._code.append(f"/{elemento['rol']} <</MCID {len(marcas)}>> BDC")
        marcas.append(elemento)

    def tabla(self, filas: list[list]) -> None:
        tabla = self.nuevo("Table", self.documento)
        for indice, fila in enumerate(filas):
            tr = self.nuevo("TR", tabla)
            for parrafo in fila:
                self.celdas[id(parrafo)] = self.nuevo("TH", tr, alcance="Column") if indice == 0 else self.nuevo("TD", tr)

    def al_dibujar_tabla(self, tabla, evento: str, *args) -> None:
        codigo = tabla.canv._code
        if evento in ("startBG", "startLines"):
            codigo.append("/Artifact BMC")
        elif evento in ("endBG", "endLines", "endCell"):
            codigo.append("EMC")
        elif evento == "startCell":
            valor = args[2]  # reportlab entrega el Paragraph dentro de una tupla
            elemento = self.celdas.get(id(valor[0] if isinstance(valor, (list, tuple)) and valor else valor))
            if elemento is None or elemento["marcas"]:  # encabezado repetido en la hoja siguiente
                codigo.append("/Artifact BMC")
            else:
                self.abrir(tabla.canv, elemento)

    def al_dibujar_maqueta(self, tabla, evento: str, *args) -> None:
        if evento in ("startBG", "startLines"):
            tabla.canv._code.append("/Artifact BMC")
        elif evento in ("endBG", "endLines"):
            tabla.canv._code.append("EMC")

    def escribir(self, lienzo) -> None:
        from reportlab.pdfbase.pdfdoc import PDFArray, PDFDictionary, PDFName, PDFString

        pdf = lienzo._doc
        paginas = pdf.Pages.pages
        todos, pendientes = [], [self.documento]
        while pendientes:
            elemento = pendientes.pop()
            todos.append(elemento)
            pendientes.extend(elemento["hijos"])
        objetos = {id(e): PDFDictionary({}) for e in todos}
        refs = {id(e): pdf.Reference(objetos[id(e)]) for e in todos}
        raiz = PDFDictionary({"Type": PDFName("StructTreeRoot")})
        ref_raiz = pdf.Reference(raiz)
        for e in todos:
            hijos = [refs[id(h)] for h in e["hijos"]] + [
                PDFDictionary({"Type": PDFName("MCR"), "Pg": pdf.Reference(paginas[p - 1]), "MCID": m})
                for p, m in e["marcas"]
            ]
            d = objetos[id(e)].dict
            d.update(Type=PDFName("StructElem"), S=PDFName(e["rol"]), K=PDFArray(hijos),
                     P=refs[id(e["padre"])] if e["padre"] else ref_raiz)
            if "alcance" in e:
                d["A"] = PDFDictionary({"O": PDFName("Table"), "Scope": PDFName(e["alcance"])})
            if "alt" in e:
                d["Alt"] = PDFString(e["alt"])
        nums = []
        for indice, pagina in enumerate(paginas):
            pagina.__NoDefault__ = [*pagina.__NoDefault__, "StructParents", "Tabs"]
            pagina.StructParents = indice
            pagina.Tabs = PDFName("S")
            nums += [indice, PDFArray([refs[id(e)] for e in self.por_pagina.get(indice + 1, [])])]
        raiz.dict.update(K=PDFArray([refs[id(self.documento)]]), ParentTree=PDFDictionary({"Nums": PDFArray(nums)}))
        pdf.Catalog.StructTreeRoot = raiz
        pdf.Catalog.MarkInfo = PDFDictionary({"Marked": "true"})


def etiquetado(base):
    """Flowable que, si tiene ``_etiqueta``, encierra su dibujo en contenido marcado; sus partes heredan la etiqueta."""

    class Etiquetado(base):
        _etiqueta: Optional[dict] = None

        def drawOn(self, canvas, x, y, _sW=0):
            if self._etiqueta is None:
                return super().drawOn(canvas, x, y, _sW)
            self._etiqueta["arbol"].abrir(canvas, self._etiqueta)
            super().drawOn(canvas, x, y, _sW)
            canvas._code.append("EMC")

        def split(self, ancho, alto):
            partes = super().split(ancho, alto)
            for parte in partes:
                parte._etiqueta = self._etiqueta
            return partes

    return Etiquetado


def artefacto(base):
    """Flowable que se dibuja como decoración (``/Artifact``): logotipos, líneas de firma."""

    class Artefacto(base):
        def drawOn(self, canvas, x, y, _sW=0):
            canvas._code.append("/Artifact BMC")
            super().drawOn(canvas, x, y, _sW)
            canvas._code.append("EMC")

    return Artefacto
