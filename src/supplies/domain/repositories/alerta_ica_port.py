"""Puerto para generar la alerta de conversión alimenticia crítica (RF-74 paso 8, CA-3).

Al clasificar ``CRITICA`` se persiste una alerta en ``modulo3.alertas`` reutilizando
la infraestructura de telemetría. La notificación push/email real se hace fuera de la
transacción (después del ``commit``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional


class AlertaICAPort(ABC):
    @abstractmethod
    def generar_alerta_critica(
        self,
        *,
        id_activo_biologico: int,
        ca_calculado: Decimal,
        periodo_evaluacion: str,
        origen_evento: str,
        fecha_evento: datetime,
    ) -> Optional[int]:
        """Inserta una alerta CONVERSION_ALIMENTICIA / CRITICO (``flush()``); devuelve
        el id de la alerta creada."""
        raise NotImplementedError
