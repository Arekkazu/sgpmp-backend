from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.prediction.domain.entities.patologia_m04 import PatologiaM04
from src.prediction.domain.entities.patologia_variable import PatologiaVariable
from src.prediction.domain.repositories.patologia_m04_repository import PatologiaM04Repository
from src.prediction.infrastructure.models.patologia_m04_model import PatologiaM04Model
from src.prediction.infrastructure.models.patologia_variable_model import PatologiaVariableModel
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyPatologiaM04Repository(PatologiaM04Repository):
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Mapeo ORM → entidad
    # ------------------------------------------------------------------
    def _a_entidad(self, orm: PatologiaM04Model) -> PatologiaM04:
        return PatologiaM04(
            id_patologia=orm.id_patologia,
            nombre=orm.nombre,
            especie_aplicable=orm.especie_aplicable,
            descripcion_clinica=orm.descripcion_clinica or "",
            es_base=orm.es_base,
            es_activo=orm.es_activo,
            version_catalogo=orm.version_catalogo,
            id_usuario_creador=orm.id_usuario_creador,
            fecha_creacion_m04=orm.fecha_creacion_m04,
            fecha_actualizacion=orm.fecha_actualizacion,
            variables=[
                PatologiaVariable(
                    id_patologia_variable=v.id_patologia_variable,
                    id_variable_ambiental=v.id_variable_ambiental,
                    peso_evidencia=v.peso_evidencia,
                    es_variable_critica=v.es_variable_critica,
                )
                for v in orm.variables
            ],
        )

    # ------------------------------------------------------------------
    # Lecturas
    # ------------------------------------------------------------------
    def obtener_por_id(self, id_patologia: int) -> Optional[PatologiaM04]:
        orm = self._db.get(PatologiaM04Model, id_patologia)
        return self._a_entidad(orm) if orm else None

    def obtener_por_nombre(self, nombre: str) -> Optional[PatologiaM04]:
        orm = (
            self._db.query(PatologiaM04Model)
            .filter(func.lower(func.trim(PatologiaM04Model.nombre)) == nombre.strip().lower())
            .first()
        )
        return self._a_entidad(orm) if orm else None

    def obtener_por_combinacion_variables(
        self, ids_variables: list[int], especie_aplicable: str, excluir_id: Optional[int] = None
    ) -> Optional[PatologiaM04]:
        ids_set = sorted(set(ids_variables))
        candidatos = (
            self._db.query(PatologiaM04Model)
            .filter(PatologiaM04Model.especie_aplicable == especie_aplicable)
        )
        if excluir_id is not None:
            candidatos = candidatos.filter(PatologiaM04Model.id_patologia != excluir_id)
        for orm in candidatos.all():
            vars_existentes = sorted({v.id_variable_ambiental for v in orm.variables})
            if vars_existentes == ids_set:
                return self._a_entidad(orm)
        return None

    def listar(
        self,
        especie_aplicable: Optional[str] = None,
        solo_activas: Optional[bool] = None,
        solo_base: Optional[bool] = None,
    ) -> list[PatologiaM04]:
        q = self._db.query(PatologiaM04Model)
        if especie_aplicable is not None:
            q = q.filter(PatologiaM04Model.especie_aplicable == especie_aplicable)
        if solo_activas is not None:
            q = q.filter(PatologiaM04Model.es_activo == solo_activas)
        if solo_base is not None:
            q = q.filter(PatologiaM04Model.es_base == solo_base)
        return [self._a_entidad(orm) for orm in q.order_by(PatologiaM04Model.id_patologia).all()]

    # ------------------------------------------------------------------
    # Escrituras
    # ------------------------------------------------------------------
    def guardar(self, entidad: PatologiaM04) -> PatologiaM04:
        try:
            orm = PatologiaM04Model(
                nombre=entidad.nombre,
                especie_aplicable=entidad.especie_aplicable,
                descripcion_clinica=entidad.descripcion_clinica,
                es_base=entidad.es_base,
                es_activo=entidad.es_activo,
                version_catalogo=entidad.version_catalogo,
                id_usuario_creador=entidad.id_usuario_creador,
            )
            self._db.add(orm)
            self._db.flush()
            for v in entidad.variables:
                self._db.add(
                    PatologiaVariableModel(
                        id_patologia=orm.id_patologia,
                        id_variable_ambiental=v.id_variable_ambiental,
                        peso_evidencia=v.peso_evidencia,
                        es_variable_critica=v.es_variable_critica,
                    )
                )
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)

    def actualizar(self, entidad: PatologiaM04) -> PatologiaM04:
        try:
            orm = self._db.get(PatologiaM04Model, entidad.id_patologia)
            orm.nombre = entidad.nombre
            orm.descripcion_clinica = entidad.descripcion_clinica
            orm.es_activo = entidad.es_activo
            orm.version_catalogo = entidad.version_catalogo
            orm.fecha_actualizacion = datetime.now(timezone.utc)
            # delete-then-insert para la colección de variables
            for hijo in list(orm.variables):
                self._db.delete(hijo)
            self._db.flush()
            for v in entidad.variables:
                self._db.add(
                    PatologiaVariableModel(
                        id_patologia=orm.id_patologia,
                        id_variable_ambiental=v.id_variable_ambiental,
                        peso_evidencia=v.peso_evidencia,
                        es_variable_critica=v.es_variable_critica,
                    )
                )
            self._db.flush()
            self._db.refresh(orm)
            return self._a_entidad(orm)
        except Exception as exc:
            raise_from_db_error(exc)
