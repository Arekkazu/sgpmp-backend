# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ampliación de ventana por resultado  |
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.prediction.domain.entities.ampliacion_ventana_retroalimentacion import AmpliacionVentanaRetroalimentacion
from src.prediction.domain.repositories.ampliacion_ventana_retroalimentacion_repository import (
    AmpliacionVentanaRetroalimentacionRepository,
)
from src.prediction.infrastructure.models.ampliacion_ventana_retroalimentacion_model import (
    AmpliacionVentanaRetroalimentacionModel,
)
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyAmpliacionVentanaRetroalimentacionRepository(AmpliacionVentanaRetroalimentacionRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def guardar(self, entidad: AmpliacionVentanaRetroalimentacion) -> AmpliacionVentanaRetroalimentacion:
        try:
            orm = AmpliacionVentanaRetroalimentacionModel(
                id_resultado_inferencia=entidad.id_resultado_inferencia,
                fecha_limite=entidad.fecha_limite,
                justificacion=entidad.justificacion,
                id_usuario_autorizador=entidad.id_usuario_autorizador,
            )
            self._db.add(orm)
            self._db.flush()
            entidad.id_ampliacion_ventana_retroalimentacion = orm.id_ampliacion_ventana_retroalimentacion
            entidad.fecha_creacion = orm.fecha_creacion
            return entidad
        except Exception as exc:
            raise_from_db_error(exc)

    def fecha_limite_vigente(self, id_resultado: uuid.UUID) -> Optional[datetime]:
        m = AmpliacionVentanaRetroalimentacionModel
        return self._db.execute(
            select(func.max(m.fecha_limite)).where(m.id_resultado_inferencia == id_resultado)
        ).scalar()
