from __future__ import annotations

from sqlalchemy.orm import Session

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.repositories.alerta_repository import AlertaRepository
from src.telemetry.domain.repositories.historico_estado_alerta_repository import HistoricoEstadoAlertaRepository
from src.telemetry.infrastructure.dto.actualizar_estado_alerta_dto import ActualizarEstadoAlertaDTO


class ActualizarEstadoAlertaUseCase:

    def __init__(
        self,
        db: Session,
        alerta_repo: AlertaRepository,
        historico_repo: HistoricoEstadoAlertaRepository,
    ) -> None:
        self.db = db
        self.alerta_repo = alerta_repo
        self.historico_repo = historico_repo

    def execute(self, id_alerta: int, dto: ActualizarEstadoAlertaDTO, id_usuario: int) -> Alerta:
        alerta = self.alerta_repo.obtener_por_id(id_alerta)
        if alerta is None:
            raise NotFoundError(code="ALERTA_NO_ENCONTRADA", message=f"Alerta {id_alerta} no encontrada.")

        estado_anterior = alerta.estado_alerta
        alerta.transicionar(dto.nuevo_estado, id_usuario, dto.motivo)

        try:
            alerta_actualizada = self.alerta_repo.actualizar_estado(
                id_alerta=id_alerta,
                nuevo_estado=alerta.estado_alerta,
                id_usuario=id_usuario,
                motivo=dto.motivo,
                fecha_atencion=alerta.fecha_atencion,
                fecha_resolucion=alerta.fecha_resolucion,
            )
            self.historico_repo.registrar(
                id_alerta=id_alerta,
                estado_anterior=estado_anterior,
                estado_nuevo=alerta.estado_alerta,
                id_usuario=id_usuario,
                motivo=dto.motivo,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return alerta_actualizada
