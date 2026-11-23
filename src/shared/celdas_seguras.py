"""Celdas de texto en las exportaciones a CSV y Excel.

Un texto libre que empieza con ``=``, ``+``, ``-``, ``@``, tabulador o retorno de carro se interpretaría
como fórmula al abrir el archivo en Excel o LibreOffice. Estas funciones lo dejan como texto.

- **CSV:** se antepone un apóstrofo al texto peligroso. Los números negativos (``-12,5``) no se tocan.
- **Excel:** openpyxl guarda como fórmula toda cadena que empiece con ``=``. :func:`proteger_libro`
  vuelve a texto toda celda que haya quedado como fórmula; el texto que se ve no cambia. El sistema no
  genera fórmulas propias en sus exportaciones, así que no se pierde nada.

Lo usan el generador compartido de M05/M06 y el de reportes de M08.
"""
from __future__ import annotations

import re
from typing import Any

_INICIO_PELIGROSO = ("=", "+", "-", "@", "\t", "\r")
_NUMERO = re.compile(r"^[+-]?\d[\d.,]*(?:[eE][+-]?\d+)?%?$")


def texto_seguro_csv(valor: Any) -> Any:
    """Devuelve el valor listo para una celda de CSV, sin que el texto pueda ejecutarse como fórmula."""
    if isinstance(valor, str) and valor.startswith(_INICIO_PELIGROSO) and not _NUMERO.match(valor):
        return "'" + valor
    return valor


def proteger_libro(libro) -> None:
    """Convierte en texto toda celda que openpyxl haya guardado como fórmula, en todas las hojas."""
    for hoja in libro.worksheets:
        for fila in hoja.iter_rows():
            for celda in fila:
                if celda.data_type == "f":
                    celda.data_type = "s"
