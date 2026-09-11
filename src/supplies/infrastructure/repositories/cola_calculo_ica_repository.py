"""Implementación SQLAlchemy de :class:`ColaCalculoICARepository` (RF-74)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.item_cola_ica import ItemColaICA
from src.supplies.domain.repositories.cola_calculo_ica_repository import ColaCalculoICARepository
from src.supplies.domain.value_objects.eficiencia_enums import EstadoItemCola
from src.supplies.infrastructure.models.cola_calculo_ica_model import ColaCalculoIcaModel

_ESTADOS_PENDIENTES = (EstadoItemCola.EN_COLA.value, EstadoItemCola.PROCESANDO.value)


class SqlAlchemyColaCalculoICARepository(ColaCalculoICARepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: ColaCalculoIcaModel) -> ItemColaICA:
        return ItemColaICA(
            id_cola=orm.id_cola,
            id_activo_biologico=orm.id_activo_biologico,
            prioridad=orm.prioridad,
            estado=EstadoItemCola(orm.estado),
            motivo=orm.motivo,
            id_ejecucion_batch=orm.id_ejecucion_batch,
            fecha_encolado=orm.fecha_encolado,
            fecha_procesado=orm.fecha_procesado,
        )

    def encolar(self, item: ItemColaICA) -> Optional[ItemColaICA]:
        # Idempotente: el índice único parcial rechaza duplicados pendientes. Se usa
        # un SAVEPOINT para que el conflicto no invalide la transacción externa (el
        # control transaccional global sigue en el use case).
        orm = ColaCalculoIcaModel(
            id_activo_biologico=item.id_activo_biologico,
            prioridad=item.prioridad,
            estado=item.estado.value,
            motivo=item.motivo,
            id_ejecucion_batch=item.id_ejecucion_batch,
        )
        try:
            with self.db.begin_nested():
                self.db.add(orm)
                self.db.flush()
        except IntegrityError:
            return None
        except Exception as exc:
            raise_from_db_error(exc, {})
        self.db.refresh(orm)
        return self._a_entidad(orm)

    def listar_pendientes(self, limite: Optional[int] = None) -> list[ItemColaICA]:
        query = (
            self.db.query(ColaCalculoIcaModel)
            .filter(ColaCalculoIcaModel.estado == EstadoItemCola.EN_COLA.value)
            .order_by(
                ColaCalculoIcaModel.prioridad.asc(),
                ColaCalculoIcaModel.fecha_encolado.asc(),
            )
        )
        if limite is not None:
            query = query.limit(limite)
        return [self._a_entidad(o) for o in query.all()]

    def contar_pendientes(self) -> int:
        return (
            self.db.query(ColaCalculoIcaModel)
            .filter(ColaCalculoIcaModel.estado == EstadoItemCola.EN_COLA.value)
            .count()
        )

    def marcar(
        self,
        id_cola: int,
        estado: EstadoItemCola,
        *,
        fecha_procesado: Optional[datetime] = None,
    ) -> None:
        orm = self.db.get(ColaCalculoIcaModel, id_cola)
        if orm is None:
            return
        orm.estado = estado.value
        if fecha_procesado is not None:
            orm.fecha_procesado = fecha_procesado
        try:
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc, {})
