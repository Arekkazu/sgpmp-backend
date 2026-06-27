from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.biological_assets.domain.repositories.infraestructura_consulta_port import (
    InfraestructuraConsulta,
    InfraestructuraConsultaPort,
)
from src.configuration.infrastructure.models.infraestructura_model import InfraestructuraModel


class InfraestructuraM09Adapter(InfraestructuraConsultaPort):
    """Consulta directamente modulo9.infraestructuras para verificar existencia y estado."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_activa(self, id_infraestructura: int) -> Optional[InfraestructuraConsulta]:
        orm = self.db.get(InfraestructuraModel, id_infraestructura)
        if orm is None or not orm.es_activo:
            return None
        return InfraestructuraConsulta(
            id_infraestructura=orm.id_infraestructura,
            nombre=orm.nombre,
            tipo=orm.tipo,
            es_activo=orm.es_activo,
        )
