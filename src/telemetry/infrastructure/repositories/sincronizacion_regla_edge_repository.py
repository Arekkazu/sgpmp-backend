"""Implementación SQLAlchemy de ``SincronizacionReglaEdgeRepository`` (DEV-08).

Los destinos salen de ``modulo3.fn_gateways_edge_por_regla_alerta`` (migración
``e3b8c1d9f702``). A qué Gateway se propaga una regla no puede depender de
quién la dispara, pero ``modulo9`` tiene RLS forzada y su dueño no tiene
BYPASSRLS: ``SECURITY DEFINER`` no alcanza, y un Ingeniero sin fincas
asignadas vería cero Gateway. Por eso la búsqueda (y la de seriales) corre
``como_sistema``, el usuario de servicio de las tareas internas (D1/D4).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.database import como_sistema
from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.sincronizacion_regla_edge import (
    ESTADO_APLICADA,
    GatewayEdge,
    SincronizacionReglaEdge,
)
from src.telemetry.domain.repositories.sincronizacion_regla_edge_repository import (
    SincronizacionReglaEdgeRepository,
)
from src.telemetry.infrastructure.models.sincronizacion_regla_edge_model import SincronizacionReglaEdgeModel

_SQL_GATEWAYS_DESTINO = text(
    "SELECT id_dispositivo_iot, serial FROM modulo3.fn_gateways_edge_por_regla_alerta(:id_regla_alertas)"
)
_SQL_SERIALES = text(
    "SELECT id_dispositivo_iot, serial FROM modulo9.dispositivos_iot WHERE id_dispositivo_iot = ANY(:ids)"
)


class SqlAlchemySincronizacionReglaEdgeRepository(SincronizacionReglaEdgeRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_gateways_destino(self, id_regla_alertas: int) -> list[GatewayEdge]:
        with como_sistema(self.db):
            filas = self.db.execute(_SQL_GATEWAYS_DESTINO, {"id_regla_alertas": id_regla_alertas}).all()
        return [GatewayEdge(id_dispositivo_iot=f.id_dispositivo_iot, serial=f.serial) for f in filas]

    def registrar_intento(
        self,
        *,
        id_regla_alertas: int,
        gateway: GatewayEdge,
        version_regla: int,
        estado_sincronizacion: str,
        mensaje: Optional[str],
        fecha_intento: datetime,
        id_usuario: Optional[int],
    ) -> SincronizacionReglaEdge:
        try:
            orm = (
                self.db.query(SincronizacionReglaEdgeModel)
                .filter(
                    SincronizacionReglaEdgeModel.id_regla_alertas == id_regla_alertas,
                    SincronizacionReglaEdgeModel.id_dispositivo_iot == gateway.id_dispositivo_iot,
                )
                .with_for_update()
                .first()
            )
            if orm is None:
                orm = SincronizacionReglaEdgeModel(
                    id_regla_alertas=id_regla_alertas,
                    id_dispositivo_iot=gateway.id_dispositivo_iot,
                    intentos_sincronizacion=1,
                )
                self.db.add(orm)
            else:
                orm.intentos_sincronizacion += 1
            orm.version_regla = version_regla
            orm.estado_sincronizacion = estado_sincronizacion
            orm.mensaje = mensaje
            orm.fecha_ultimo_intento = fecha_intento
            orm.id_usuario = id_usuario
            if estado_sincronizacion == ESTADO_APLICADA:
                orm.fecha_aplicacion = fecha_intento
            self.db.flush()
            return self._a_entidad(orm, gateway.serial)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar_por_regla(self, id_regla_alertas: int) -> list[SincronizacionReglaEdge]:
        orms = (
            self.db.query(SincronizacionReglaEdgeModel)
            .filter(SincronizacionReglaEdgeModel.id_regla_alertas == id_regla_alertas)
            .all()
        )
        if not orms:
            return []
        with como_sistema(self.db):
            seriales = dict(
                self.db.execute(_SQL_SERIALES, {"ids": [o.id_dispositivo_iot for o in orms]}).tuples().all()
            )
        nodos = [self._a_entidad(o, seriales.get(o.id_dispositivo_iot, str(o.id_dispositivo_iot))) for o in orms]
        return sorted(nodos, key=lambda n: n.serial)

    @staticmethod
    def _a_entidad(orm: SincronizacionReglaEdgeModel, serial: str) -> SincronizacionReglaEdge:
        return SincronizacionReglaEdge(
            id_regla_alertas=orm.id_regla_alertas,
            id_dispositivo_iot=orm.id_dispositivo_iot,
            serial=serial,
            version_regla=orm.version_regla,
            estado_sincronizacion=orm.estado_sincronizacion,
            intentos_sincronizacion=orm.intentos_sincronizacion,
            fecha_ultimo_intento=orm.fecha_ultimo_intento,
            mensaje=orm.mensaje,
            fecha_aplicacion=orm.fecha_aplicacion,
            id_usuario=orm.id_usuario,
        )
