"""Caso de uso: interrumpir una corrida del batch ICA en curso (RF-74, FA-12).

Marca la ejecución ``INTERRUMPIDO`` y preserva la cola. Los workers de la corrida en
vuelo detectan el cambio de estado de forma cooperativa y encolan sus pendientes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import NotFoundError
from src.supplies.domain.entities.ejecucion_batch_ica import EjecucionBatchICA
from src.supplies.domain.repositories.ejecucion_batch_ica_repository import EjecucionBatchICARepository
from src.supplies.domain.value_objects.eficiencia_enums import CausaInterrupcionBatch


class InterrumpirBatchICAUseCase:
    def __init__(self, db: Session, ejecucion_repo: EjecucionBatchICARepository) -> None:
        self.db = db
        self.ejecucion_repo = ejecucion_repo

    def execute(
        self, id_ejecucion: int, id_usuario: Optional[int], motivo: Optional[str] = None
    ) -> EjecucionBatchICA:
        ejecucion = self.ejecucion_repo.obtener(id_ejecucion)
        if ejecucion is None:
            raise NotFoundError(
                code="EJECUCION_NO_ENCONTRADA",
                message=f"La ejecución de batch ICA con ID {id_ejecucion} no existe.",
                field="id_ejecucion",
            )
        try:
            # Lanza FlowError si la corrida ya no está EN_EJECUCION.
            ejecucion.interrumpir(
                causa=motivo or CausaInterrupcionBatch.MANUAL.value,
                hora_corte=datetime.now(timezone.utc),
                id_usuario=id_usuario,
            )
            self.ejecucion_repo.guardar(ejecucion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return ejecucion
