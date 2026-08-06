"""Implementación SQLAlchemy de :class:`ConfiguracionBatchICARepository` (RF-74)."""
from __future__ import annotations

from datetime import time

from sqlalchemy.orm import Session

from src.supplies.domain.repositories.configuracion_batch_ica_repository import (
    ConfiguracionBatch,
    ConfiguracionBatchICARepository,
)
from src.supplies.infrastructure.models.configuracion_batch_ica_model import ConfiguracionBatchIcaModel

# Valores por defecto si la fila de configuración aún no existe.
_DEFAULTS = ConfiguracionBatch(
    limite_activos=5000,
    num_workers_max=4,
    umbral_paralelizacion=500,
    ventana_horas=4,
    hora_ejecucion=time(2, 0),
    max_reintentos=3,
    backoff_minutos=[2, 4, 6],
    es_activo=True,
)


class SqlAlchemyConfiguracionBatchICARepository(ConfiguracionBatchICARepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self) -> ConfiguracionBatch:
        orm = (
            self.db.query(ConfiguracionBatchIcaModel)
            .order_by(ConfiguracionBatchIcaModel.id_configuracion.asc())
            .first()
        )
        if orm is None:
            return _DEFAULTS
        return ConfiguracionBatch(
            limite_activos=orm.limite_activos,
            num_workers_max=orm.num_workers_max,
            umbral_paralelizacion=orm.umbral_paralelizacion,
            ventana_horas=orm.ventana_horas,
            hora_ejecucion=orm.hora_ejecucion,
            max_reintentos=orm.max_reintentos,
            backoff_minutos=list(orm.backoff_minutos or [2, 4, 6]),
            es_activo=orm.es_activo,
        )
