from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.especie_consulta_port import EspecieConsulta, EspecieConsultaPort
from src.configuration.infrastructure.models.especie_model import EspecieModel


class EspecieM09Adapter(EspecieConsultaPort):
    """Consulta directamente modulo9.especies para verificar existencia y estado."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_activa(self, id_especie: int) -> Optional[EspecieConsulta]:
        orm = self.db.get(EspecieModel, id_especie)
        if orm is None or not orm.es_activo:
            return None
        return EspecieConsulta(
            id_especie=orm.id_especie,
            nombre=orm.nombre,
            es_activo=orm.es_activo,
        )
