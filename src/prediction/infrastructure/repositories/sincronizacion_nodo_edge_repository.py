"""Implementación SQLAlchemy de ``SincronizacionNodoEdgeRepository`` (DEV-09)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.sincronizacion_nodo_edge import (
    ESTADO_APLICADA,
    NodoEdge,
    SincronizacionNodoEdge,
)
from src.prediction.domain.repositories.sincronizacion_nodo_edge_repository import SincronizacionNodoEdgeRepository
from src.prediction.infrastructure.models.sincronizacion_nodo_edge_model import SincronizacionNodoEdgeModel
from src.shared.database import como_sistema
from src.shared.db_error_translator import raise_from_db_error

_SQL_SERIALES = text(
    "SELECT id_dispositivo_iot, serial FROM modulo9.dispositivos_iot WHERE id_dispositivo_iot = ANY(:ids)"
)


class SqlAlchemySincronizacionNodoEdgeRepository(SincronizacionNodoEdgeRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar_intento(
        self,
        *,
        nodo: NodoEdge,
        tipo_modelo: str,
        config_version_servidor: int,
        config_version_nodo: Optional[int],
        estado_sincronizacion: str,
        motivo_fallo: Optional[str],
        fecha_intento: datetime,
    ) -> SincronizacionNodoEdge:
        try:
            orm = (
                self.db.query(SincronizacionNodoEdgeModel)
                .filter(
                    SincronizacionNodoEdgeModel.id_dispositivo_iot == nodo.id_dispositivo_iot,
                    SincronizacionNodoEdgeModel.tipo_modelo == tipo_modelo,
                )
                .with_for_update()
                .first()
            )
            if orm is None:
                orm = SincronizacionNodoEdgeModel(
                    id_dispositivo_iot=nodo.id_dispositivo_iot,
                    tipo_modelo=tipo_modelo,
                    intentos_sincronizacion=0,
                )
                self.db.add(orm)
            orm.intentos_sincronizacion += 1
            orm.config_version_servidor = config_version_servidor
            orm.config_version_nodo = config_version_nodo
            orm.estado_sincronizacion = estado_sincronizacion
            orm.motivo_fallo = motivo_fallo
            orm.fecha_ultimo_intento = fecha_intento
            if estado_sincronizacion == ESTADO_APLICADA:
                orm.fecha_aplicacion = fecha_intento
            self.db.flush()
            return self._a_entidad(orm, nodo.serial)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar_por_tipo_modelo(self, tipo_modelo: str) -> list[SincronizacionNodoEdge]:
        orms = (
            self.db.query(SincronizacionNodoEdgeModel)
            .filter(SincronizacionNodoEdgeModel.tipo_modelo == tipo_modelo)
            .all()
        )
        if not orms:
            return []
        # modulo9 tiene RLS forzada: un Veterinario no ve dispositivos_iot.
        with como_sistema(self.db):
            seriales = dict(
                self.db.execute(_SQL_SERIALES, {"ids": [o.id_dispositivo_iot for o in orms]}).tuples().all()
            )
        nodos = [self._a_entidad(o, seriales.get(o.id_dispositivo_iot, str(o.id_dispositivo_iot))) for o in orms]
        return sorted(nodos, key=lambda n: n.serial)

    @staticmethod
    def _a_entidad(orm: SincronizacionNodoEdgeModel, serial: str) -> SincronizacionNodoEdge:
        return SincronizacionNodoEdge(
            id_dispositivo_iot=orm.id_dispositivo_iot,
            serial=serial,
            tipo_modelo=orm.tipo_modelo,
            config_version_servidor=orm.config_version_servidor,
            estado_sincronizacion=orm.estado_sincronizacion,
            intentos_sincronizacion=orm.intentos_sincronizacion,
            config_version_nodo=orm.config_version_nodo,
            fecha_ultimo_intento=orm.fecha_ultimo_intento,
            fecha_aplicacion=orm.fecha_aplicacion,
            motivo_fallo=orm.motivo_fallo,
        )
