"""Implementación SQLAlchemy de :class:`ConfiguracionBatchHistorialRepository` (RF-81)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.supplies.domain.repositories.configuracion_batch_historial_repository import (
    ConfiguracionBatchHistorial,
    ConfiguracionBatchHistorialRepository,
)
from src.supplies.infrastructure.models.configuracion_batch_historial_suministro_model import (
    ConfiguracionBatchHistorialSuministroModel,
)

_DEFAULTS = ConfiguracionBatchHistorial(
    num_workers_max=2,
    max_reintentos=3,
    backoff_minutos=[1, 3, 5],
    limite_concurrencia_exportaciones=3,
    limite_concurrencia_consultas=5,
    umbral_nivel3=10_000,
    umbral_nivel4=50_000,
    tope_maximo_registros=200_000,
    umbral_exportacion_async=10_000,
    intervalo_poll_segundos=15,
    es_activo=True,
)


class SqlAlchemyConfiguracionBatchHistorialRepository(ConfiguracionBatchHistorialRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener(self) -> ConfiguracionBatchHistorial:
        orm = (
            self.db.query(ConfiguracionBatchHistorialSuministroModel)
            .order_by(ConfiguracionBatchHistorialSuministroModel.id_configuracion.asc())
            .first()
        )
        if orm is None:
            return _DEFAULTS
        return ConfiguracionBatchHistorial(
            num_workers_max=orm.num_workers_max,
            max_reintentos=orm.max_reintentos,
            backoff_minutos=list(orm.backoff_minutos or [1, 3, 5]),
            limite_concurrencia_exportaciones=orm.limite_concurrencia_exportaciones,
            limite_concurrencia_consultas=orm.limite_concurrencia_consultas,
            umbral_nivel3=orm.umbral_nivel3,
            umbral_nivel4=orm.umbral_nivel4,
            tope_maximo_registros=orm.tope_maximo_registros,
            umbral_exportacion_async=orm.umbral_exportacion_async,
            intervalo_poll_segundos=orm.intervalo_poll_segundos,
            es_activo=orm.es_activo,
        )
