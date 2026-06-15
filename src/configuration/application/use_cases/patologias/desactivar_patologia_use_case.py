"""Caso de uso: Desactivar patología del catálogo (Flujo G — RF-16).

Desactiva la patología globalmente. Bloqueado si tiene dependencias activas
en eventos sanitarios o predicciones de M04 (FA-04).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.patologia import Patologia
from src.configuration.domain.repositories.auditoria_patologia_repository import AuditoriaPatologiaRepository
from src.configuration.domain.repositories.dependencia_patologia_port import DependenciaPatologiaPort
from src.configuration.domain.repositories.patologia_repository import PatologiaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


def _snapshot(patologia: Patologia) -> dict:
    return {
        "id_patologia": patologia.id_patologia,
        "nombre": patologia.nombre.valor,
        "descripcion": patologia.descripcion,
        "es_activo": patologia.es_activo,
        "fecha_actualizacion": patologia.fecha_actualizacion.isoformat() if patologia.fecha_actualizacion else None,
    }


class DesactivarPatologiaUseCase:

    def __init__(
        self,
        db: Session,
        patologias_repo: PatologiaRepository,
        auditoria_repo: AuditoriaPatologiaRepository,
        dependencia_port: DependenciaPatologiaPort,
    ) -> None:
        self.db = db
        self.patologias_repo = patologias_repo
        self.auditoria_repo = auditoria_repo
        self.dependencia_port = dependencia_port

    def execute(self, id_patologia: int, usuario_actual: UsuarioActual) -> Patologia:
        patologia = self.patologias_repo.obtener_por_id(id_patologia)
        if patologia is None:
            raise NotFoundError(
                code="PATOLOGIA_NO_ENCONTRADA",
                message=f"No existe una patología con ID {id_patologia}.",
            )
        if not patologia.es_activo:
            raise BusinessRuleError(
                code="PATOLOGIA_YA_INACTIVA",
                message="La patología ya se encuentra inactiva.",
            )
        if self.dependencia_port.tiene_dependencias_activas(id_patologia):
            raise BusinessRuleError(
                code="PATOLOGIA_CON_DEPENDENCIAS",
                message=f"La patología '{patologia.nombre.valor}' no puede ser desactivada porque "
                        "forma parte del historial clínico de uno o más activos.",
            )

        snapshot_anterior = _snapshot(patologia)
        patologia.desactivar()
        patologia.fecha_actualizacion = datetime.now(timezone.utc)

        try:
            patologia_actualizada = self.patologias_repo.actualizar(patologia)
            self.auditoria_repo.registrar(
                id_patologia=patologia_actualizada.id_patologia,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="DEACTIVATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=_snapshot(patologia_actualizada),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return patologia_actualizada
