"""Caso de uso: Reactivar etapa inactiva del ciclo productivo (RF-16).

Sin esto una etapa desactivada quedaba bloqueada: no se puede editar
(``ETAPA_INACTIVA``) y su nombre sigue ocupado para la especie. Mismo patrón
que la reactivación de especies (RF-15); se audita como ``UPDATE`` porque el
CHECK de la auditoría solo admite CREATE, UPDATE y DEACTIVATE.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.ciclos.desactivar_ciclo_use_case import _snapshot
from src.configuration.domain.entities.ciclo_biologico import CicloBiologico
from src.configuration.domain.repositories.auditoria_ciclo_repository import AuditoriaCicloRepository
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class ReactivarCicloUseCase:
    """Restaura a activa una etapa previamente desactivada."""

    def __init__(
        self,
        db: Session,
        ciclos_repo: CicloBiologicoRepository,
        auditoria_repo: AuditoriaCicloRepository,
    ) -> None:
        self.db = db
        self.ciclos_repo = ciclos_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_ciclo_biologico: int, usuario_actual: UsuarioActual) -> CicloBiologico:
        ciclo = self.ciclos_repo.obtener_por_id(id_ciclo_biologico)
        if ciclo is None:
            raise NotFoundError(
                code="ETAPA_NO_ENCONTRADA",
                message=f"No existe una etapa con ID {id_ciclo_biologico}.",
            )
        if ciclo.es_activo:
            raise BusinessRuleError(
                code="ETAPA_YA_ACTIVA",
                message="La etapa ya se encuentra activa.",
            )

        snapshot_anterior = _snapshot(ciclo)
        ciclo.activar()
        ciclo.fecha_actualizacion = datetime.now(timezone.utc)

        try:
            ciclo_actualizado = self.ciclos_repo.actualizar(ciclo)
            self.auditoria_repo.registrar(
                id_ciclo_biologico=ciclo_actualizado.id_ciclo_biologico,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=_snapshot(ciclo_actualizado),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return ciclo_actualizado
