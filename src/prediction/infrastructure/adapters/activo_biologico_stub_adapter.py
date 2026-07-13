from __future__ import annotations

from src.prediction.domain.repositories.activo_biologico_port import ActivoBiologicoPort


class ActivoBiologicoStubAdapter(ActivoBiologicoPort):
    def activo_existe_y_accesible(self, id_activo: int, id_usuario: int, id_rol: int) -> bool:
        return True
