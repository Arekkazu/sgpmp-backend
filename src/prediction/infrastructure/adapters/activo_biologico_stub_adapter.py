# | Fecha      | Nombre   | Que se hizo                                             |
# |------------|----------|---------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: especie del activo para el resultado del motor IA |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Stub de acceso a activos biológicos."""
from __future__ import annotations

from typing import Optional

from src.prediction.domain.repositories.activo_biologico_port import ActivoBiologicoPort


class ActivoBiologicoStubAdapter(ActivoBiologicoPort):
    """Stub que considera accesible cualquier activo."""
    def activo_existe_y_accesible(self, id_activo: int, id_usuario: int, id_rol: int) -> bool:
        """Siempre ``True``."""
        return True

    def obtener_especie(self, id_activo: int) -> Optional[int]:
        """id_especie del activo, o None si no existe (RF-66: lo usa el motor IA)."""
        return None
