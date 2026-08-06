"""Caso de uso: anular una aplicación de medicamento VALIDADA (RF-76).

Un registro ANULADO no puede volver a anularse (E8). La justificación exige al
menos 20 caracteres. La reversión del estado del activo a ACTIVO es
responsabilidad del scheduler de RF-44 (fuera del alcance de CU-01).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, NotFoundError
from src.supplies.domain.entities.medicamento import Medicamento
from src.supplies.domain.repositories.medicamento_repository import MedicamentoRepository
from src.supplies.domain.value_objects.estado_registro import EstadoRegistro
from src.supplies.domain.value_objects.justificacion_anulacion import JustificacionAnulacion
from src.supplies.infrastructure.dto.anular_registro_dto import AnularRegistroDTO


class AnularMedicamentoUseCase:
    """Anula una aplicación de medicamento VALIDADA con justificación obligatoria."""

    def __init__(self, db: Session, medicamento_repo: MedicamentoRepository) -> None:
        self.db = db
        self.medicamento_repo = medicamento_repo

    def execute(
        self, id_medicamento: int, dto: AnularRegistroDTO, usuario_actual: UsuarioActual
    ) -> Medicamento:
        medicamento = self.medicamento_repo.obtener_por_id(id_medicamento)
        if medicamento is None:
            raise NotFoundError(
                code="MEDICAMENTO_NO_ENCONTRADO",
                message=f"El registro de aplicación de medicamento con ID {id_medicamento} no existe.",
            )

        if medicamento.estado_registro == EstadoRegistro.ANULADO.value:
            raise ConflictError(
                code="MEDICAMENTO_YA_ANULADO",
                message=(
                    f"El registro de aplicación {id_medicamento} ya se encuentra en estado ANULADO. "
                    "No es posible anular un registro que ya fue anulado previamente."
                ),
            )

        justificacion = JustificacionAnulacion(dto.justificacion_anulacion)
        medicamento.anular(justificacion.valor, datetime.now(timezone.utc))

        try:
            anulado = self.medicamento_repo.anular(medicamento)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return anulado
