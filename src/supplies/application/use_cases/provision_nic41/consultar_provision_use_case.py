"""Casos de uso de solo lectura sobre provisiones consolidadas NIC-41 (RF-79)."""
from __future__ import annotations

from src.shared.errors import NotFoundError
from src.supplies.domain.entities.provision_nic41 import ProvisionNic41
from src.supplies.domain.repositories.provision_nic41_repository import ProvisionNic41Repository


class ConsultarProvisionUseCase:
    """Consulta puntual de un reporte consolidado por id."""

    def __init__(self, provision_repo: ProvisionNic41Repository) -> None:
        self.provision_repo = provision_repo

    def execute(self, id_provision: int) -> ProvisionNic41:
        provision = self.provision_repo.obtener(id_provision)
        if provision is None:
            raise NotFoundError(
                code="PROVISION_NO_ENCONTRADA",
                message=f"El reporte de provisión {id_provision} no existe.",
            )
        return provision


class ListarVersionesProvisionUseCase:
    """Lista la cadena completa de versiones de una instancia de ciclo, ordenada ascendente."""

    def __init__(self, provision_repo: ProvisionNic41Repository) -> None:
        self.provision_repo = provision_repo

    def execute(self, id_gestion_fases: int) -> list[ProvisionNic41]:
        return self.provision_repo.listar_versiones(id_gestion_fases)
