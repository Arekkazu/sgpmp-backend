"""Caso de uso: Desactivar patología por especie (Flujo G — RF-16).

Desactiva (baja lógica) la patología de esa especie. Bloqueado si el vínculo al
catálogo M04 tiene dependencias activas en eventos sanitarios o predicciones
(FA-04). Las patologías creadas por M09 (``id_patologia`` None) no tienen
dependencias M04 posibles.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.repositories.auditoria_patologia_repository import AuditoriaPatologiaRepository
from src.configuration.domain.repositories.dependencia_patologia_port import DependenciaPatologiaPort
from src.configuration.domain.repositories.especie_patologia_repository import EspeciePatologiaRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class DesactivarPatologiaUseCase:

    def __init__(
        self,
        db: Session,
        especie_patologia_repo: EspeciePatologiaRepository,
        auditoria_repo: AuditoriaPatologiaRepository,
        dependencia_port: DependenciaPatologiaPort,
    ) -> None:
        self.db = db
        self.especie_patologia_repo = especie_patologia_repo
        self.auditoria_repo = auditoria_repo
        self.dependencia_port = dependencia_port

    def execute(self, id_especies_patologias: int, usuario_actual: UsuarioActual) -> EspeciePatologia:
        entidad = self.especie_patologia_repo.obtener_por_id(id_especies_patologias)
        if entidad is None:
            raise NotFoundError(
                code="PATOLOGIA_NO_ENCONTRADA",
                message=f"No existe una patología con ID {id_especies_patologias}.",
            )
        if not entidad.es_activo:
            raise BusinessRuleError(
                code="PATOLOGIA_YA_INACTIVA",
                message="La patología ya se encuentra inactiva.",
            )
        if entidad.id_patologia is not None and self.dependencia_port.tiene_dependencias_activas(
            entidad.id_patologia
        ):
            raise BusinessRuleError(
                code="PATOLOGIA_CON_DEPENDENCIAS",
                message=f"La patología '{entidad.nombre.valor}' no puede ser desactivada porque "
                        "forma parte del historial clínico de uno o más activos.",
            )

        snapshot_anterior = entidad._snapshot()
        entidad.desactivar()
        entidad.fecha_actualizacion = datetime.now(timezone.utc)

        try:
            actualizada = self.especie_patologia_repo.actualizar(entidad)
            self.auditoria_repo.registrar(
                id_especies_patologias=actualizada.id_especies_patologias,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="DEACTIVATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=actualizada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return actualizada
