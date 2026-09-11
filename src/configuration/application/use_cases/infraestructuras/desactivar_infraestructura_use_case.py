"""Caso de uso: Desactivar área productiva (PATCH /desactivar RF-20 FA-04)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.auditoria_infraestructura_repository import AuditoriaInfraestructuraRepository
from src.configuration.domain.repositories.infraestructura_dependency_port import InfraestructuraDependencyPort
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class DesactivarInfraestructuraUseCase:

    def __init__(
        self,
        db: Session,
        infra_repo: InfraestructuraRepository,
        auditoria_repo: AuditoriaInfraestructuraRepository,
        dependency_port: InfraestructuraDependencyPort,
    ) -> None:
        self.db = db
        self.infra_repo = infra_repo
        self.auditoria_repo = auditoria_repo
        self.dependency_port = dependency_port

    def execute(self, id_infraestructura: int, usuario_actual: UsuarioActual) -> Infraestructura:
        infra = self.infra_repo.obtener_por_id(id_infraestructura)
        if infra is None:
            raise NotFoundError(
                code="INFRAESTRUCTURA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {id_infraestructura}.",
            )

        if not infra.es_activo:
            raise BusinessRuleError(
                code="INFRAESTRUCTURA_YA_INACTIVA",
                message=f"El área '{infra.nombre.valor}' ya se encuentra inactiva.",
            )

        if self.dependency_port.tiene_dependencias_activas(id_infraestructura):
            raise BusinessRuleError(
                code="INFRAESTRUCTURA_CON_DEPENDENCIAS",
                message=(
                    f"El área '{infra.nombre.valor}' tiene dispositivos y/o activos biológicos asociados. "
                    "Debe desvincular o trasladar los recursos antes de desactivar la infraestructura."
                ),
            )

        snapshot_anterior = infra._snapshot()
        infra.desactivar()

        try:
            infra_actualizada = self.infra_repo.actualizar(infra)
            self.auditoria_repo.registrar(
                id_infraestructura=infra_actualizada.id_infraestructura,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="DEACTIVATE",
                valores_nuevos=infra_actualizada._snapshot(),
                valores_anteriores=snapshot_anterior,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return infra_actualizada
