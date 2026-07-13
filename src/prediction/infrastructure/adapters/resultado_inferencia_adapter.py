from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.repositories.resultado_inferencia_port import ResultadoInferenciaPort
from src.prediction.infrastructure.models.resultado_inferencia_model import ResultadoInferenciaModel


class SqlAlchemyResultadoInferenciaAdapter(ResultadoInferenciaPort):
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener_por_id(self, id_resultado: uuid.UUID) -> Optional[dict]:
        orm = self._db.get(ResultadoInferenciaModel, id_resultado)
        if orm is None:
            return None
        return {
            "fecha_inferencia": orm.fecha_inferencia,
            "id_activo_biologico": orm.id_activo_biologico,
        }
