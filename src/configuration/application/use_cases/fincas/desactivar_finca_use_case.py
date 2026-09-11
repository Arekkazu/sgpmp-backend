"""Caso de uso: Desactivar finca (PATCH /desactivar RF-19 FA-04)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.repositories.auditoria_finca_repository import AuditoriaFincaRepository
from src.configuration.domain.repositories.finca_dependency_port import FincaDependencyPort
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class DesactivarFincaUseCase:

    def __init__(
        self,
        db: Session,
        finca_repo: FincaRepository,
        auditoria_repo: AuditoriaFincaRepository,
        dependency_port: FincaDependencyPort,
    ) -> None:
        self.db = db
        self.finca_repo = finca_repo
        self.auditoria_repo = auditoria_repo
        self.dependency_port = dependency_port

    def execute(self, id_finca: int, usuario_actual: UsuarioActual) -> Finca:
        finca = self.finca_repo.obtener_por_id(id_finca)
        if finca is None:
            raise NotFoundError(code="FINCA_NO_ENCONTRADA", message=f"No existe una finca con ID {id_finca}.")

        if not finca.es_activo:
            raise BusinessRuleError(
                code="FINCA_YA_INACTIVA",
                message=f"La finca '{finca.nombre.valor}' ya se encuentra inactiva.",
            )

        if self.dependency_port.tiene_dependencias_activas(id_finca):
            raise BusinessRuleError(
                code="FINCA_CON_DEPENDENCIAS",
                message=(
                    f"No se puede desactivar la finca '{finca.nombre.valor}' porque aún cuenta con "
                    "infraestructura o activos biológicos asociados. "
                    "Debe reubicarlos o darlos de baja antes de desactivar la unidad productiva."
                ),
            )

        snapshot_anterior = finca._snapshot()
        finca.desactivar()

        try:
            finca_actualizada = self.finca_repo.actualizar(finca)
            self.auditoria_repo.registrar(
                id_finca=finca_actualizada.id_finca,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="DEACTIVATE",
                valores_nuevos=finca_actualizada._snapshot(),
                valores_anteriores=snapshot_anterior,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return finca_actualizada
