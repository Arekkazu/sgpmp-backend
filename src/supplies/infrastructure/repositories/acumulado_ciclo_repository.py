"""Implementación SQLAlchemy del puerto :class:`AcumuladoCicloRepository` (RF-78, CU-05).

Solo lectura — la mutación del acumulado la hace el trigger de BD
``trg_acumular_costo_ciclo`` (ver ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``
Gap 6). ``acumulado_por_categoria`` llega de ``jsonb`` como ``dict[str, float]``
(psycopg2 decodifica números JSON como ``float``); se reconvierte a ``Decimal``
vía ``str()`` para no perder precisión.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.acumulado_ciclo import AcumuladoCiclo
from src.supplies.domain.repositories.acumulado_ciclo_repository import AcumuladoCicloRepository
from src.supplies.infrastructure.models.acumulado_ciclo_model import AcumuladoCicloModel

_LOCK_TIMEOUT = "2s"


class SqlAlchemyAcumuladoCicloRepository(AcumuladoCicloRepository):
    """Adaptador SQLAlchemy para ``modulo5.acumulado_ciclo``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: AcumuladoCicloModel) -> AcumuladoCiclo:
        categorias = {
            categoria: Decimal(str(monto))
            for categoria, monto in (orm.acumulado_por_categoria or {}).items()
        }
        return AcumuladoCiclo(
            id_acumulado_ciclo=orm.id_acumulado_ciclo,
            id_activo_biologico=orm.id_activo_biologico,
            id_ciclo_productivo=orm.id_ciclo_productivo,
            id_gestion_fases=orm.id_gestion_fases,
            acumulado_total_ciclo=Decimal(str(orm.acumulado_total_ciclo or 0)),
            acumulado_por_categoria=categorias,
            version_acumulado=orm.version_acumulado,
            estado=orm.estado or "ACTIVO",
            fecha_ultima_actualizacion=orm.fecha_ultima_actualizacion,
        )

    def obtener(self, id_gestion_fases: int) -> Optional[AcumuladoCiclo]:
        orm = (
            self.db.query(AcumuladoCicloModel)
            .filter(AcumuladoCicloModel.id_gestion_fases == id_gestion_fases)
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def obtener_bloqueando(self, id_gestion_fases: int) -> Optional[AcumuladoCiclo]:
        # lock_timeout evita bloqueos indefinidos ante contención — el use case inspecciona
        # InfrastructureError.original_error.orig para traducir LockNotAvailable/DeadlockDetected
        # a CONFLICTO_CONCURRENCIA (FA-08) en vez de un fallo técnico genérico.
        try:
            self.db.execute(text(f"SET LOCAL lock_timeout = '{_LOCK_TIMEOUT}'"))
            orm = (
                self.db.query(AcumuladoCicloModel)
                .filter(AcumuladoCicloModel.id_gestion_fases == id_gestion_fases)
                .with_for_update()
                .first()
            )
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm) if orm else None

    def marcar_consolidado(self, id_gestion_fases: int) -> None:
        orm = (
            self.db.query(AcumuladoCicloModel)
            .filter(AcumuladoCicloModel.id_gestion_fases == id_gestion_fases)
            .first()
        )
        if orm is not None:
            orm.estado = "CONSOLIDADO"
            self.db.flush()
