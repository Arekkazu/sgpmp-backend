"""Consulta del historial auditable de identidad visual (RF-26, TC-M09-169)."""
from __future__ import annotations

from src.configuration.domain.entities.auditoria_identidad_visual import AuditoriaIdentidadVisual
from src.configuration.domain.repositories.auditoria_identidad_visual_repository import AuditoriaIdentidadVisualRepository
from src.configuration.domain.repositories.identidad_visual_repository import IdentidadVisualRepository
from src.shared.errors import NotFoundError


class ConsultarAuditoriaIdentidadVisualUseCase:

    def __init__(
        self,
        auditoria_repo: AuditoriaIdentidadVisualRepository,
        identidad_repo: IdentidadVisualRepository,
    ) -> None:
        self.auditoria_repo = auditoria_repo
        self.identidad_repo = identidad_repo

    def execute(self, id_finca: int) -> list[AuditoriaIdentidadVisual]:
        if self.identidad_repo.obtener_por_finca(id_finca) is None:
            raise NotFoundError(
                code="IDENTIDAD_VISUAL_NO_ENCONTRADA",
                message=f"No existe identidad visual registrada para la finca {id_finca}.",
            )
        return self.auditoria_repo.listar_por_finca(id_finca)
