# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79 E4: versión N+1, SUPERADO y a M06   |
"""Caso de uso: corregir un reporte consolidado NIC-41 (RF-79 E4).

Genera la versión N+1 con ``id_reporte_anterior`` y ``motivo_correccion``; la
versión anterior queda SUPERADO (no se elimina), el hash se recalcula y la
nueva versión se entrega a M06. Reutiliza la consolidación de
:class:`ConsolidarCicloUseCase` (mismo cálculo y mismas verificaciones de R11).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError
from src.supplies.application.use_cases.provision_nic41.consolidar_ciclo_use_case import ConsolidarCicloUseCase
from src.supplies.domain.entities.provision_nic41 import ProvisionNic41
from src.supplies.domain.repositories.provision_nic41_repository import ProvisionNic41Repository
from src.supplies.domain.value_objects.motivo_correccion import MotivoCorreccion


class CorregirProvisionUseCase:
    def __init__(
        self, db: Session, provision_repo: ProvisionNic41Repository, consolidar: ConsolidarCicloUseCase
    ) -> None:
        self.db = db
        self.provision_repo = provision_repo
        self.consolidar = consolidar

    def execute(self, id_provision: int, motivo_correccion: str, usuario_actual: UsuarioActual) -> ProvisionNic41:
        original = self.provision_repo.obtener(id_provision)
        if original is None:
            raise NotFoundError(
                code="PROVISION_NO_ENCONTRADA",
                message=f"El reporte de provisión {id_provision} no existe.",
            )
        motivo = MotivoCorreccion(motivo_correccion)
        try:
            nueva = self.consolidar.consolidar_sin_commit(
                original.id_gestion_fases, usuario_actual.id_usuario, motivo_correccion=motivo.valor
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.consolidar.avisar_si_incompleto(nueva)
        return nueva
