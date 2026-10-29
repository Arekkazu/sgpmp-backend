# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: activos por especie y carga del área (RFC-012) |
"""Implementación real de :class:`InfraestructuraDependencyPort` (RF-20 FA-04).

Verifica dispositivos IoT activos y sensores asociados vigentes vía
``vw_rf20_dependencias_infraestructuras`` (resuelve la asociación vigente de cada
dispositivo al área, incluyendo reasignaciones de RF-22) y activos biológicos
activos alojados directamente en el área, vía ``modulo2.activos_biologicos``.
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
                "SELECT dispositivos_activos, sensores_asociados_activos "
                "FROM modulo9.vw_rf20_dependencias_infraestructuras "
                "WHERE id_infraestructura = :id"
            ),
            {"id": id_infraestructura},
        ).fetchone()
        # INC-M09-20-02: un sensor asociado vigente también bloquea aunque su
        # dispositivo esté inactivo; lo exige el trigger del área (P0127).
        if row is not None and (row.dispositivos_activos > 0 or row.sensores_asociados_activos > 0):
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

    def contar_activos_por_especie(self, id_infraestructura: int) -> dict[int, int]:
        filas = self.db.execute(
            text(
                "SELECT id_especie, count(*) AS cantidad FROM modulo2.activos_biologicos "
                "WHERE id_infraestructura = :id AND id_estado NOT IN (5, 6) "  # excluye CERRADO y BAJA
                "GROUP BY id_especie"
            ),
            {"id": id_infraestructura},
        ).fetchall()
        return {f.id_especie: f.cantidad for f in filas}

    def calcular_carga(self, id_infraestructura: int) -> int:
        # Misma regla que InfraestructuraM09Adapter.calcular_ocupacion de M02 (RF-34/RF-48).
        return int(self.db.execute(
            text(
                "SELECT COALESCE(SUM(CASE WHEN ab.tipo = 'INDIVIDUAL' THEN 1 "
                "  ELSE COALESCE(dp.cantidad_actual, 0) END), 0) "
                "FROM modulo2.activos_biologicos ab "
                "LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales dp "
                "  ON dp.id_activo_biologico = ab.id_activo_biologico "
                "WHERE ab.id_infraestructura = :id AND ab.id_estado NOT IN (5, 6)"  # excluye CERRADO y BAJA
            ),
            {"id": id_infraestructura},
        ).scalar())
