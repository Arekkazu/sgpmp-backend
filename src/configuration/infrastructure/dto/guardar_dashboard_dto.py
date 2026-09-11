"""DTO de entrada para guardar la configuración del dashboard (RF-28)."""
from __future__ import annotations

from typing import Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO


class WidgetConfigDTO(BaseDTO):
    id_widget: int
    posicion_fila: int = Field(ge=1, le=3)
    posicion_columna: int = Field(ge=1, le=4)
    span_columnas: int = Field(ge=1, le=2)
    visible: bool
    orden: int = Field(ge=0)


class GuardarDashboardDTO(BaseDTO):
    layout_config: list[WidgetConfigDTO]
    active_widget: list[str]
    # Versión del perfil que el cliente leyó en el GET. Si el administrador cambió
    # el rol o la finca del usuario entre la lectura y el guardado, el contexto de
    # la personalización ya no es el mismo y el RF pide rechazar con 409. Opcional
    # para no romper a los clientes que todavía no la envían.
    version_perfil: Optional[int] = None
