from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

import src.biological_assets.infrastructure.models  # noqa: F401

from src.biological_assets.domain.entities.activo_biologico import HistoricoEstado
from src.biological_assets.domain.repositories.historico_estado_repository import HistoricoEstadoRepository
from src.biological_assets.infrastructure.models.historico_estado_activo_model import HistoricoEstadoActivoModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyHistoricoEstadoRepository(HistoricoEstadoRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        id_activo: int,
        id_estado_anterior: int,
        id_estado_nuevo: int,
        fecha: datetime,
        motivo: Optional[str],
        usuario_id: int,
        modulo_origen: str,
    ) -> HistoricoEstado:
        try:
            self.db.execute(text('SET LOCAL app.usuario_id = :uid'), {'uid': usuario_id})
            orm = HistoricoEstadoActivoModel(
                id_activo_biologico=id_activo,
                id_estado_anterior=id_estado_anterior,
                id_estado_nuevo=id_estado_nuevo,
                fecha_cambio=fecha,
                motivo_cambio=motivo,
                modulo_origen=modulo_origen,
                id_usuario=usuario_id,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return HistoricoEstado(
            id_historico=orm.id_historico_estado_activo,
            id_activo_biologico=orm.id_activo_biologico,
            id_estado_anterior=orm.id_estado_anterior,
            id_estado_nuevo=orm.id_estado_nuevo,
            fecha_cambio=orm.fecha_cambio,
            motivo_cambio=orm.motivo_cambio,
            modulo_origen=orm.modulo_origen,
            id_usuario=orm.id_usuario,
        )
