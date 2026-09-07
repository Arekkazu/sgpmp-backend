"""Caso de uso: Reactivar finca inactiva (Flujo E — RF-19).

Solo el Administrador puede reactivar. La operación se registra como
``UPDATE`` en la auditoría (``REACTIVATE`` no es un valor válido en el
CHECK constraint ``auditorias_fincas_tipo_operacion_check``).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.repositories.auditoria_finca_repository import AuditoriaFincaRepository
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class ReactivarFincaUseCase:

    def __init__(
        self,
        db: Session,
        finca_repo: FincaRepository,
        auditoria_repo: AuditoriaFincaRepository,
    ) -> None:
        self.db = db
        self.finca_repo = finca_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_finca: int, usuario_actual: UsuarioActual) -> Finca:
        finca = self.finca_repo.obtener_por_id(id_finca)
        if finca is None:
            raise NotFoundError(code="FINCA_NO_ENCONTRADA", message=f"No existe una finca con ID {id_finca}.")

        if finca.es_activo:
            raise BusinessRuleError(
                code="FINCA_YA_ACTIVA",
                message=f"La finca '{finca.nombre.valor}' ya se encuentra activa.",
            )

        snapshot_anterior = finca._snapshot()
        finca.activar()

        try:
            finca_actualizada = self.finca_repo.actualizar(finca)
            self.auditoria_repo.registrar(
                id_finca=finca_actualizada.id_finca,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_nuevos=finca_actualizada._snapshot(),
                valores_anteriores=snapshot_anterior,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return finca_actualizada
