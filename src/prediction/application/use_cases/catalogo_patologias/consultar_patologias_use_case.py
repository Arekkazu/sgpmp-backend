from __future__ import annotations

from typing import Optional

from src.prediction.domain.entities.patologia_m04 import PatologiaM04
from src.prediction.domain.repositories.patologia_m04_repository import PatologiaM04Repository


class ConsultarPatologiasUseCase:
    def __init__(self, *, repo: PatologiaM04Repository) -> None:
        self._repo = repo

    def execute(
        self,
        especie_aplicable: Optional[str] = None,
        solo_activas: Optional[bool] = None,
        solo_base: Optional[bool] = None,
    ) -> list[PatologiaM04]:
        return self._repo.listar(
            especie_aplicable=especie_aplicable,
            solo_activas=solo_activas,
            solo_base=solo_base,
        )
