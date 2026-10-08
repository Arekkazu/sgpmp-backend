"""Implementaciones SQLAlchemy de los puertos de calibración por visión (RF-24 v2.0)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.calibracion_vision import CalibracionVision, LineaBaseVision
from src.configuration.domain.repositories.calibracion_vision_repository import (
    CalibracionVisionRepository,
    LineaBaseVisionRepository,
)
from src.configuration.domain.value_objects.calibracion_vision import (
    EstadoCalibracionVision,
    EtapaCalibracionVision,
    OrigenDisparo,
)
from src.configuration.infrastructure.models.calibracion_vision_model import (
    CalibracionVisionModel,
    LineaBaseVisionModel,
)
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyCalibracionVisionRepository(CalibracionVisionRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: CalibracionVisionModel) -> CalibracionVision:
        return CalibracionVision(
            id_calibracion_vision=orm.id_calibracion_vision,
            id_infraestructura=orm.id_infraestructura,
            id_especie=orm.id_especie,
            origen_disparo=OrigenDisparo(orm.origen_disparo),
            id_usuario=orm.id_usuario,
            ventana_observacion=orm.json_ventana_observacion,
            fecha_calibracion=orm.fecha_calibracion,
            estado=EstadoCalibracionVision(orm.estado),
            etapa_fallo=EtapaCalibracionVision(orm.etapa_fallo) if orm.etapa_fallo else None,
            motivo=orm.motivo,
            linea_base=orm.json_linea_base,
            n_observaciones=orm.n_observaciones,
            n_observaciones_validas=orm.n_observaciones_validas,
            iteraciones=orm.iteraciones,
            observaciones=orm.observaciones,
            fecha_creacion=orm.fecha_creacion,
        )

    def guardar(self, calibracion: CalibracionVision) -> CalibracionVision:
        try:
            orm = CalibracionVisionModel(
                id_infraestructura=calibracion.id_infraestructura,
                id_especie=calibracion.id_especie,
                origen_disparo=calibracion.origen_disparo.value,
                id_usuario=calibracion.id_usuario,
                json_ventana_observacion=calibracion.ventana_observacion,
                fecha_calibracion=calibracion.fecha_calibracion,
                estado=calibracion.estado.value,
                etapa_fallo=calibracion.etapa_fallo.value if calibracion.etapa_fallo else None,
                motivo=calibracion.motivo,
                json_linea_base=calibracion.linea_base,
                n_observaciones=calibracion.n_observaciones,
                n_observaciones_validas=calibracion.n_observaciones_validas,
                iteraciones=calibracion.iteraciones,
                observaciones=calibracion.observaciones,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar_por_area(self, id_infraestructura: int) -> list[CalibracionVision]:
        filas = (
            self.db.query(CalibracionVisionModel)
            .filter(CalibracionVisionModel.id_infraestructura == id_infraestructura)
            .order_by(
                CalibracionVisionModel.fecha_calibracion.desc(),
                CalibracionVisionModel.id_calibracion_vision.desc(),
            )
            .all()
        )
        return [self._a_entidad(orm) for orm in filas]


class SqlAlchemyLineaBaseVisionRepository(LineaBaseVisionRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: LineaBaseVisionModel) -> LineaBaseVision:
        return LineaBaseVision(
            id_infraestructura=orm.id_infraestructura,
            id_especie=orm.id_especie,
            id_calibracion_vision=orm.id_calibracion_vision,
            valor=orm.json_valor,
            fecha_publicacion=orm.fecha_publicacion,
        )

    def obtener_vigente(self, id_infraestructura: int, id_especie: int) -> Optional[LineaBaseVision]:
        orm = self.db.get(LineaBaseVisionModel, (id_infraestructura, id_especie))
        return self._a_entidad(orm) if orm is not None else None

    def publicar(self, linea_base: LineaBaseVision) -> LineaBaseVision:
        try:
            # FOR UPDATE: dos cálculos simultáneos del mismo par no se pisan a medias.
            orm = self.db.get(
                LineaBaseVisionModel,
                (linea_base.id_infraestructura, linea_base.id_especie),
                with_for_update=True,
            )
            if orm is None:
                orm = LineaBaseVisionModel(
                    id_infraestructura=linea_base.id_infraestructura,
                    id_especie=linea_base.id_especie,
                )
                self.db.add(orm)
            orm.id_calibracion_vision = linea_base.id_calibracion_vision
            orm.json_valor = linea_base.valor
            orm.fecha_publicacion = linea_base.fecha_publicacion
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)
