"""Adapter de ``RecalibracionVisionPort``: calibración por visión automática en M09 (RF-24 v2.0, #551).

Corre en ``BackgroundTasks``, después de la respuesta de M02, con una sesión
propia del usuario de servicio (D1): la calibración es del Sistema, no del
usuario que registró el lote, y un fallo en M09 no afecta el alta ni el cierre.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import BackgroundTasks

from src.biological_assets.domain.repositories.recalibracion_vision_port import RecalibracionVisionPort
from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import CalibrarVisionUseCase
from src.configuration.infrastructure.adapters.observacion_vision_m03_adapter import ObservacionVisionM03Adapter
from src.configuration.infrastructure.repositories.calibracion_vision_repository import (
    SqlAlchemyCalibracionVisionRepository,
    SqlAlchemyLineaBaseVisionRepository,
)
from src.configuration.infrastructure.repositories.camara_area_repository import SqlAlchemyCamaraAreaRepository
from src.configuration.infrastructure.repositories.infraestructura_repository import (
    SqlAlchemyInfraestructuraRepository,
)
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.shared.database import id_usuario_servicio, sesion_sistema
from src.shared.errors import AppError

logger = logging.getLogger(__name__)


def _recalibrar_vision(id_infraestructura: int, momento: datetime, motivo: str) -> None:
    db = None
    try:
        db = sesion_sistema()
        CalibrarVisionUseCase(
            db=db,
            infraestructura_repo=SqlAlchemyInfraestructuraRepository(db),
            camara_repo=SqlAlchemyCamaraAreaRepository(db),
            observacion_port=ObservacionVisionM03Adapter(db),
            calibracion_repo=SqlAlchemyCalibracionVisionRepository(db),
            linea_base_repo=SqlAlchemyLineaBaseVisionRepository(db),
            eventos_repo=SqlAlchemyEventoRepository(db),
        ).execute_automatico(
            id_infraestructura,
            momento,
            id_usuario_auditoria=id_usuario_servicio(db),
            motivo_disparo=motivo,
        )
    except AppError as exc:
        # FALLIDA / NO_CONVERGIDA / VISION_NO_DISPONIBLE: ya quedó en historial y RF-10.
        logger.info("RF-24: calibración por visión automática del área %s: %s", id_infraestructura, exc.code)
    except Exception:
        logger.exception("RF-24: falló la calibración por visión automática del área %s", id_infraestructura)
    finally:
        if db is not None:
            db.close()


class RecalibracionVisionM09Adapter(RecalibracionVisionPort):

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    def solicitar(self, id_infraestructura: int, momento: datetime, motivo: str) -> None:
        self._background_tasks.add_task(_recalibrar_vision, id_infraestructura, momento, motivo)
