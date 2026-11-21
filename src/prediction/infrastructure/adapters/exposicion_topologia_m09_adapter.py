# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 C21.4: exposición desde modulo9.aristas_transmision y los contagios de M04 |
"""Una arista DIRIGIDA lleva el contagio de origen a destino; una BIDIRECCIONAL, en ambos sentidos.
El peso es ``intensidad × factor_barrera`` (el término de bioseguridad llega con RF-20 v2.2)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.riesgo_contagio import FocoVecino
from src.prediction.domain.repositories.exposicion_port import ExposicionPort
from src.shared.db_error_translator import raise_from_db_error

_SQL_FOCOS = text("""
    WITH area AS (
        SELECT id_infraestructura FROM modulo2.activos_biologicos WHERE id_activo_biologico = :id_lote
    ), aristas AS (
        SELECT CASE WHEN a.id_infraestructura_destino = area.id_infraestructura
                    THEN a.id_infraestructura_origen ELSE a.id_infraestructura_destino END AS id_area,
               a.via::text AS via, a.intensidad * a.factor_barrera AS peso
        FROM modulo9.aristas_transmision a CROSS JOIN area
        WHERE a.es_activo
          AND (a.id_infraestructura_destino = area.id_infraestructura
               OR (a.direccion::text = 'BIDIRECCIONAL' AND a.id_infraestructura_origen = area.id_infraestructura))
    )
    SELECT ar.id_area, ar.via, ar.peso, r.factor_sanitario_fs
    FROM aristas ar
    JOIN LATERAL (
        SELECT rc.factor_sanitario_fs
        FROM modulo4.resultados_riesgo_contagio rc
        JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = rc.id_activo_biologico
        WHERE ab.id_infraestructura = ar.id_area AND rc.fecha_calculo >= :desde AND NOT rc.confianza_baja
          AND NOT COALESCE(rc.factores_ausentes, '[]'::jsonb) @> '["fs"]'::jsonb
        ORDER BY rc.fecha_calculo DESC, rc.id_resultado_contagio DESC
        LIMIT 1
    ) r ON true
    WHERE r.factor_sanitario_fs > 0
    ORDER BY ar.id_area, ar.via
""")

_SQL_LOTES_EXPUESTOS = text("""
    WITH area AS (
        SELECT id_infraestructura FROM modulo2.activos_biologicos WHERE id_activo_biologico = :id_lote
    ), expuestas AS (
        SELECT DISTINCT CASE WHEN a.id_infraestructura_origen = area.id_infraestructura
                             THEN a.id_infraestructura_destino ELSE a.id_infraestructura_origen END AS id_area
        FROM modulo9.aristas_transmision a CROSS JOIN area
        WHERE a.es_activo
          AND (a.id_infraestructura_origen = area.id_infraestructura
               OR (a.direccion::text = 'BIDIRECCIONAL' AND a.id_infraestructura_destino = area.id_infraestructura))
    )
    SELECT ab.id_activo_biologico
    FROM expuestas e
    JOIN modulo2.activos_biologicos ab ON ab.id_infraestructura = e.id_area
    JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = ab.id_estado
    WHERE ea.nombre::text <> ALL (ARRAY['INACTIVO', 'CERRADO', 'BAJA'])
    ORDER BY ab.id_activo_biologico
""")


class ExposicionTopologiaM09Adapter(ExposicionPort):
    def __init__(self, db: Session) -> None:
        self._db = db

    def focos_hacia(self, id_lote: int, desde: datetime) -> list[FocoVecino]:
        try:
            filas = self._db.execute(_SQL_FOCOS, {"id_lote": id_lote, "desde": desde}).all()
        except Exception as exc:
            raise_from_db_error(exc)
        return [FocoVecino(id_area, via, Decimal(peso), Decimal(fs)) for id_area, via, peso, fs in filas]

    def lotes_expuestos(self, id_lote: int) -> list[int]:
        try:
            return list(self._db.execute(_SQL_LOTES_EXPUESTOS, {"id_lote": id_lote}).scalars())
        except Exception as exc:
            raise_from_db_error(exc)
