"""Caso de uso: Reactivar área productiva inactiva (PATCH /reactivar RF-20 v1.1).

Análogo a RF-19 (fincas) y RF-15 (especies): solo el Administrador, y se audita
como ``UPDATE`` porque ``REACTIVATE`` no es un tipo de operación del historial.
Un área no puede volver a operar sobre una finca inactiva.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.auditoria_infraestructura_repository import AuditoriaInfraestructuraRepository
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class ReactivarInfraestructuraUseCase:
    """Reactiva un área inactiva cuya finca esté activa."""

    def __init__(
        self,
        db: Session,
        infra_repo: InfraestructuraRepository,
        finca_repo: FincaRepository,
        auditoria_repo: AuditoriaInfraestructuraRepository,
    ) -> None:
        self.db = db
        self.infra_repo = infra_repo
        self.finca_repo = finca_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_infraestructura: int, usuario_actual: UsuarioActual) -> Infraestructura:
        infra = self.infra_repo.obtener_por_id(id_infraestructura)
        if infra is None:
            raise NotFoundError(
                code="INFRAESTRUCTURA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {id_infraestructura}.",
            )
        if infra.es_activo:
            raise BusinessRuleError(
                code="INFRAESTRUCTURA_YA_ACTIVA",
                message=f"El área '{infra.nombre.valor}' ya se encuentra activa.",
            )

        finca = self.finca_repo.obtener_por_id(infra.id_finca)
        if finca is None or not finca.es_activo:
            raise BusinessRuleError(
                code="FINCA_INACTIVA_O_INEXISTENTE",
                message=(
                    "No es posible reactivar el área productiva porque la finca asociada "
                    "no existe o se encuentra inactiva."
                ),
            )

        snapshot_anterior = infra._snapshot()
        infra.activar()

        try:
            infra_actualizada = self.infra_repo.actualizar(infra)
            self.auditoria_repo.registrar(
                id_infraestructura=infra_actualizada.id_infraestructura,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_nuevos=infra_actualizada._snapshot(),
                valores_anteriores=snapshot_anterior,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return infra_actualizada
