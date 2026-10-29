"""Schemas de respuesta del dashboard: layout, catálogo de widgets y datos (RF-28)."""
from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel


class WidgetConfigResponse(BaseModel):
    """Posición de un widget en la grilla."""
    id_widget: int
    posicion_fila: int
    posicion_columna: int
    span_columnas: int
    visible: bool
    orden: int


class DashboardLayoutResponse(BaseModel):
    """Dashboard del usuario con su ``version_perfil`` para el siguiente guardado."""
    id_dashboard_layout: Optional[int]
    id_usuario: int
    grid: list[WidgetConfigResponse]
    active_widget: list[str]
    fecha_actualizacion: Optional[datetime.datetime]
    # El cliente la devuelve en el PATCH para que el backend detecte que el perfil
    # cambió mientras editaba.
    version_perfil: Optional[int] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, entity, version_perfil: Optional[int] = None) -> DashboardLayoutResponse:
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
                )
                for w in entity.grid
            ],
            active_widget=entity.active_widget,
            fecha_actualizacion=entity.fecha_actualizacion,
            version_perfil=version_perfil,
        )


class WidgetCatalogoResponse(BaseModel):
    """Widget disponible para el rol del usuario."""
    id_widget: int
    clave: str
    nombre: str
    grupo: str
    span_predeterminado: int

    model_config = {"from_attributes": True}


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
