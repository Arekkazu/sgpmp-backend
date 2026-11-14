# | Fecha      | Nombre   | Que se hizo                                             |
# |------------|----------|---------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-228-G068 RF-72: informa si el activo está en BAJA |
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo

from src.prediction.domain.repositories.resultado_inferencia_port import ResultadoInferenciaPort
from src.prediction.infrastructure.models.resultado_inferencia_model import ResultadoInferenciaModel


class SqlAlchemyResultadoInferenciaAdapter(ResultadoInferenciaPort):
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener_por_id(self, id_resultado: uuid.UUID) -> Optional[dict]:
        orm = self._db.get(ResultadoInferenciaModel, id_resultado)
        if orm is None:
            return None
        id_estado = self._db.execute(
            text("SELECT id_estado FROM modulo2.activos_biologicos WHERE id_activo_biologico = :id"),
            {"id": orm.id_activo_biologico},
        ).scalar()
        return {
            "fecha_inferencia": orm.fecha_inferencia,
            "id_activo_biologico": orm.id_activo_biologico,
            # Estado vigente del activo (RF-72: debe existir y ser válido), no el de la inferencia.
            "activo_en_baja": id_estado == EstadoActivo.BAJA,
        }
