from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository
from src.telemetry.infrastructure.dto.resolver_vinculacion_dto import ResolverVinculacionDTO

logger = logging.getLogger(__name__)


class ResolverVinculacionUseCase:
    """RF-61-C: Resolución manual de una vinculación AMBIGUA por parte del Ingeniero de Campo."""

    def __init__(
        self,
        db: Session,
        vinculacion_repo: VinculacionLecturaRepository,
        reclasificar_semaforo_use_case: Optional[object] = None,
    ) -> None:
        self.db = db
        self.vinculacion_repo = vinculacion_repo
        self.reclasificar_semaforo_use_case = reclasificar_semaforo_use_case

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
        except Exception:
            self.db.rollback()
            raise

        # INC-M09-106-G31: reclasificar el semáforo contra RF-17 (best-effort, fuera de la transacción)
        if self.reclasificar_semaforo_use_case is not None and resultado.id_activo_biologico:
            try:
                self.reclasificar_semaforo_use_case.execute(
                    id_telemetria=resultado.id_telemetria,
                    id_activo_biologico=resultado.id_activo_biologico,
                )
            except Exception:
                logger.warning(
                    'INC-M09-106-G31: fallo al reclasificar semáforo para vinculación %s.',
                    id_vinculacion_lectura,
                    exc_info=True,
                )

        return resultado
