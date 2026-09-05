from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.historico_transicion_dispositivo import HistoricoTransicionDispositivo
from src.telemetry.domain.repositories.historico_transicion_dispositivo_repository import HistoricoTransicionDispositivoRepository
from src.telemetry.infrastructure.models.historico_transicion_dispositivo_model import HistoricoTransicionDispositivoModel


class SqlAlchemyHistoricoTransicionDispositivoRepository(HistoricoTransicionDispositivoRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(self, transicion: HistoricoTransicionDispositivo) -> HistoricoTransicionDispositivo:
        try:
            orm = HistoricoTransicionDispositivoModel(
                id_dispositivo_iot=transicion.id_dispositivo_iot,
                estado_anterior=transicion.estado_anterior,
                estado_nuevo=transicion.estado_nuevo,
                causa_primaria=transicion.causa_primaria,
                causa_secundar=transicion.causa_secundaria,
                id_usuairo_responsable=transicion.id_usuario_responsable,
                notas=transicion.notas,
                fecha_transicion=transicion.fecha_transicion,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar_por_dispositivo(
        self, id_dispositivo_iot: int, limite: int = 20
    ) -> List[HistoricoTransicionDispositivo]:
        rows = self.db.execute(
            select(HistoricoTransicionDispositivoModel)
            .where(HistoricoTransicionDispositivoModel.id_dispositivo_iot == id_dispositivo_iot)
            .order_by(HistoricoTransicionDispositivoModel.fecha_transicion.desc())
            .limit(limite)
        ).scalars().all()
        return [self._a_entidad(r) for r in rows]

    @staticmethod
    def _a_entidad(orm: HistoricoTransicionDispositivoModel) -> HistoricoTransicionDispositivo:
        return HistoricoTransicionDispositivo(
            id_transaccion=orm.id_transaccion,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            estado_anterior=orm.estado_anterior,
            estado_nuevo=orm.estado_nuevo,
            causa_primaria=orm.causa_primaria,
            causa_secundaria=orm.causa_secundar,
            id_usuario_responsable=orm.id_usuairo_responsable,
            notas=orm.notas,
            fecha_transicion=orm.fecha_transicion,
        )
