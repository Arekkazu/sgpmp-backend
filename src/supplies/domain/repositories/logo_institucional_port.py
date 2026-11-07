# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77: logo en el encabezado del PDF      |
"""Puerto del logotipo institucional (RF-26) para el encabezado del PDF de RF-77."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class LogoInstitucionalPort(ABC):
    @abstractmethod
    def ruta_logo(self, *, id_activo_biologico: Optional[int] = None,
                  id_infraestructura: Optional[int] = None) -> Optional[str]:
        """Ruta en disco del logo PNG/JPEG de la finca, o ``None`` si no hay uno utilizable."""
        raise NotImplementedError
