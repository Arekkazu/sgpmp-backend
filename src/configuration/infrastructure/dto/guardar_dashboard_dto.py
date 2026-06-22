"""DTO de entrada para guardar la configuración del dashboard (PATCH RF-28)."""
from pydantic import Field, field_validator

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
