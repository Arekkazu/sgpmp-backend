# | Fecha      | Nombre   | Que se hizo                                             |
# |------------|----------|---------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-66: especie del activo para el resultado del motor IA |
from __future__ import annotations

from typing import Optional

from src.prediction.domain.repositories.activo_biologico_port import ActivoBiologicoPort


class ActivoBiologicoStubAdapter(ActivoBiologicoPort):
    def activo_existe_y_accesible(self, id_activo: int, id_usuario: int, id_rol: int) -> bool:
        return True

    def obtener_especie(self, id_activo: int) -> Optional[int]:
        return None
