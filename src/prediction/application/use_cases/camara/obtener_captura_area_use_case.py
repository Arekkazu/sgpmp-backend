# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66: lo que ve la cámara de un área (última captura o la de una ventana) |
# | 2026-11-02 | Arekkazu | RF-66 POBLACIONAL: inventario del área y aviso de discrepancia del conteo |
"""Para Predicción: la captura más reciente de las cámaras del área (ficha del lote) o la de una
ventana concreta (detalle de una inferencia POBLACIONAL, por su ``fecha_fin_ventana``), junto con el
inventario del área y, para la captura actual, si el conteo de la cámara se aleja de él."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.conteo_poblacional import VENTANAS, hay_discrepancia
from src.prediction.domain.repositories.camaras_area_port import CamarasAreaPort
from src.shared.almacen_capturas import Captura, buscar_captura
from src.shared.errors import NotFoundError


@dataclass(frozen=True)
class CapturaArea:
    captura: Captura
    cantidad_registrada: Optional[int]
    #: Solo para la captura actual: una ventana vieja no dice cómo está el lote hoy.
    discrepancia_inventario: bool


class ObtenerCapturaAreaUseCase:

    def __init__(self, camaras_port: CamarasAreaPort) -> None:
        self.camaras_port = camaras_port

    def execute(self, id_area: int, ventana_fin: Optional[datetime] = None) -> CapturaArea:
        camaras = self.camaras_port.camaras(id_area)
        if not camaras:
            raise NotFoundError(code="AREA_SIN_CAMARA", message="El área no tiene cámara de visión.")
        captura = buscar_captura(camaras, ventana_fin)
        if captura is None:
            raise NotFoundError(code="CAPTURA_NO_DISPONIBLE", message=(
                "La captura de esa ventana ya no está disponible: solo se guardan las más recientes."
                if ventana_fin else "La cámara todavía no ha enviado capturas."))
        registrada = self.camaras_port.cantidad_registrada(id_area)
        discrepancia = ventana_fin is None and hay_discrepancia(
            self.camaras_port.conteos_recientes(id_area, VENTANAS), registrada)
        return CapturaArea(captura, registrada, discrepancia)
