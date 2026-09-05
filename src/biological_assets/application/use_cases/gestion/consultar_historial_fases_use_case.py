from __future__ import annotations

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import GestionFase
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.shared.errors import NotFoundError


class ConsultarHistorialFasesUseCase:
    def __init__(self, db: Session, repo: ActivoBiologicoRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(self, id_activo: int) -> list[GestionFase]:
        activo = self.repo.obtener_por_id(id_activo)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )
        return self.repo.obtener_gestiones_fases(id_activo)
