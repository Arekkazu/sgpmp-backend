# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: entrada de vista previa y generación |
"""DTOs de entrada de los reportes (RF-104). El tipo y el formato se validan aquí (400 si no son del catálogo);
los filtros, contra la definición de cada reporte en el dominio."""
from typing import Any, Literal, Optional

from pydantic import Field

from src.reporting.domain.reportes.catalogo import CATALOGO
from src.shared.base_dto import BaseDTO

TipoReporte = Literal[tuple(CATALOGO)]  # type: ignore[valid-type]


class VistaPreviaReporteDTO(BaseDTO):
    tipo_reporte: TipoReporte
    filtros: Optional[dict[str, Any]] = Field(default=None, description="Filtros del reporte (ver /reportes/catalogo)")


class SolicitarReporteDTO(VistaPreviaReporteDTO):
    formato: Literal["PDF", "EXCEL"]
