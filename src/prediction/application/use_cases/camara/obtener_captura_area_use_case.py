# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66: lo que ve la cámara de un área (última captura o la de una ventana) |
"""Para Predicción: la captura más reciente de las cámaras del área (ficha del lote) o la de una
ventana concreta (detalle de una inferencia POBLACIONAL, por su ``fecha_fin_ventana``)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.prediction.domain.repositories.camaras_area_port import CamarasAreaPort
from src.shared.almacen_capturas import Captura, buscar_captura
from src.shared.errors import NotFoundError


class ObtenerCapturaAreaUseCase:

    def __init__(self, camaras_port: CamarasAreaPort) -> None:
        self.camaras_port = camaras_port

    def execute(self, id_area: int, ventana_fin: Optional[datetime] = None) -> Captura:
        camaras = self.camaras_port.camaras(id_area)
        if not camaras:
            raise NotFoundError(code="AREA_SIN_CAMARA", message="El área no tiene cámara de visión.")
        captura = buscar_captura(camaras, ventana_fin)
        if captura is None:
            raise NotFoundError(code="CAPTURA_NO_DISPONIBLE", message=(
                "La captura de esa ventana ya no está disponible: solo se guardan las más recientes."
                if ventana_fin else "La cámara todavía no ha enviado capturas."))
        return captura
