from __future__ import annotations

from sqlalchemy.orm import Session

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository
from src.telemetry.infrastructure.dto.resolver_vinculacion_dto import ResolverVinculacionDTO


class ResolverVinculacionUseCase:
    """RF-61-C: Resolución manual de una vinculación AMBIGUA por parte del Ingeniero de Campo."""

    def __init__(
        self,
        db: Session,
        vinculacion_repo: VinculacionLecturaRepository,
    ) -> None:
        self.db = db
        self.vinculacion_repo = vinculacion_repo

    def execute(
        self, id_vinculacion_lectura: int, dto: ResolverVinculacionDTO, id_usuario: int
    ) -> VinculacionLectura:
        try:
            vinculacion = self.vinculacion_repo.obtener_por_id(id_vinculacion_lectura)
            if vinculacion is None:
                raise NotFoundError(
                    code='VINCULACION_NO_ENCONTRADA',
                    message='Vinculación no encontrada.',
                )
            vinculacion.resolver(
                id_activo_biologico=dto.id_activo_biologico,
                id_usuario=id_usuario,
            )
            vinculacion.modelo_manejo = dto.modelo_manejo
            resultado = self.vinculacion_repo.actualizar(vinculacion)
            self.db.commit()
            return resultado
        except Exception:
            self.db.rollback()
            raise
