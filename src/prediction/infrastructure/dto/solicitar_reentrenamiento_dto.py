# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71/RF-73: solicitud de reentrenamiento como evento de auditoría |
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: solicitud por animal y procesos de reentrenamiento |
from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from src.shared.base_dto import BaseDTO


class SolicitarReentrenamientoDTO(BaseDTO):
    """Por tipo de modelo (solo bitácora) o, con ``id_activo_biologico``, por animal: abre un
    proceso que el motor de IA ejecuta (AJF-14). Hace falta uno de los dos."""
    tipo_modelo: Optional[str] = Field(default=None, description="MODELO_ESPECIES_GRANDES o MODELO_ESPECIES_MEDIANAS")
    id_activo_biologico: Optional[int] = Field(default=None, gt=0, description="Animal cuyo modelo se reentrena (AJF-14).")
    motivo: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _uno_de_los_dos(self) -> "SolicitarReentrenamientoDTO":
        if self.tipo_modelo is None and self.id_activo_biologico is None:
            raise ValueError("Indica tipo_modelo o id_activo_biologico.")
        return self
