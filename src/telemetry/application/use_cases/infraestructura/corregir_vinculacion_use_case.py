from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.shared.errors import BusinessRuleError, NotFoundError
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository
from src.telemetry.infrastructure.dto.corregir_vinculacion_dto import CorregirVinculacionDTO


class CorregirVinculacionUseCase:
    """RF-61-C: Corrección post-vinculación (inmutabilidad).
    Marca la vinculación original como CORREGIDA y crea una nueva con mecanismo=CORRECCION.
    """

    def __init__(
        self,
        db: Session,
        vinculacion_repo: VinculacionLecturaRepository,
    ) -> None:
        self.db = db
        self.vinculacion_repo = vinculacion_repo

    def execute(
        self, id_vinculacion_lectura: int, dto: CorregirVinculacionDTO, id_usuario: int
    ) -> VinculacionLectura:
        ahora = datetime.now(timezone.utc)
        try:
            original = self.vinculacion_repo.obtener_por_id(id_vinculacion_lectura)
            if original is None:
                raise NotFoundError(
                    code='VINCULACION_NO_ENCONTRADA',
                    message='Vinculación no encontrada.',
                )
            if original.estado_vinculacion == 'CORREGIDA':
                raise BusinessRuleError(
                    code='VINCULACION_YA_CORREGIDA',
                    message='La vinculación ya fue corregida previamente.',
                )

            # Marcar original como CORREGIDA
            original.estado_vinculacion = 'CORREGIDA'
            self.vinculacion_repo.actualizar(original)

            # Crear nueva vinculación como corrección
            nueva = self.vinculacion_repo.guardar(VinculacionLectura(
                id_vinculacion_lectura=None,
                id_telemetria=original.id_telemetria,
                modelo_manejo=dto.modelo_manejo,
                id_activo_biologico=dto.id_activo_biologico,
                id_infraestructura=original.id_infraestructura,
                fecha_inicio_vinculacion=original.fecha_inicio_vinculacion,
                fecha_fin_vinculacion=original.fecha_fin_vinculacion,
                mecanismo_vinculacion='CORRECCION',
                estado_vinculacion='VINCULADA',
                id_usuario=id_usuario,
                motivo_correccion=dto.motivo,
                id_vinculacion_reemplazada=original.id_vinculacion_lectura,
                fecha_creacion=ahora,
            ))

            self.db.commit()
            return nueva
        except Exception:
            self.db.rollback()
            raise
