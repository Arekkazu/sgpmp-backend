"""Caso de uso: Consultar la auditoría de un umbral ambiental (RF-17 — TC-M09-64).

INC-M09-30-G30: la auditoría se persistía en ``modulo9.auditorias_umbrales_ambientales``
pero no existía API para consultarla, por lo que no podía correlacionarse cada
operación (usuario, fecha, tipo y valores) con el ``id_umbral_ambiental``.
"""
from __future__ import annotations

from src.configuration.domain.entities.auditoria_umbral import AuditoriaUmbral
from src.configuration.domain.repositories.auditoria_umbral_repository import AuditoriaUmbralRepository
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository
from src.shared.errors import NotFoundError


class ConsultarAuditoriaUmbralUseCase:

    def __init__(
        self,
        auditoria_repo: AuditoriaUmbralRepository,
        umbral_repo: UmbralAmbientalRepository,
    ) -> None:
        self.auditoria_repo = auditoria_repo
        self.umbral_repo = umbral_repo

    def execute(self, id_umbral_ambiental: int) -> list[AuditoriaUmbral]:
        if self.umbral_repo.obtener_por_id(id_umbral_ambiental) is None:
            raise NotFoundError(
                code="UMBRAL_NO_ENCONTRADO",
                message=f"No existe el umbral ambiental con ID {id_umbral_ambiental}.",
            )
        return self.auditoria_repo.listar_por_umbral(id_umbral_ambiental)
