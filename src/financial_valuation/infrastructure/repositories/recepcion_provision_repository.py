# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: M06 provisional (recepción)        |
"""Implementación SQLAlchemy de :class:`RecepcionProvisionRepository`."""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.recepcion_provision import RecepcionProvision
from src.financial_valuation.domain.repositories.recepcion_provision_repository import (
    RecepcionProvisionRepository,
)
from src.financial_valuation.infrastructure.models.recepcion_provision_m05_model import RecepcionProvisionM05Model
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyRecepcionProvisionRepository(RecepcionProvisionRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar_si_nueva(self, recepcion: RecepcionProvision) -> bool:
        sentencia = (
            insert(RecepcionProvisionM05Model)
            .values(
                id_evento_provision=recepcion.id_evento_provision,
                modalidad=recepcion.modalidad,
                schema_version=recepcion.schema_version,
                id_activo_biologico=recepcion.id_activo_biologico,
                id_gestion_fases=recepcion.id_gestion_fases,
                json_contenido=recepcion.contenido,
            )
            .on_conflict_do_nothing(index_elements=["id_evento_provision"])
        )
        try:
            resultado = self.db.execute(sentencia)
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
        return resultado.rowcount == 1
