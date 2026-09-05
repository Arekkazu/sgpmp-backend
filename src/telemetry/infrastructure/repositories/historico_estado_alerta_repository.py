from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.alerta import HistoricoEstadoAlerta
from src.telemetry.domain.repositories.historico_estado_alerta_repository import HistoricoEstadoAlertaRepository
from src.telemetry.infrastructure.models.historico_estado_alerta_model import HistoricoEstadoAlertaModel


class SqlAlchemyHistoricoEstadoAlertaRepository(HistoricoEstadoAlertaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        id_alerta: int,
        estado_anterior: str,
        estado_nuevo: str,
        id_usuario: Optional[int] = None,
        motivo: Optional[str] = None,
    ) -> None:
        try:
            orm = HistoricoEstadoAlertaModel(
                id_alerta=id_alerta,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_nuevo,
                id_usuario=id_usuario,
                motivo=motivo,
                fecha_cambio=datetime.now(timezone.utc),
            )
            self.db.add(orm)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_por_alerta(self, id_alerta: int) -> list[HistoricoEstadoAlerta]:
        orms = (
            self.db.query(HistoricoEstadoAlertaModel)
            .filter(HistoricoEstadoAlertaModel.id_alerta == id_alerta)
            .order_by(HistoricoEstadoAlertaModel.fecha_cambio.asc())
            .all()
        )
        return [self._a_entidad(o) for o in orms]

    @staticmethod
    def _a_entidad(orm: HistoricoEstadoAlertaModel) -> HistoricoEstadoAlerta:
        return HistoricoEstadoAlerta(
            id_historico_estado_alerta=orm.id_historico_estado_alerta,
            id_alerta=orm.id_alerta,
            estado_anterior=orm.estado_anterior,
            estado_nuevo=orm.estado_nuevo,
            id_usuario=orm.id_usuario,
            motivo=orm.motivo,
            fecha_cambio=orm.fecha_cambio,
        )
