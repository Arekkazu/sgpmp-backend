# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-10 | —        | TC-M06-G109: consulta de marca y aviso limitado a identificadores explícitos |
"""Puerto de notificaciones internas de M06 al Contador (RF-14)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class NotificacionFinancieraPort(ABC):
    @abstractmethod
    def a_contadores(self, tipo_evento: str, mensaje: str, detalle: dict, id_finca: int | None = None) -> None:
        """Avisa a los Contadores (de la finca si se indica). Nunca propaga errores."""

    @abstractmethod
    def ya_notificado(self, tipo_evento: str, detalle: dict) -> bool:
        """Si ya se envió un aviso de ese tipo cuyo detalle contiene ``detalle``."""

    @abstractmethod
    def a_usuarios_autorizados(self, id_usuarios: tuple[int, ...] | list[int], tipo_evento: str,
                               mensaje: str, detalle: dict) -> bool:
        """Avisa solo a esos identificadores. Falso si no quedó evento ni notificación."""
