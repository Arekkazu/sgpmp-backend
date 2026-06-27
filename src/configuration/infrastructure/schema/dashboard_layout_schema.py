"""Schema de respuesta para el layout del dashboard (RF-28)."""
from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel


class WidgetConfigResponse(BaseModel):
    id_widget: int
    posicion_fila: int
    posicion_columna: int
    span_columnas: int
    visible: bool
    orden: int


class DashboardLayoutResponse(BaseModel):
    id_dashboard_layout: Optional[int]
    id_usuario: int
    grid: list[WidgetConfigResponse]
    active_widget: list[str]
    fecha_actualizacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, entity) -> DashboardLayoutResponse:
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
        )
