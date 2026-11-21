# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-110: editar vía, dirección, intensidad y barrera de una arista |
"""El usuario ajusta su mapa: qué tanto transmite una relación (intensidad), si hay barrera, la vía o la
dirección. El RLS oculta las aristas de áreas ajenas, así que una que el usuario no ve es 404."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.arista_transmision import AristaTransmision
from src.configuration.domain.repositories.arista_transmision_repository import AristaTransmisionRepository
from src.configuration.infrastructure.dto.registrar_arista_transmision_dto import EditarAristaTransmisionDTO
from src.shared.errors import NotFoundError


class EditarAristaTransmisionUseCase:

    def __init__(self, db: Session, arista_repo: AristaTransmisionRepository) -> None:
        self.db = db
        self.arista_repo = arista_repo

    def execute(self, id_arista: int, dto: EditarAristaTransmisionDTO) -> AristaTransmision:
        arista = self.arista_repo.obtener_por_id(id_arista)
        if arista is None:
            raise NotFoundError(code="ARISTA_NO_ENCONTRADA", message=f"No existe la arista {id_arista}.")
        arista.editar(dto.cambios())
        try:
            arista = self.arista_repo.actualizar(arista)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return arista
