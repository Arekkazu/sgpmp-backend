"""Implementación SQLAlchemy del puerto ``DispositivoIotRepository``."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.models.dispositivo_iot_model import DispositivoIotModel
from src.configuration.infrastructure.models.infraestructura_model import InfraestructuraModel
from src.shared.db_error_translator import raise_from_db_error
from src.shared.rehidratar import rehidratar


class SqlAlchemyDispositivoIotRepository(DispositivoIotRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: DispositivoIotModel) -> DispositivoIot:
        return DispositivoIot(
            id_dispositivo_iot=orm.id_dispositivo_iot,
            serial=rehidratar(SerialDispositivo, orm.serial),
            descripcion=orm.descripcion,
            id_infraestructura=orm.id_infraestructura,
            id_tipo_dispositivo=orm.id_tipo_dispositivo,
            es_activo=orm.es_activo,
            fecha_creacion=orm.fecha_creacion,
            id_dispositivo_gateway=orm.id_dispositivo_gateway,
            resolucion=orm.resolucion,
            fps=orm.fps,
            area_cobertura_m2=orm.area_cobertura_m2,
            categoria=orm.tipo.categoria,
        )

    def obtener_por_id(
        self,
        id_dispositivo_iot: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[DispositivoIot]:
        query = self.db.query(DispositivoIotModel).filter(
            DispositivoIotModel.id_dispositivo_iot == id_dispositivo_iot
        )
        if ids_fincas_permitidas is not None:
            query = query.join(
                InfraestructuraModel,
                DispositivoIotModel.id_infraestructura
                == InfraestructuraModel.id_infraestructura,
            ).filter(InfraestructuraModel.id_finca.in_(ids_fincas_permitidas))
        orm = query.first()
        return self._a_entidad(orm) if orm else None

    def obtener_por_serial(self, serial: str) -> Optional[DispositivoIot]:
        orm = (
            self.db.query(DispositivoIotModel)
            .filter(DispositivoIotModel.serial == serial)
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, dispositivo: DispositivoIot) -> DispositivoIot:
        orm = DispositivoIotModel(
            serial=dispositivo.serial.valor,
            descripcion=dispositivo.descripcion,
            id_infraestructura=dispositivo.id_infraestructura,
            id_tipo_dispositivo=dispositivo.id_tipo_dispositivo,
            es_activo=dispositivo.es_activo,
            fecha_creacion=dispositivo.fecha_creacion,
            id_dispositivo_gateway=dispositivo.id_dispositivo_gateway,
            resolucion=dispositivo.resolucion,
            fps=dispositivo.fps,
            area_cobertura_m2=dispositivo.area_cobertura_m2,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {
                "uq_dispositivo_iot_serial": (
                    f"El serial '{dispositivo.serial.valor}' ya está registrado en el sistema."
                ),
            })
        return self._a_entidad(orm)

    def actualizar(self, dispositivo: DispositivoIot) -> DispositivoIot:
        orm = self.db.get(DispositivoIotModel, dispositivo.id_dispositivo_iot)
        orm.es_activo = dispositivo.es_activo
        orm.id_dispositivo_gateway = dispositivo.id_dispositivo_gateway
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc, {})
        return self._a_entidad(orm)

    def listar_por_gateway(self, id_dispositivo_gateway: int) -> list[DispositivoIot]:
        filas = (
            self.db.query(DispositivoIotModel)
            .filter(
                DispositivoIotModel.id_dispositivo_gateway == id_dispositivo_gateway,
                DispositivoIotModel.es_activo.is_(True),
            )
            .order_by(DispositivoIotModel.serial)
            .all()
        )
        return [self._a_entidad(orm) for orm in filas]

    def listar(
        self,
        *,
        solo_activos: bool = False,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[DispositivoIot]:
        query = self.db.query(DispositivoIotModel)
        if ids_fincas_permitidas is not None:
            query = query.join(
                InfraestructuraModel,
                DispositivoIotModel.id_infraestructura
                == InfraestructuraModel.id_infraestructura,
            ).filter(InfraestructuraModel.id_finca.in_(ids_fincas_permitidas))
        if solo_activos:
            query = query.filter(DispositivoIotModel.es_activo.is_(True))
        return [self._a_entidad(orm) for orm in query.order_by(DispositivoIotModel.serial).all()]
