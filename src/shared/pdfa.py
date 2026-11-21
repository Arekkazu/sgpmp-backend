# | Fecha      | Nombre         | Que se hizo                                                            |
# |------------|----------------|------------------------------------------------------------------------|
# | 2026-11-13 | LuisfNarvaez01 | TC-M06-G70 RF-92: PDF/A-1b (fuente incrustada, perfil sRGB y metadatos XMP) |
"""Conformidad PDF/A-1b (ISO 19005-1) para los PDF de ReportLab, que no la trae de fábrica.

Un PDF/A-1b necesita:

- todas las fuentes incrustadas: se usa la TrueType Vera que viene con ReportLab (las 14 estándar, como
  Helvetica, no se incrustan), también como fuente inicial del lienzo, que si no declara Helvetica en cada página;
- un *OutputIntent* ``GTS_PDFA1`` con un perfil ICC de versión 2 (PDF/A-1 no admite la 4, que es la que genera
  Pillow), así que el perfil sRGB se arma aquí;
- metadatos XMP sin comprimir con ``pdfaid:part=1`` y ``pdfaid:conformance=B``, coherentes con el diccionario
  Info (título, autor, asunto, palabras clave, creador, productor y fechas).

Uso: :data:`FUENTE` / :data:`FUENTE_NEGRITA` en los estilos, ``initialFontName=FUENTE`` en la plantilla y
:func:`aplicar_pdfa1b` sobre el lienzo después de ``build`` y antes de ``save``.
"""
from __future__ import annotations

import struct
from functools import lru_cache
from xml.sax.saxutils import escape

FUENTE = "SGPMP-Sans"
FUENTE_NEGRITA = "SGPMP-Sans-Bold"
CONDICION_SALIDA = "sRGB IEC61966-2.1"


def registrar_fuentes() -> None:
    """Registra las TrueType incrustables (Vera, con licencia libre, incluida en ReportLab)."""
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if FUENTE in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(FUENTE, "Vera.ttf"))
    pdfmetrics.registerFont(TTFont(FUENTE_NEGRITA, "VeraBd.ttf"))
    addMapping(FUENTE, 0, 0, FUENTE)
    addMapping(FUENTE, 1, 0, FUENTE_NEGRITA)
    addMapping(FUENTE, 0, 1, FUENTE)
    addMapping(FUENTE, 1, 1, FUENTE_NEGRITA)


# --- Perfil ICC sRGB, versión 2.1 (ICC.1:1998-09) ------------------------------------------------------------

def _s15(valor: float) -> bytes:
    return struct.pack(">i", round(valor * 65536))


def _xyz(x: float, y: float, z: float) -> bytes:
    return b"XYZ " + bytes(4) + _s15(x) + _s15(y) + _s15(z)


def _curva_srgb(puntos: int = 1024) -> bytes:
    valores = []
    for i in range(puntos):
        v = i / (puntos - 1)
        lineal = v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        valores.append(struct.pack(">H", round(lineal * 65535)))
    return b"curv" + bytes(4) + struct.pack(">I", puntos) + b"".join(valores)


def _descripcion(texto: str) -> bytes:
    ascii_ = texto.encode("ascii") + b"\0"
    # textDescriptionType: ASCII, Unicode vacío (idioma + largo) y ScriptCode vacío (2 + 1 + 67 bytes).
    return b"desc" + bytes(4) + struct.pack(">I", len(ascii_)) + ascii_ + bytes(8) + bytes(3) + bytes(67)


@lru_cache(maxsize=1)
def perfil_srgb_v2() -> bytes:
    """Perfil de monitor sRGB (matriz + curvas), con primarios adaptados a D50 como pide el espacio de conexión."""
    curva = _curva_srgb()
    etiquetas = [
        (b"desc", _descripcion(CONDICION_SALIDA)),
        (b"cprt", b"text" + bytes(4) + b"Sin restricciones de uso\0"),
        (b"wtpt", _xyz(0.9505, 1.0, 1.0890)),
        (b"rXYZ", _xyz(0.4361, 0.2225, 0.0139)),
        (b"gXYZ", _xyz(0.3851, 0.7169, 0.0971)),
        (b"bXYZ", _xyz(0.1431, 0.0606, 0.7141)),
        (b"rTRC", curva), (b"gTRC", curva), (b"bTRC", curva),
    ]
    inicio = 128 + 4 + 12 * len(etiquetas)
    tabla, datos, ubicacion = [], b"", {}
    for firma, contenido in etiquetas:
        if contenido not in ubicacion:  # las tres curvas comparten los mismos bytes
            ubicacion[contenido] = inicio + len(datos)
            datos += contenido + bytes(-len(contenido) % 4)
        tabla.append(firma + struct.pack(">II", ubicacion[contenido], len(contenido)))
    cuerpo = struct.pack(">I", len(etiquetas)) + b"".join(tabla) + datos
    cabecera = (struct.pack(">I", 128 + len(cuerpo)) + bytes(4) + bytes([2, 0x10, 0, 0]) + b"mntr" + b"RGB " + b"XYZ "
                + struct.pack(">6H", 2026, 1, 1, 0, 0, 0) + b"acsp" + bytes(4) + bytes(4) + bytes(4) + bytes(4)
                + bytes(8) + bytes(4) + _s15(0.9642) + _s15(1.0) + _s15(0.8249) + bytes(4) + bytes(44))
    assert len(cabecera) == 128
    return cabecera + cuerpo


# --- Metadatos XMP -------------------------------------------------------------------------------------------

def _fecha_xmp(marca) -> str:
    y, mes, d, h, mi, s = marca.YMDhms
    return f"{y:04d}-{mes:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}{marca.dhh:+03d}:{marca.dmm:02d}"


def xmp_pdfa1b(*, titulo: str, autor: str, asunto: str, palabras: str, creador: str, productor: str, fecha: str) -> bytes:
    t, a, s, k, c, p = (escape(v or "") for v in (titulo, autor, asunto, palabras, creador, productor))
    return f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">
   <pdfaid:part>1</pdfaid:part>
   <pdfaid:conformance>B</pdfaid:conformance>
  </rdf:Description>
  <rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{t}</rdf:li></rdf:Alt></dc:title>
   <dc:creator><rdf:Seq><rdf:li>{a}</rdf:li></rdf:Seq></dc:creator>
   <dc:description><rdf:Alt><rdf:li xml:lang="x-default">{s}</rdf:li></rdf:Alt></dc:description>
  </rdf:Description>
  <rdf:Description rdf:about="" xmlns:pdf="http://ns.adobe.com/pdf/1.3/">
   <pdf:Producer>{p}</pdf:Producer>
   <pdf:Keywords>{k}</pdf:Keywords>
  </rdf:Description>
  <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
   <xmp:CreatorTool>{c}</xmp:CreatorTool>
   <xmp:CreateDate>{fecha}</xmp:CreateDate>
   <xmp:ModifyDate>{fecha}</xmp:ModifyDate>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>""".encode("utf-8")


def aplicar_pdfa1b(lienzo) -> None:
    """Agrega el OutputIntent y los metadatos XMP al documento del lienzo (antes de ``save``)."""
    from reportlab.pdfbase import pdfdoc
    from reportlab.pdfbase.pdfdoc import PDFArray, PDFDictionary, PDFName, PDFString

    class _StreamCrudo(pdfdoc.PDFStream):
        """Stream sin filtros (los metadatos XMP no pueden ir comprimidos) y con ``Length`` exacto."""

        def format(self, document):
            diccionario = PDFDictionary({**self.dictionary.dict, "Length": len(self.content)})
            return pdfdoc.format(diccionario, document) + b"\nstream\n" + self.content + b"\nendstream\n"

    pdf = lienzo._doc
    info = pdf.info
    pdf.Catalog.Metadata = _StreamCrudo(PDFDictionary({"Type": PDFName("Metadata"), "Subtype": PDFName("XML")}),
                                        content=xmp_pdfa1b(titulo=info.title, autor=info.author, asunto=info.subject,
                                                           palabras=info.keywords, creador=info.creator,
                                                           productor=info.producer, fecha=_fecha_xmp(pdf._timeStamp)))
    perfil = _StreamCrudo(PDFDictionary({"N": 3}), content=perfil_srgb_v2())
    pdf.Catalog.OutputIntents = PDFArray([PDFDictionary({
        "Type": PDFName("OutputIntent"), "S": PDFName("GTS_PDFA1"),
        "OutputConditionIdentifier": PDFString(CONDICION_SALIDA), "Info": PDFString(CONDICION_SALIDA),
        "DestOutputProfile": pdf.Reference(perfil),
    })])
    # El catálogo de ReportLab solo escribe las llaves que conoce: se le suma OutputIntents.
    pdf.Catalog.__NoDefault__ = [*pdfdoc.PDFCatalog.__NoDefault__, "OutputIntents"]
