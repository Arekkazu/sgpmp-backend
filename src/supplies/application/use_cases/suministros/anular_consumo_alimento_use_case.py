# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-75: anular compensa el ledger de RF-78 |
"""Caso de uso: anular un registro de consumo de alimento VALIDADO (RF-75 pasos 10-13).

Un registro ANULADO no puede reactivarse ni volver a anularse. La justificación
debe tener al menos 20 caracteres (E6, 400). El costo que el consumo había
sumado al acumulado del ciclo (RF-78) se compensa en la misma transacción, así
el registro anulado queda fuera de todos los cálculos (postcondición 4). La
inmutabilidad de los campos de negocio la refuerza un trigger de la BD.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, NotFoundError
from src.supplies.application.use_cases.costeo_suministros.compensar_anulacion import CompensadorAnulacion
from src.supplies.domain.entities.consumo_alimento import ConsumoAlimento
from src.supplies.domain.repositories.consumo_alimento_repository import ConsumoAlimentoRepository
from src.supplies.domain.value_objects.estado_registro import EstadoRegistro
from src.supplies.domain.value_objects.justificacion_anulacion import MENSAJE_RF75, JustificacionAnulacion
from src.supplies.infrastructure.dto.anular_registro_dto import AnularRegistroDTO


class AnularConsumoAlimentoUseCase:
    """Anula un registro de consumo VALIDADO con justificación obligatoria."""

    def __init__(
        self, db: Session, consumo_repo: ConsumoAlimentoRepository, compensador: CompensadorAnulacion
    ) -> None:
        self.db = db
        self.consumo_repo = consumo_repo
        self.compensador = compensador

    def execute(
        self, id_consumo: int, dto: AnularRegistroDTO, usuario_actual: UsuarioActual
    ) -> ConsumoAlimento:
        consumo = self.consumo_repo.obtener_por_id(id_consumo)
        if consumo is None:
            raise NotFoundError(
                code="CONSUMO_NO_ENCONTRADO",
                message=f"El registro de consumo con ID {id_consumo} no existe.",
            )

        if consumo.estado_registro == EstadoRegistro.ANULADO.value:
            desde = (
                f" desde el {consumo.fecha_hora_anulacion.isoformat()}" if consumo.fecha_hora_anulacion else ""
            )
            raise ConflictError(
                code="CONSUMO_YA_ANULADO",
                message=(
                    f"El registro de consumo {id_consumo} ya se encuentra en estado ANULADO{desde}. "
                    "Un registro ANULADO no puede ser reactivado; si necesita reemplazarlo, cree un nuevo registro."
                ),
            )

        justificacion = JustificacionAnulacion(dto.justificacion_anulacion, MENSAJE_RF75)
        ledger = self.compensador.validar("ALIMENTO", id_consumo)
        consumo.anular(justificacion.valor, datetime.now(timezone.utc))

        try:
            anulado = self.consumo_repo.anular(consumo)
            if ledger is not None:
                self.compensador.compensar(
                    ledger,
                    f"Anulación del consumo {id_consumo} (RF-75): {justificacion.valor}",
                    usuario_actual.id_usuario,
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return anulado
