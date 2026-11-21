# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-320-G24 RF-85 FA-4: baja del activo cosechado completamente |
"""Puerto hacia M02 para iniciar la baja de un activo (RF-45) desde M06.

RF-85 FA-4: cuando la cosecha de un PRODUCTO_DE_CONSUMO equivale al 100 % del activo, M06 inicia su baja."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional


class BajaActivoPort(ABC):
    @abstractmethod
    def dar_de_baja_por_cosecha(self, id_activo_biologico: int, fecha: date, motivo: str) -> Optional[str]:
        """Registra la baja total del activo en M02 en su propia transacción.

        Devuelve ``None`` si quedó registrada o el mensaje por el que M02 la rechazó. Nunca propaga errores."""
