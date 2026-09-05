"""Schemas de respuesta de RF-81 — Historial/Trazabilidad de Suministros."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from src.supplies.domain.entities.historial_suministro import LineaHistorialSuministro, ResumenConsultaHistorial
from src.supplies.domain.entities.trabajo_historial_suministro import (
    EjecucionHistorialSuministro,
    TrabajoHistorialSuministro,
)


class LineaHistorialResponse(BaseModel):
    id_registro_suministro: str
    id_activo_biologico: int
    id_ciclo_productivo: int
    tipo_suministro: str
    descripcion: str
    fecha_aplicacion: datetime.date
    cantidad: Decimal
    unidad_medida: str
    precio_unitario: Decimal
    costo_registro: Decimal
    origen_precio: str
    tipo_operacion: str
    observacion: Optional[str]
    fecha_registro: Optional[datetime.datetime]
    nombre_activo: Optional[str]
    especie: Optional[str]
    nombre_ciclo: Optional[str]
    estado_ciclo: Optional[str]

    @classmethod
    def desde_entidad(cls, l: LineaHistorialSuministro) -> "LineaHistorialResponse":
        return cls(
            id_registro_suministro=l.id_registro_suministro,
            id_activo_biologico=l.id_activo_biologico,
            id_ciclo_productivo=l.id_ciclo_productivo,
            tipo_suministro=l.tipo_suministro,
            descripcion=l.descripcion,
            fecha_aplicacion=l.fecha_aplicacion,
            cantidad=l.cantidad,
            unidad_medida=l.unidad_medida,
            precio_unitario=l.precio_unitario,
            costo_registro=l.costo_registro,
            origen_precio=l.origen_precio,
            tipo_operacion=l.tipo_operacion,
            observacion=l.observacion,
            fecha_registro=l.fecha_registro,
            nombre_activo=l.nombre_activo,
            especie=l.especie,
            nombre_ciclo=l.nombre_ciclo,
            estado_ciclo=l.estado_ciclo,
        )


class ResumenHistorialResponse(BaseModel):
    total_registros_filtrados: int
    monto_total_filtrado: Decimal
    desglose_por_tipo_suministro: dict
    desglose_por_ciclo: dict
    pagina_actual: int
    total_paginas: int
    datos_contexto_no_disponibles: bool
    datos_actualizados_hasta: datetime.datetime
    nivel_volumen: int

    @classmethod
    def desde_entidad(cls, r: ResumenConsultaHistorial) -> "ResumenHistorialResponse":
        return cls(
            total_registros_filtrados=r.total_registros_filtrados,
            monto_total_filtrado=r.monto_total_filtrado,
            desglose_por_tipo_suministro=r.desglose_por_tipo_suministro,
            desglose_por_ciclo=r.desglose_por_ciclo,
            pagina_actual=r.pagina_actual,
            total_paginas=r.total_paginas,
            datos_contexto_no_disponibles=r.datos_contexto_no_disponibles,
            datos_actualizados_hasta=r.datos_actualizados_hasta,
            nivel_volumen=r.nivel_volumen,
        )


class HistorialSuministroListResponse(BaseModel):
    items: list[LineaHistorialResponse]
    resumen: ResumenHistorialResponse


class TrabajoHistorialResponse(BaseModel):
    """Respuesta HTTP 202 al encolar un trabajo pesado."""

    id_cola: Optional[int]
    tipo_trabajo: str
    estado: str
    fecha_solicitud: Optional[datetime.datetime]
    mensaje: str

    @classmethod
    def desde_entidad(cls, t: TrabajoHistorialSuministro, mensaje: str) -> "TrabajoHistorialResponse":
        return cls(
            id_cola=t.id_cola,
            tipo_trabajo=t.tipo_trabajo,
            estado=t.estado.value,
            fecha_solicitud=t.fecha_solicitud,
            mensaje=mensaje,
        )


class EstadoTrabajoHistorialResponse(BaseModel):
    id_cola: Optional[int]
    tipo_trabajo: str
    estado: str
    fecha_solicitud: Optional[datetime.datetime]
    fecha_procesado: Optional[datetime.datetime]
    intento: Optional[int]
    total_registros: Optional[int] = None

    @classmethod
    def desde_entidades(
        cls, trabajo: TrabajoHistorialSuministro, ejecucion: Optional[EjecucionHistorialSuministro]
    ) -> "EstadoTrabajoHistorialResponse":
        return cls(
            id_cola=trabajo.id_cola,
            tipo_trabajo=trabajo.tipo_trabajo,
            estado=trabajo.estado.value,
            fecha_solicitud=trabajo.fecha_solicitud,
            fecha_procesado=trabajo.fecha_procesado,
            intento=ejecucion.intento if ejecucion else None,
            total_registros=ejecucion.total_registros if ejecucion else None,
        )
