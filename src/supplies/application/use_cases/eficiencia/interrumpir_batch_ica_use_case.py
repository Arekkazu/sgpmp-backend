# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | INC-M05-511 RF-74: al arrancar se interrumpen las corridas del batch ICA que quedaron huérfanas |
# | 2026-11-12 | Leandro | INC-M05-350/351-G05 RF-74: separar causa y motivo y emitir un aviso tras confirmar el corte. |
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
from src.supplies.domain.repositories.notificacion_suministros_port import NotificacionSuministrosPort
from src.supplies.domain.value_objects.eficiencia_enums import CausaInterrupcionBatch


class InterrumpirBatchICAUseCase:
    def __init__(
        self, db: Session, ejecucion_repo: EjecucionBatchICARepository,
        notificador: Optional[NotificacionSuministrosPort] = None,
    ) -> None:
        self.db = db
        self.ejecucion_repo = ejecucion_repo
        self.notificador = notificador

    def execute(
        self, id_ejecucion: int, id_usuario: Optional[int], motivo: Optional[str] = None
    ) -> EjecucionBatchICA:
        ejecucion = self._interrumpir(id_ejecucion, CausaInterrupcionBatch.MANUAL, id_usuario, motivo)
        if self.notificador is not None:
            self.notificador.a_roles(
                ("Administrador", "Productor"),
                "BATCH_ICA_INTERRUMPIDO",
                "El proceso batch de cálculo de CA fue interrumpido manualmente. "
                "El procesamiento pendiente puede retomarse en la siguiente ejecución.",
                {"id_ejecucion": id_ejecucion, "causa_interrupcion": ejecucion.causa_interrupcion},
            )
        return ejecucion

    def _interrumpir(
        self, id_ejecucion: int, causa: CausaInterrupcionBatch,
        id_usuario: Optional[int] = None, motivo: Optional[str] = None,
    ) -> EjecucionBatchICA:
        try:
            ejecucion = self.ejecucion_repo.obtener(id_ejecucion, para_actualizar=True)
            if ejecucion is None:
                raise NotFoundError(
                    code="EJECUCION_NO_ENCONTRADA",
                    message=f"La ejecución de batch ICA con ID {id_ejecucion} no existe.",
                    field="id_ejecucion",
                )
            ejecucion.interrumpir(
                causa=causa.value,
                hora_corte=datetime.now(timezone.utc),
                id_usuario=id_usuario,
                motivo=motivo,
            )
            self.ejecucion_repo.guardar(ejecucion)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return ejecucion

    def interrumpir_huerfanas(self) -> list[int]:
        """Al arrancar el proceso no queda ningún worker vivo: una corrida ``EN_EJECUCION``
        quedó huérfana por un reinicio y bloquearía todas las siguientes con ``BATCH_EN_CURSO``.
        Hay un solo proceso por ambiente, así que todas las que encuentre son huérfanas."""
        ids: list[int] = []
        while (ejecucion := self.ejecucion_repo.obtener_en_ejecucion()) is not None:
            self._interrumpir(ejecucion.id_ejecucion, CausaInterrupcionBatch.REINICIO_SERVIDOR)
            ids.append(ejecucion.id_ejecucion)
        return ids
