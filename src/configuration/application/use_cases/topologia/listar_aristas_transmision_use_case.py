# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: aristas activas de una finca               |
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.arista_transmision import AristaTransmision
from src.configuration.domain.repositories.arista_transmision_repository import AristaTransmisionRepository
from src.shared.errors import NotFoundError


class ListarAristasTransmisionUseCase:

    def __init__(self, arista_repo: AristaTransmisionRepository) -> None:
        self.arista_repo = arista_repo

    def execute(self, id_finca: int, ids_fincas_permitidas: Optional[list[int]] = None) -> list[AristaTransmision]:
        if ids_fincas_permitidas is not None and id_finca not in ids_fincas_permitidas:
            raise NotFoundError(code="FINCA_NO_ENCONTRADA", message=f"No existe la finca {id_finca}.",
                                field="id_finca")
        return self.arista_repo.listar_activas_por_finca(id_finca)
