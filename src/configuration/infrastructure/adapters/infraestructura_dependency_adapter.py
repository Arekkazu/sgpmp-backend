"""Implementación real de :class:`InfraestructuraDependencyPort` (RF-20 FA-04).

Verifica dispositivos IoT activos vía ``vw_rf20_dependencias_infraestructuras``
(resuelve la asociación vigente de cada dispositivo al área, incluyendo
reasignaciones de RF-22) y activos biológicos activos alojados directamente en el
área, vía ``modulo2.activos_biologicos``.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.repositories.infraestructura_dependency_port import InfraestructuraDependencyPort


class InfraestructuraDependencyAdapter(InfraestructuraDependencyPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def tiene_dependencias_activas(self, id_infraestructura: int) -> bool:
        row = self.db.execute(
            text(
                "SELECT dispositivos_activos FROM modulo9.vw_rf20_dependencias_infraestructuras "
                "WHERE id_infraestructura = :id"
            ),
            {"id": id_infraestructura},
        ).fetchone()
        if row is not None and row.dispositivos_activos > 0:
            return True

        tiene_activos_biologicos = self.db.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM modulo2.activos_biologicos "
                "  WHERE id_infraestructura = :id AND id_estado NOT IN (5, 6)"  # excluye CERRADO y BAJA
                ")"
            ),
            {"id": id_infraestructura},
        ).scalar()
        return bool(tiene_activos_biologicos)
