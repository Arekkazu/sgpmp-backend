"""Caso de uso: Desactivar etapa del ciclo productivo (Flujo C — RF-16).

Bloquea la desactivación si existen activos biológicos en la etapa (FA-03).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.ciclo_biologico import CicloBiologico
from src.configuration.domain.repositories.auditoria_ciclo_repository import AuditoriaCicloRepository
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.configuration.domain.repositories.dependencia_ciclo_port import DependenciaCicloPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


def _snapshot(ciclo: CicloBiologico) -> dict:
    return {
        "id_ciclo_biologico": ciclo.id_ciclo_biologico,
        "nombre": ciclo.nombre.valor,
        "descripcion": ciclo.descripcion,
        "duracion_dias": ciclo.duracion_dias.valor,
        "id_especie": ciclo.id_especie,
        "es_activo": ciclo.es_activo,
        "fecha_actualizacion": ciclo.fecha_actualizacion.isoformat() if ciclo.fecha_actualizacion else None,
    }


class DesactivarCicloUseCase:

    def __init__(
        self,
        db: Session,
        ciclos_repo: CicloBiologicoRepository,
        auditoria_repo: AuditoriaCicloRepository,
        dependencia_port: DependenciaCicloPort,
    ) -> None:
        self.db = db
        self.ciclos_repo = ciclos_repo
        self.auditoria_repo = auditoria_repo
        self.dependencia_port = dependencia_port

    def execute(self, id_ciclo_biologico: int, usuario_actual: UsuarioActual) -> CicloBiologico:
        ciclo = self.ciclos_repo.obtener_por_id(id_ciclo_biologico)
        if ciclo is None:
            raise NotFoundError(
                code="ETAPA_NO_ENCONTRADA",
                message=f"No existe una etapa con ID {id_ciclo_biologico}.",
            )
        if not ciclo.es_activo:
            raise BusinessRuleError(
                code="ETAPA_YA_INACTIVA",
                message="La etapa ya se encuentra inactiva.",
            )
        if self.dependencia_port.tiene_dependencias_activas(id_ciclo_biologico):
            raise BusinessRuleError(
                code="ETAPA_CON_ACTIVOS",
                message=f"No es posible desactivar la etapa '{ciclo.nombre.valor}'. "
                        "Existen activos biológicos actualmente en esta fase del ciclo. "
                        "Debe trasladarlos de etapa antes de proceder.",
            )

        snapshot_anterior = _snapshot(ciclo)
        ciclo.desactivar()
        ciclo.fecha_actualizacion = datetime.now(timezone.utc)

        try:
            ciclo_actualizado = self.ciclos_repo.actualizar(ciclo)
            self.auditoria_repo.registrar(
                id_ciclo_biologico=ciclo_actualizado.id_ciclo_biologico,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="DEACTIVATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=_snapshot(ciclo_actualizado),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return ciclo_actualizado
