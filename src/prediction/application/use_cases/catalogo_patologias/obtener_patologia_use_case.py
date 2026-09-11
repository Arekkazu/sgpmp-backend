from __future__ import annotations

from src.prediction.domain.entities.patologia_m04 import PatologiaM04
from src.prediction.domain.repositories.patologia_m04_repository import PatologiaM04Repository
from src.shared.errors import NotFoundError


class ObtenerPatologiaUseCase:
    def __init__(self, *, repo: PatologiaM04Repository) -> None:
        self._repo = repo

    def execute(self, id_patologia: int) -> PatologiaM04:
        entidad = self._repo.obtener_por_id(id_patologia)
        if not entidad:
            raise NotFoundError(code="PATOLOGIA_NO_ENCONTRADA", message="Patología no encontrada.")
        return entidad
