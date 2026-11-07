# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: outbox persistente hacia M06       |
"""Implementación SQLAlchemy de :class:`OutboxProvisionM06Repository` (RF-79)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.supplies.domain.entities.evento_provision_m06 import (
    EstadoEventoProvision,
    EventoProvisionM06,
    ModalidadProvision,
)
from src.supplies.domain.repositories.outbox_provision_m06_repository import OutboxProvisionM06Repository
from src.supplies.infrastructure.models.outbox_provision_m06_model import OutboxProvisionM06Model


class SqlAlchemyOutboxProvisionM06Repository(OutboxProvisionM06Repository):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: OutboxProvisionM06Model) -> EventoProvisionM06:
        return EventoProvisionM06(
            id_evento_provision=orm.id_outbox_provision_m06,
            modalidad=orm.modalidad,
            schema_version=orm.schema_version,
            id_activo_biologico=orm.id_activo_biologico,
            id_gestion_fases=orm.id_gestion_fases,
            id_registro_suministro=orm.id_registro_suministro,
            id_provision=orm.id_provision,
            costo_registro=orm.costo_registro,
            contenido=orm.json_contenido,
            estado=orm.estado,
            numero_intentos=orm.numero_intentos,
            fecha_intentos=list(orm.fecha_intentos or []),
            fecha_proximo_intento=orm.fecha_proximo_intento,
            es_alerta_enviada=orm.es_alerta_enviada,
            fecha_creacion=orm.fecha_creacion,
            fecha_entrega=orm.fecha_entrega,
        )

    def encolar(self, evento: EventoProvisionM06) -> EventoProvisionM06:
        orm = OutboxProvisionM06Model(
            id_outbox_provision_m06=evento.id_evento_provision,
            modalidad=evento.modalidad,
            schema_version=evento.schema_version,
            id_activo_biologico=evento.id_activo_biologico,
            id_gestion_fases=evento.id_gestion_fases,
            id_registro_suministro=evento.id_registro_suministro,
            id_provision=evento.id_provision,
            costo_registro=evento.costo_registro,
            json_contenido=evento.contenido,
            estado=evento.estado,
            fecha_proximo_intento=evento.fecha_proximo_intento,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def listar_listos(self, ahora: datetime, limite: int) -> list[EventoProvisionM06]:
        filas = (
            self.db.query(OutboxProvisionM06Model)
            .filter(
                OutboxProvisionM06Model.estado != EstadoEventoProvision.ENTREGADO.value,
                OutboxProvisionM06Model.fecha_proximo_intento <= ahora,
            )
            .order_by(OutboxProvisionM06Model.fecha_creacion.asc())
            .limit(limite)
            .all()
        )
        return [self._a_entidad(f) for f in filas]

    def actualizar(self, evento: EventoProvisionM06) -> None:
        orm = self.db.get(OutboxProvisionM06Model, evento.id_evento_provision)
        orm.estado = evento.estado
        orm.numero_intentos = evento.numero_intentos
        orm.fecha_intentos = evento.fecha_intentos
        orm.fecha_proximo_intento = evento.fecha_proximo_intento
        orm.es_alerta_enviada = evento.es_alerta_enviada
        orm.fecha_entrega = evento.fecha_entrega
        try:
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)

    def contar_pendientes(self) -> int:
        return (
            self.db.query(OutboxProvisionM06Model)
            .filter(OutboxProvisionM06Model.estado != EstadoEventoProvision.ENTREGADO.value)
            .count()
        )

    def _incrementales(self, id_gestion_fases: int):
        return self.db.query(OutboxProvisionM06Model).filter(
            OutboxProvisionM06Model.id_gestion_fases == id_gestion_fases,
            OutboxProvisionM06Model.modalidad == ModalidadProvision.INCREMENTAL.value,
        )

    def contar_sin_entregar(self, id_gestion_fases: int) -> int:
        # Solo los que ya fallaron al menos una vez: uno recién encolado sale en el próximo ciclo
        # del despachador y no indica un problema de entrega (E7 f habla de eventos retenidos).
        return self._incrementales(id_gestion_fases).filter(
            OutboxProvisionM06Model.estado != EstadoEventoProvision.ENTREGADO.value,
            OutboxProvisionM06Model.numero_intentos > 0,
        ).count()

    def sumar_incrementales(self, id_gestion_fases: int) -> Decimal:
        total = self._incrementales(id_gestion_fases).with_entities(
            func.coalesce(func.sum(OutboxProvisionM06Model.costo_registro), 0)
        ).scalar()
        return Decimal(total)
