"""Implementación real de :class:`FincaDependencyPort` (RF-19 FA-04).

Verifica dispositivos IoT activos vía ``vw_rf19_dependencias_fincas`` (resuelve la
asociación vigente de cada dispositivo a su área, incluyendo reasignaciones de
RF-22) y activos biológicos activos vía ``modulo2.activos_biologicos``, unidos a
las áreas de la finca.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.repositories.finca_dependency_port import FincaDependencyPort


class FincaDependencyAdapter(FincaDependencyPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def tiene_dependencias_activas(self, id_finca: int) -> bool:
        row = self.db.execute(
            text(
                "SELECT dispositivos_activos FROM modulo9.vw_rf19_dependencias_fincas "
                "WHERE id_finca = :id"
            ),
            {"id": id_finca},
        ).fetchone()
        if row is not None and row.dispositivos_activos > 0:
            return True

        tiene_activos_biologicos = self.db.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM modulo2.activos_biologicos ab "
                "  JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura "
                "  WHERE i.id_finca = :id AND ab.id_estado NOT IN (5, 6)"  # excluye CERRADO y BAJA
                ")"
            ),
            {"id": id_finca},
        ).scalar()
        return bool(tiene_activos_biologicos)
