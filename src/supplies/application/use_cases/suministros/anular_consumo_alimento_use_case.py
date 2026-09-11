"""Caso de uso: anular un registro de consumo de alimento VALIDADO (RF-75).

Un registro ANULADO no puede reactivarse ni volver a anularse. La justificación
debe tener al menos 20 caracteres. La inmutabilidad de los campos de negocio la
refuerza un trigger de la BD.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, NotFoundError
from src.supplies.domain.entities.consumo_alimento import ConsumoAlimento
from src.supplies.domain.repositories.consumo_alimento_repository import ConsumoAlimentoRepository
from src.supplies.domain.value_objects.estado_registro import EstadoRegistro
from src.supplies.domain.value_objects.justificacion_anulacion import JustificacionAnulacion
from src.supplies.infrastructure.dto.anular_registro_dto import AnularRegistroDTO


class AnularConsumoAlimentoUseCase:
    """Anula un registro de consumo VALIDADO con justificación obligatoria."""

    def __init__(self, db: Session, consumo_repo: ConsumoAlimentoRepository) -> None:
        self.db = db
        self.consumo_repo = consumo_repo

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
            raise ConflictError(
                code="CONSUMO_YA_ANULADO",
                message=(
                    f"El registro de consumo {id_consumo} ya se encuentra en estado ANULADO. "
                    "Un registro anulado no puede reactivarse; cree un nuevo registro si es necesario."
                ),
            )

        justificacion = JustificacionAnulacion(dto.justificacion_anulacion)
        consumo.anular(justificacion.valor, datetime.now(timezone.utc))

        try:
            anulado = self.consumo_repo.anular(consumo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return anulado
