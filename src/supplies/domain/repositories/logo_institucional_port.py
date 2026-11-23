# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77: logo en el encabezado del PDF      |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto del logotipo institucional (RF-26) para el encabezado del PDF de RF-77."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class LogoInstitucionalPort(ABC):
    """Puerto para obtener el logo de la finca de un activo o área."""
    @abstractmethod
    def ruta_logo(self, *, id_activo_biologico: Optional[int] = None,
                  id_infraestructura: Optional[int] = None) -> Optional[str]:
        """Ruta en disco del logo PNG/JPEG de la finca, o ``None`` si no hay uno utilizable."""
        raise NotImplementedError
