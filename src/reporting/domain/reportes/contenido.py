# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: contenido de un reporte, independiente del formato  |
# | 2026-11-19 | Arekkazu | M08 RF-104: parámetros, indicadores y autor como en las plantillas V1.1 |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Contenido de un reporte, igual para PDF, Excel y la vista previa (RF-104).

- ``encabezado``: pares etiqueta/valor (finca, NIT, período…).
- ``resumen``: tablas de totales e indicadores (hoja «Resumen Ejecutivo» del Excel).
- ``detalle``: el cuerpo de registros (hoja «Datos Detallados»).
- ``secciones``: reportes por secciones (ficha del animal, ejecutivo): en el Excel, una hoja cada una.
- ``finales``: tablas que van al final del cuerpo en el PDF (totales, alertas de retiro, sensores sin calibrar);
  en el Excel, en el resumen.
- ``parametros``: los filtros con que se generó, legibles («Especie: Todas»), como «Parámetros de selección».
- ``indicadores``: las tarjetas de «Resumen ejecutivo de indicadores» de cada plantilla (total, valor, conteos).
- ``generado_por`` y ``generado``: quién lo pidió (nombre y rol) y cuándo, para la línea bajo el título.

Cada columna declara su tipo: el Excel guarda montos y números como NUMBER con 2 decimales y fechas como
DATE; el PDF y la vista previa los formatean. Ninguna celda se muestra vacía: quien arma el reporte pone el
texto que corresponde («Sin registro SINIGAN») y lo que quede en ``None`` sale como «Sin dato».
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

TEXTO, ENTERO, NUMERO, MONEDA, PORCENTAJE, FECHA, FECHA_HORA = (
    "TEXTO", "ENTERO", "NUMERO", "MONEDA", "PORCENTAJE", "FECHA", "FECHA_HORA")
SIN_DATO = "Sin dato"


@dataclass(frozen=True)
class Columna:
    """Columna de una tabla del reporte."""
    clave: str
    titulo: str
    tipo: str = TEXTO


@dataclass
class Tabla:
    """Tabla del reporte con sus columnas y filas."""
    titulo: str
    columnas: list[Columna]
    filas: list[dict[str, Any]] = field(default_factory=list)
    nota: Optional[str] = None


@dataclass(frozen=True)
class Indicador:
    """Indicador destacado del reporte."""
    etiqueta: str
    valor: Any
    tipo: str = TEXTO


@dataclass
class Seccion:
    """Sección del reporte con tablas y textos."""
    titulo: str
    tablas: list[Tabla] = field(default_factory=list)
    textos: list[str] = field(default_factory=list)


@dataclass
class ContenidoReporte:
    """Contenido completo de un reporte, independiente del formato."""
    titulo: str
    encabezado: list[tuple[str, str]] = field(default_factory=list)
    resumen: list[Tabla] = field(default_factory=list)
    detalle: Optional[Tabla] = None
    secciones: list[Seccion] = field(default_factory=list)
    finales: list[Tabla] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    aclaraciones: list[str] = field(default_factory=list)
    firma: Optional[str] = None
    parametros: list[tuple[str, str]] = field(default_factory=list)
    indicadores: list[Indicador] = field(default_factory=list)
    generado_por: str = ""
    generado: Optional[datetime] = None
    # Secciones que entran en la vista previa (la ficha del animal muestra solo las dos primeras).
    secciones_vista_previa: Optional[int] = None

    @property
    def numero_registros(self) -> int:
        """Registros del cuerpo: filas del detalle, o de las tablas de las secciones si no hay detalle."""
        if self.detalle is not None:
            return len(self.detalle.filas)
        return sum(len(t.filas) for s in self.secciones for t in s.tablas)

    @property
    def tiene_datos(self) -> bool:
        """FA-2: hay registros en el cuerpo. Los totales del resumen (que siempre tienen su fila «Total») no
        cuentan: un inventario vacío no se genera."""
        return self.numero_registros > 0
