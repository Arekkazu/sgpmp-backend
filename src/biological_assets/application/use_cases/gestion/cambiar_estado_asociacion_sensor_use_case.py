from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import AsociacionSensorActivo
from src.biological_assets.domain.repositories.asociacion_sensor_activo_repository import (
    AsociacionSensorActivoRepository,
)
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError

if TYPE_CHECKING:
    from src.identity_access.infrastructure.dependencies import UsuarioActual
    from src.biological_assets.infrastructure.dto.cambiar_estado_asociacion_sensor_dto import (
        CambiarEstadoAsociacionSensorDTO,
    )

# RF-49: transiciones manuales permitidas del ciclo de vida de una asociacion.
# SUPERADA es terminal y solo la asigna AsociarSensorActivoUseCase al reemplazar
# una asociacion -- ningun estado puede transicionar a SUPERADA por este endpoint.
_TRANSICIONES_VALIDAS: dict[str, set[str]] = {
    'ACTIVA': {'INACTIVA'},
    'INACTIVA': {'ACTIVA'},
    'SUPERADA': set(),
}


class CambiarEstadoAsociacionSensorUseCase:

    def __init__(self, db: Session, repo: AsociacionSensorActivoRepository) -> None:
        self.db = db
        self.repo = repo

    def execute(
        self,
        id_activo: int,
        id_asociacion: int,
        dto: CambiarEstadoAsociacionSensorDTO,
        usuario_actual: UsuarioActual,
    ) -> AsociacionSensorActivo:
        asociacion = self.repo.obtener_por_id(id_asociacion)
        if asociacion is None or asociacion.id_activo_biologico != id_activo:
            raise NotFoundError(
                code='ASOCIACION_NO_ENCONTRADA',
                message=f'No existe una asociación con id {id_asociacion} para el activo {id_activo}.',
            )

        estado_actual = asociacion.estado_asociacion
        estado_nuevo = dto.estado_nuevo

        if estado_actual == estado_nuevo:
            raise ConflictError(
                code='ESTADO_REDUNDANTE',
                message=f'La asociación ya se encuentra en estado {estado_nuevo}.',
            )

        permitidas = _TRANSICIONES_VALIDAS.get(estado_actual, set())
        if estado_nuevo not in permitidas:
            raise BusinessRuleError(
                code='TRANSICION_INVALIDA',
                message=(
                    f'La transición {estado_actual} → {estado_nuevo} no está permitida. '
                    f'Transiciones válidas desde {estado_actual}: {", ".join(sorted(permitidas)) or "ninguna"}.'
                ),
            )

        snapshot_anterior = {
            'estado_asociacion': asociacion.estado_asociacion,
            'fecha_fin': asociacion.fecha_fin.isoformat() if asociacion.fecha_fin else None,
            'motivo': asociacion.motivo,
        }

        asociacion.estado_asociacion = estado_nuevo
        asociacion.motivo = dto.motivo
        if estado_nuevo == 'INACTIVA':
            asociacion.fecha_fin = datetime.datetime.now(datetime.timezone.utc)
        elif estado_nuevo == 'ACTIVA':
            asociacion.fecha_fin = None

        try:
            asociacion = self.repo.actualizar_estado(asociacion)
            self.repo.registrar_auditoria(
                id_asociacion=asociacion.id_asociacion_activo_sensor,
                id_usuario=usuario_actual.id_usuario,
                tipo_op='UPDATE',
                valores_anteriores=snapshot_anterior,
                valores_nuevos={
                    'estado_asociacion': asociacion.estado_asociacion,
                    'fecha_fin': asociacion.fecha_fin.isoformat() if asociacion.fecha_fin else None,
                    'motivo': asociacion.motivo,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return asociacion
