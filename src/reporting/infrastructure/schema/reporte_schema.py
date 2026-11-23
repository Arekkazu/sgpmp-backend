# | Fecha      | Nombre   | Que se hizo                                          |
# |------------|----------|------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: respuestas del catálogo, vista previa y reportes |
# | 2026-11-19 | Arekkazu | M08 RF-104: parámetros, indicadores y autor en la vista previa |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Esquemas de respuesta de los reportes (RF-104)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class FiltroCatalogoResponse(BaseModel):
    """Filtro de un reporte del catálogo."""
    nombre: str
    etiqueta: str
    tipo: str
    obligatorio: bool
    valores: list[str]


class ReporteCatalogoResponse(BaseModel):
    """Reporte del catálogo con sus filtros."""
    tipo_reporte: str
    titulo: str
    periodo_cerrado: bool
    compara_periodos: bool
    limite_sincrono: int
    filtros: list[FiltroCatalogoResponse]


class ColumnaResponse(BaseModel):
    """Columna de una tabla de la vista previa."""
    clave: str
    titulo: str
    tipo: str


class TablaPreviaResponse(BaseModel):
    """Tabla de la vista previa."""
    titulo: str
    nota: Optional[str] = None
    total_filas: int
    columnas: list[ColumnaResponse]
    filas: list[dict[str, Any]]


class SeccionPreviaResponse(BaseModel):
    """Sección de la vista previa."""
    titulo: str
    textos: list[str]
    tablas: list[TablaPreviaResponse]


class DatoEncabezadoResponse(BaseModel):
    """Dato del encabezado del reporte."""
    dato: str
    valor: str


class IndicadorResponse(BaseModel):
    """Indicador destacado del reporte."""
    etiqueta: str
    valor: Any
    tipo: str


class VistaPreviaResponse(BaseModel):
    """Vista previa de un reporte."""
    tipo_reporte: str
    titulo: str
    encabezado: list[DatoEncabezadoResponse]
    numero_registros: int
    en_segundo_plano: bool
    sin_datos: bool
    mensaje: Optional[str] = None
    resumen: list[TablaPreviaResponse]
    detalle: Optional[TablaPreviaResponse] = None
    secciones: list[SeccionPreviaResponse]
    finales: list[TablaPreviaResponse]
    advertencias: list[str]
    aclaraciones: list[str]
    generado_por: Optional[str] = None
    parametros: list[DatoEncabezadoResponse] = []
    indicadores: list[IndicadorResponse] = []


class ParteReporteResponse(BaseModel):
    """Parte descargable de un reporte."""
    numero_parte: int
    nombre_archivo: str
    tamano_bytes: int
    checksum_sha256: str


class ReporteResponse(BaseModel):
    """Una solicitud de reporte. ``url_descarga`` de cada parte: ``/reportes/{id}/partes/{n}/descarga``."""
    id_reporte: UUID
    tipo_reporte: str
    titulo: str
    formato: str
    estado: str
    filtros_aplicados: dict[str, Any]
    numero_registros: Optional[int] = None
    tamano_archivo_kb: Optional[int] = None
    checksum_sha256: Optional[str] = None
    mensaje: Optional[str] = None
    fecha_solicitud: Optional[datetime] = None
    fecha_generacion: Optional[datetime] = None
    fecha_expiracion: Optional[datetime] = None
    partes: list[ParteReporteResponse] = []
