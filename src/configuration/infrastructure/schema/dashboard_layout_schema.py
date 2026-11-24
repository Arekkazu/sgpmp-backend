# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: opciones, frecuencia y cómo se dibuja cada widget        |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Schemas de respuesta del dashboard: layout, catálogo de widgets y datos (RF-28)."""
from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel

from src.reporting.domain.widgets import DEFINICIONES


class WidgetConfigResponse(BaseModel):
    """Posición de un widget en la grilla."""
    id_widget: int
    posicion_fila: int
    posicion_columna: int
    span_columnas: int
    visible: bool
    orden: int
    parametros: dict[str, Any] = {}


class DashboardLayoutResponse(BaseModel):
    """Dashboard del usuario con su ``version_perfil`` para el siguiente guardado."""
    id_dashboard_layout: Optional[int]
    id_usuario: int
    grid: list[WidgetConfigResponse]
    active_widget: list[str]
    fecha_actualizacion: Optional[datetime.datetime]
    # Segundos entre actualizaciones automáticas del dashboard (RF-103, 15-120).
    frecuencia_actualizacion: int
    # El cliente la devuelve en el PATCH para que el backend detecte que el perfil
    # cambió mientras editaba.
    version_perfil: Optional[int] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, entity, version_perfil: Optional[int] = None) -> DashboardLayoutResponse:
        """Construye la respuesta a partir de la entidad de dominio."""
        return cls(
            id_dashboard_layout=entity.id_dashboard_layout,
            id_usuario=entity.id_usuario,
            grid=[
                WidgetConfigResponse(
                    id_widget=w.id_widget,
                    posicion_fila=w.posicion_fila,
                    posicion_columna=w.posicion_columna,
                    span_columnas=w.span_columnas,
                    visible=w.visible,
                    orden=w.orden,
                    parametros=w.parametros,
                )
                for w in entity.grid
            ],
            active_widget=entity.active_widget,
            fecha_actualizacion=entity.fecha_actualizacion,
            frecuencia_actualizacion=entity.frecuencia_actualizacion,
            version_perfil=version_perfil,
        )


class OpcionWidgetResponse(BaseModel):
    """Opción configurable de un widget. ``tipo``: areas, area, especies, sensores o lista (con
    ``valores``). El front pone el texto de la opción y de cada valor."""
    nombre: str
    tipo: str
    valores: list[Any] = []
    defecto: Any = None


class WidgetCatalogoResponse(BaseModel):
    """Widget disponible para el rol del usuario, con cómo se dibuja y qué se configura (RF-103)."""
    id_widget: int
    clave: str
    nombre: str
    grupo: str
    span_predeterminado: int
    visual: Optional[str] = None
    opciones: list[OpcionWidgetResponse] = []
    requiere_finca: bool = True
    reacciona_a_alertas: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def desde_widget(cls, widget) -> WidgetCatalogoResponse:
        """Construye la respuesta a partir del widget del catálogo."""
        definicion = DEFINICIONES.get(widget.clave)
        extra = {} if definicion is None else {
            "visual": definicion.visual,
            "opciones": [OpcionWidgetResponse(nombre=o.nombre, tipo=o.tipo, valores=list(o.valores),
                                              defecto=o.defecto) for o in definicion.opciones],
            "requiere_finca": definicion.requiere_finca,
            "reacciona_a_alertas": definicion.reacciona_a_alertas,
        }
        return cls(id_widget=widget.id_widget, clave=widget.clave, nombre=widget.nombre, grupo=widget.grupo,
                   span_predeterminado=widget.span_predeterminado, **extra)


class WidgetDatosResponse(BaseModel):
    """Widget visible con sus datos; ``sin_datos`` y ``mensaje`` explican un widget
    vacío.
    """
    id_widget: int
    clave: str
    nombre: str
    posicion_fila: int
    posicion_columna: int
    span_columnas: int
    orden: int
    sin_datos: bool
    mensaje: Optional[str]
    datos: list[dict[str, Any]]

    model_config = {"from_attributes": True}
