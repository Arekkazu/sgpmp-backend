"""Implementación SQLAlchemy de :class:`ConfiguracionBatchReporteGastoRepository` (RF-77)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.supplies.domain.repositories.configuracion_batch_reporte_gasto_repository import (
    ConfiguracionBatchReporteGasto,
    ConfiguracionBatchReporteGastoRepository,
)
from src.supplies.infrastructure.models.configuracion_batch_reporte_gasto_model import (
    ConfiguracionBatchReporteGastoModel,
)

_DEFAULTS = ConfiguracionBatchReporteGasto(
    num_workers_max=2,
    max_reintentos=3,
    backoff_minutos=[1, 3, 5],
    limite_concurrencia=5,
    intervalo_poll_segundos=15,
    es_activo=True,
)


class SqlAlchemyConfiguracionBatchReporteGastoRepository(ConfiguracionBatchReporteGastoRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self) -> ConfiguracionBatchReporteGasto:
        orm = (
            self.db.query(ConfiguracionBatchReporteGastoModel)
            .order_by(ConfiguracionBatchReporteGastoModel.id_configuracion.asc())
            .first()
        )
        if orm is None:
            return _DEFAULTS
        return ConfiguracionBatchReporteGasto(
            num_workers_max=orm.num_workers_max,
            max_reintentos=orm.max_reintentos,
            backoff_minutos=list(orm.backoff_minutos or [1, 3, 5]),
            limite_concurrencia=orm.limite_concurrencia,
            intervalo_poll_segundos=orm.intervalo_poll_segundos,
            es_activo=orm.es_activo,
        )
