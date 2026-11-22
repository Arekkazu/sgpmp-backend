# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: opciones por widget y frecuencia de actualización |
"""DTO de entrada para guardar la configuración del dashboard (RF-28)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO


class WidgetConfigDTO(BaseDTO):
    """Posición de un widget en la grilla 4×3 (fila 1-3, columna 1-4)."""
    id_widget: int
    posicion_fila: int = Field(ge=1, le=3)
    posicion_columna: int = Field(ge=1, le=4)
    span_columnas: int = Field(ge=1, le=2)
    visible: bool
    orden: int = Field(ge=0)
    # Opciones de "Configurar widget" (RF-103); se validan contra el catálogo del widget.
    parametros: dict[str, Any] = Field(default_factory=dict)


class GuardarDashboardDTO(BaseDTO):
    """Grilla completa del dashboard y claves de los widgets activos (máximo 12).

    ``version_perfil`` debe ser la leída (409 si el perfil cambió).
    """
    layout_config: list[WidgetConfigDTO]
    active_widget: list[str]
    # Versión del perfil que el cliente leyó en el GET. Si el administrador cambió
    # el rol o la finca del usuario entre la lectura y el guardado, el contexto de
    # la personalización ya no es el mismo y el RF pide rechazar con 409. Opcional
    # para no romper a los clientes que todavía no la envían.
    version_perfil: Optional[int] = None
    # Segundos entre actualizaciones automáticas del dashboard (RF-103). Sin enviar: se conserva.
    frecuencia_actualizacion: Optional[int] = Field(default=None, ge=15, le=120)
