"""Caso de uso: listado paginado de activos biológicos (RF-35 / RF-36)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.domain.repositories.activo_biologico_repository import ActivoBiologicoRepository
from src.biological_assets.infrastructure.dto.listar_activos_dto import ListarActivosDTO


class ListarActivosUseCase:
    """Lista activos con filtros por especie, tipo, estado e infraestructura, limitado a
    las fincas del usuario.
    """

    def __init__(self, db: Session, repo: ActivoBiologicoRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(
        self,
        dto: ListarActivosDTO,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[ActivoBiologico], int]:
        return self.repo.listar(
            id_especie=dto.id_especie,
            tipo=dto.tipo,
            id_estado=dto.id_estado,
            id_infraestructura=dto.id_infraestructura,
            pagina=dto.pagina,
            page_size=dto.page_size,
            ids_fincas_permitidas=ids_fincas_permitidas,
        )
