from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.prediction.domain.entities.retroalimentacion_clinica import RetroalimentacionClinica


class RetroalimentacionClinicaResponse(BaseModel):
    id_retroalimentacion: uuid.UUID
    id_resultado_inferencia: uuid.UUID
    id_activo_biologico: int
    estado_retroalimentacion: str
    diagnosticos_reales: Optional[list[int]]
    fuente_diagnostico: Optional[str]
    es_fuente_desconocida: bool
    es_conflicto_retroalimentacion: bool
    observaciones_clinicas: Optional[str]
    id_usuario_veterinario: int
    fecha_retroalimentacion: datetime
    estado_registro: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_entity(cls, e: RetroalimentacionClinica) -> "RetroalimentacionClinicaResponse":
        return cls(
            id_retroalimentacion=e.id_retroalimentacion,
            id_resultado_inferencia=e.id_resultado_inferencia,
            id_activo_biologico=e.id_activo_biologico,
            estado_retroalimentacion=e.estado_retroalimentacion,
            diagnosticos_reales=e.diagnosticos_reales,
            fuente_diagnostico=e.fuente_diagnostico,
            es_fuente_desconocida=e.es_fuente_desconocida,
            es_conflicto_retroalimentacion=e.es_conflicto_retroalimentacion,
            observaciones_clinicas=e.observaciones_clinicas,
            id_usuario_veterinario=e.id_usuario_veterinario,
            fecha_retroalimentacion=e.fecha_retroalimentacion,
            estado_registro=e.estado_registro,
        )
