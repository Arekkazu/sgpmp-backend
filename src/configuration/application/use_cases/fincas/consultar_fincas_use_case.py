"""Caso de uso: Listar o consultar finca(s) (GET RF-19)."""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.shared.errors import NotFoundError


class ConsultarFincasUseCase:

    def __init__(self, finca_repo: FincaRepository) -> None:
        self.finca_repo = finca_repo

    def listar(self, *, id_usuario_filtro: Optional[int] = None, solo_activas: bool = False) -> list[Finca]:
        return self.finca_repo.listar(id_usuario_filtro=id_usuario_filtro, solo_activas=solo_activas)

    def obtener(self, id_finca: int, *, id_usuario_filtro: Optional[int] = None) -> Finca:
        finca = self.finca_repo.obtener_por_id(id_finca)
        if finca is None:
            raise NotFoundError(
                code="FINCA_NO_ENCONTRADA",
                message=f"No existe una finca con ID {id_finca}.",
            )
        if id_usuario_filtro is not None and finca.id_usuario != id_usuario_filtro:
            raise NotFoundError(
                code="FINCA_NO_ENCONTRADA",
                message=f"No existe una finca con ID {id_finca}.",
            )
        return finca
