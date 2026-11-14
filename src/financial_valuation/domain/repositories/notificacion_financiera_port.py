# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-08 | Arekkazu | INC-M06-299-G81 RF-89: avisos de vencimiento sin duplicados tras reinicios (marca persistente) |
"""Puerto de notificaciones internas de M06 al Contador (RF-14)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class NotificacionFinancieraPort(ABC):
    @abstractmethod
    def a_contadores(self, tipo_evento: str, mensaje: str, detalle: dict, id_finca: int | None = None) -> None:
        """Avisa a los Contadores (de la finca si se indica). Nunca propaga errores."""

    @abstractmethod
    def ya_notificado(self, tipo_evento: str, detalle: dict) -> bool:
        """Si ya se envió un aviso de ese tipo cuyo detalle contiene ``detalle`` (deduplicación persistente)."""
