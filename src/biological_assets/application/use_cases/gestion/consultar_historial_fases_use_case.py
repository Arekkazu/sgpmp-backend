"""Caso de uso: historial de fases productivas de un activo (RF-37)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import GestionFase
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.shared.errors import NotFoundError


class ConsultarHistorialFasesUseCase:
    """Lista todas las gestiones de fase del activo, incluida la vigente."""

    def __init__(self, db: Session, repo: ActivoBiologicoRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(
        self,
        id_activo: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[GestionFase]:
        activo = self.repo.obtener_por_id(id_activo, ids_fincas_permitidas=ids_fincas_permitidas)
        if activo is None:
            raise NotFoundError(
                code='ACTIVO_NO_ENCONTRADO',
                message=f'El activo biológico con ID {id_activo} no existe.',
            )
        return self.repo.obtener_gestiones_fases(id_activo)
