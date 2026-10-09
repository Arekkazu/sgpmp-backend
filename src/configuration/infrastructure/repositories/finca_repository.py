"""Implementación SQLAlchemy del puerto ``FincaRepository``."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.configuration.domain.entities.finca import Finca
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.configuration.domain.value_objects.nombre_finca import NombreFinca
from src.configuration.domain.value_objects.tamano_h import TamanoH
from src.configuration.domain.value_objects.ubicacion_finca import UbicacionFinca
from src.configuration.infrastructure.models.finca_model import FincaModel
from src.shared.db_error_translator import raise_from_db_error
from src.shared.rehidratar import rehidratar


class SqlAlchemyFincaRepository(FincaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _a_entidad(orm: FincaModel) -> Finca:
        return Finca(
            id_finca=orm.id_finca,
            nombre=rehidratar(NombreFinca, orm.nombre),
            ubicacion=UbicacionFinca.from_dict(orm.ubicacion),
            tamano_h=rehidratar(TamanoH, Decimal(str(orm.tamano_h))),
            es_activo=bool(orm.es_activo),
            fecha_creacion=orm.fecha_creacion,
            fecha_actualizacion=orm.fecha_actualizacion,
            id_usuario=orm.id_usuario,
        )

    def obtener_por_id(self, id_finca: int, *, bloquear: bool = False) -> Optional[Finca]:
        orm = self.db.get(FincaModel, id_finca, with_for_update=bloquear, populate_existing=bloquear)
        return self._a_entidad(orm) if orm else None

    def obtener_por_nombre(self, nombre: NombreFinca) -> Optional[Finca]:
        orm = (
            self.db.query(FincaModel)
            .filter(func.lower(FincaModel.nombre) == nombre.normalizado())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def guardar(self, finca: Finca, id_creador: Optional[int] = None) -> Finca:
        orm = FincaModel(
            nombre=finca.nombre.valor,
            ubicacion=finca.ubicacion.to_dict(),
            tamano_h=finca.tamano_h.valor,
            es_activo=finca.es_activo,
            fecha_creacion=finca.fecha_creacion,
            fecha_actualizacion=finca.fecha_actualizacion,
        )
        try:
            self.db.add(orm)
            self.db.flush()
            # F3: `fincas` ya no guarda dueño; el usuario indicado al registrar
            # entra como primer acceso de la finca (y así se lee de vuelta).
            # F4: quien la registra también queda con acceso, porque ningún rol
            # es global; va después para no pasar por propietario. Sin esa fila
            # el `refresh` de abajo no vería la finca bajo RLS.
            for id_usuario in dict.fromkeys((finca.id_usuario, id_creador)):
                if id_usuario is None:
                    continue
                self.db.execute(
                    text(
                        "INSERT INTO modulo9.usuarios_fincas (id_usuario, id_finca) "
                        "VALUES (:id_usuario, :id_finca)"
                    ),
                    {"id_usuario": id_usuario, "id_finca": orm.id_finca},
                )
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def actualizar(self, finca: Finca) -> Finca:
        orm = self.db.get(FincaModel, finca.id_finca)
        orm.nombre = finca.nombre.valor
        orm.ubicacion = finca.ubicacion.to_dict()
        orm.tamano_h = finca.tamano_h.valor
        orm.es_activo = finca.es_activo
        orm.fecha_actualizacion = finca.fecha_actualizacion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except Exception as exc:
            raise_from_db_error(exc)
        return self._a_entidad(orm)

    def listar(self, *, ids_fincas: Optional[list[int]] = None, solo_activas: bool = False) -> list[Finca]:
        query = self.db.query(FincaModel)
        if ids_fincas is not None:
            query = query.filter(FincaModel.id_finca.in_(ids_fincas))
        if solo_activas:
            query = query.filter(FincaModel.es_activo.is_(True))
        return [self._a_entidad(orm) for orm in query.order_by(FincaModel.nombre).all()]
