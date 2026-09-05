"""Caso de uso: Desactivar umbral ambiental (Flujo D — RF-17)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental
from src.configuration.domain.repositories.auditoria_umbral_repository import AuditoriaUmbralRepository
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class DesactivarUmbralUseCase:

    def __init__(
        self,
        db: Session,
        umbral_repo: UmbralAmbientalRepository,
        auditoria_repo: AuditoriaUmbralRepository,
    ) -> None:
        self.db = db
        self.umbral_repo = umbral_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_umbral_ambiental: int, usuario_actual: UsuarioActual) -> UmbralAmbiental:
        umbral = self.umbral_repo.obtener_por_id(id_umbral_ambiental)
        if umbral is None:
            raise NotFoundError(
                code='UMBRAL_NO_ENCONTRADO',
                message=f"No existe un umbral ambiental con ID {id_umbral_ambiental}.",
            )
        if not umbral.es_activo:
            raise BusinessRuleError(
                code='UMBRAL_YA_INACTIVO',
                message="El umbral ambiental ya se encuentra inactivo.",
            )

        snapshot = umbral._snapshot()
        umbral.desactivar()

        try:
            umbral_actualizado = self.umbral_repo.actualizar(umbral)
            self.auditoria_repo.registrar(
                id_umbral_ambiental=umbral_actualizado.id_umbral_ambiental,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion='DEACTIVATE',
                valores_anteriores=snapshot,
                valores_nuevos=umbral_actualizado._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return umbral_actualizado
