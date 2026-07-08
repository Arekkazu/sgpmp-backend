from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.vinculacion_lectura_repository import VinculacionLecturaRepository
from src.telemetry.infrastructure.models.vinculacion_lectura_model import VinculacionLecturaModel


class SqlAlchemyVinculacionLecturaRepository(VinculacionLecturaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def guardar(self, vinculacion: VinculacionLectura) -> VinculacionLectura:
        try:
            orm = VinculacionLecturaModel(
                id_telemetria=vinculacion.id_telemetria,
                modelo_manejo=vinculacion.modelo_manejo,
                id_activo_biologico=vinculacion.id_activo_biologico,
                id_infraestructura=vinculacion.id_infraestructura,
                fecha_inicio_vinculacion=vinculacion.fecha_inicio_vinculacion,
                fecha_fin_vinculacion=vinculacion.fecha_fin_vinculacion,
                mecanismo_vinculacion=vinculacion.mecanismo_vinculacion,
                estado_vinculacion=vinculacion.estado_vinculacion,
                id_usuario=vinculacion.id_usuario,
                motivo_correcion=vinculacion.motivo_correccion,
                id_vinculacion_remplazada=vinculacion.id_vinculacion_reemplazada,
                fecha_creacion=vinculacion.fecha_creacion,
            )
            self.db.add(orm)
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def obtener_por_id(self, id_vinculacion_lectura: int) -> Optional[VinculacionLectura]:
        orm = self.db.get(VinculacionLecturaModel, id_vinculacion_lectura)
        return self._a_entidad(orm) if orm else None

    def actualizar(self, vinculacion: VinculacionLectura) -> VinculacionLectura:
        try:
            orm = self.db.get(VinculacionLecturaModel, vinculacion.id_vinculacion_lectura)
            orm.estado_vinculacion = vinculacion.estado_vinculacion
            orm.mecanismo_vinculacion = vinculacion.mecanismo_vinculacion
            orm.id_activo_biologico = vinculacion.id_activo_biologico
            orm.modelo_manejo = vinculacion.modelo_manejo
            orm.id_usuario = vinculacion.id_usuario
            orm.motivo_correcion = vinculacion.motivo_correccion
            self.db.flush()
            self.db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def listar(
        self,
        id_telemetria: Optional[int] = None,
        estado_vinculacion: Optional[str] = None,
        mecanismo_vinculacion: Optional[str] = None,
        id_infraestructura: Optional[int] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> Tuple[List[VinculacionLectura], int]:
        q = select(VinculacionLecturaModel)
        if id_telemetria is not None:
            q = q.where(VinculacionLecturaModel.id_telemetria == id_telemetria)
        if estado_vinculacion:
            q = q.where(VinculacionLecturaModel.estado_vinculacion == estado_vinculacion)
        if mecanismo_vinculacion:
            q = q.where(VinculacionLecturaModel.mecanismo_vinculacion == mecanismo_vinculacion)
        if id_infraestructura is not None:
            q = q.where(VinculacionLecturaModel.id_infraestructura == id_infraestructura)
        if fecha_desde is not None:
            q = q.where(VinculacionLecturaModel.fecha_creacion >= fecha_desde)
        if fecha_hasta is not None:
            q = q.where(VinculacionLecturaModel.fecha_creacion <= fecha_hasta)

        total = self.db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
        rows = self.db.execute(
            q.order_by(VinculacionLecturaModel.fecha_creacion.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        ).scalars().all()
        return [self._a_entidad(r) for r in rows], total

    @staticmethod
    def _a_entidad(orm: VinculacionLecturaModel) -> VinculacionLectura:
        return VinculacionLectura(
            id_vinculacion_lectura=orm.id_vinculacion_lectura,
            id_telemetria=orm.id_telemetria,
            modelo_manejo=orm.modelo_manejo,
            id_activo_biologico=orm.id_activo_biologico,
            id_infraestructura=orm.id_infraestructura,
            fecha_inicio_vinculacion=orm.fecha_inicio_vinculacion,
            fecha_fin_vinculacion=orm.fecha_fin_vinculacion,
            mecanismo_vinculacion=orm.mecanismo_vinculacion,
            estado_vinculacion=orm.estado_vinculacion,
            id_usuario=orm.id_usuario,
            motivo_correccion=orm.motivo_correcion,
            id_vinculacion_reemplazada=orm.id_vinculacion_remplazada,
            fecha_creacion=orm.fecha_creacion,
        )
