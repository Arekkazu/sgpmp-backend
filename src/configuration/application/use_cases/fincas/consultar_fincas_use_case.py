"""Caso de uso: Listar o consultar finca(s) (GET RF-19)."""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.shared.errors import AuthorizationError, NotFoundError


class ConsultarFincasUseCase:

    def __init__(self, finca_repo: FincaRepository) -> None:
        self.finca_repo = finca_repo

    def listar(self, *, ids_fincas_permitidas: Optional[list[int]] = None, solo_activas: bool = False) -> list[Finca]:
        return self.finca_repo.listar(ids_fincas=ids_fincas_permitidas, solo_activas=solo_activas)

    def obtener(self, id_finca: int, *, ids_fincas_permitidas: Optional[list[int]] = None) -> Finca:
        finca = self.finca_repo.obtener_por_id(id_finca)
        if finca is None:
            raise NotFoundError(
                code="FINCA_NO_ENCONTRADA",
                message=f"No existe una finca con ID {id_finca}.",
            )
        if ids_fincas_permitidas is not None and id_finca not in ids_fincas_permitidas:
            raise AuthorizationError(
                code="FINCA_NO_AUTORIZADA",
                message="No tiene autorización para consultar la finca solicitada.",
            )
        return finca
