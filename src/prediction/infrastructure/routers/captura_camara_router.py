# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66: GET de lo que ve la cámara de un área                     |
"""Lo que ve la cámara de un área (Predicción › Estado sanitario y detalle de la inferencia).

  GET /prediccion/areas/{id_area}/captura[?ventana_fin=] — última captura de sus cámaras, o la de
      esa ventana. Mismo recurso que el monitor (42, R); la RLS de M09 limita a las áreas del usuario.
"""
from __future__ import annotations

import base64
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.prediction.application.use_cases.camara.obtener_captura_area_use_case import ObtenerCapturaAreaUseCase
from src.prediction.infrastructure.adapters.camaras_area_m09_adapter import CamarasAreaM09Adapter
from src.shared.database import get_db
from src.shared.fechas import FechaHoraUtc
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion/areas", tags=["Predicción M04 - Monitor de Inferencia"])

_RECURSO = 42  # modulo1.recursos: 'historial_diagnostico'


class CapturaCamaraResponse(BaseModel):
    id_dispositivo_iot: int
    fecha: datetime
    n_individuos: Optional[int]
    #: data URL lista para un <img src>.
    imagen: str


@router.get(
    "/{id_area}/captura",
    response_model=CapturaCamaraResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Lo que ve la cámara del área: última captura o la de una ventana",
)
def obtener_captura(
    id_area: int,
    ventana_fin: Optional[FechaHoraUtc] = Query(None, description="Fin de la ventana de una inferencia POBLACIONAL."),
    db: Session = Depends(get_db),
) -> CapturaCamaraResponse:
    """404 AREA_SIN_CAMARA si el área no tiene cámara (o no es del usuario); 404
    CAPTURA_NO_DISPONIBLE si todavía no hay o si esa ventana ya se descartó."""
    c = ObtenerCapturaAreaUseCase(CamarasAreaM09Adapter(db)).execute(id_area, ventana_fin)
    return CapturaCamaraResponse(
        id_dispositivo_iot=c.id_dispositivo_iot, fecha=c.fecha, n_individuos=c.n_individuos,
        imagen="data:image/jpeg;base64," + base64.b64encode(c.jpeg).decode(),
    )
