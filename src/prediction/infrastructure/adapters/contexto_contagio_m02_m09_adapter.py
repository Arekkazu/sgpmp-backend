# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-68: contexto del lote desde M02/M03/M09 para el disparo automático |
"""Contexto de RF-68 para un lote: densidad del área, sensores operativos y ambiente.

- Densidad: individuos activos del área / superficie. Un lote POBLACIONAL pide el promedio
  registrado (E2, densidad negativa) porque su cantidad vive en su propio detalle.
- Sensores operativos: los asociados al lote cuyo dispositivo está ACTIVO (RF-60).
- Ambiente: última temperatura ambiental y humedad relativa de los sensores asociados al área
  (M09), dentro de la vigencia ambiental de RF-68.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.riesgo_contagio import SINCRONIA_MAXIMA, VIGENCIA_AMBIENTAL
from src.prediction.domain.repositories.contexto_contagio_port import (
    AmbienteArea,
    ContextoContagio,
    ContextoContagioPort,
)
from src.shared.db_error_translator import raise_from_db_error

_SQL_LOTE = text("""
    SELECT a.tipo::text AS tipo, a.id_infraestructura, i.superficie,
           (SELECT count(*) FROM modulo2.activos_biologicos x
              JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = x.id_estado
             WHERE x.id_infraestructura = a.id_infraestructura AND x.tipo::text = 'INDIVIDUAL'
               AND ea.nombre::text <> ALL (ARRAY['INACTIVO', 'CERRADO', 'BAJA'])) AS individuos,
           (SELECT count(*) FROM modulo2.asociaciones_activos_sensores s
             WHERE s.id_activo_biologico = a.id_activo_biologico AND s.estado_asociacion = 'ACTIVA'
               AND (s.fecha_fin IS NULL OR s.fecha_fin > :instante)) AS sensores,
           (SELECT count(*) FROM modulo2.asociaciones_activos_sensores s
              JOIN modulo9.sensores se ON se.id_sensores = s.id_sensor
              JOIN modulo3.estados_dispositivos_iot e
                ON e.id_dispositivo_iot = se.id_dispositivo_iot AND e.estado_actual::text = 'ACTIVO'
             WHERE s.id_activo_biologico = a.id_activo_biologico AND s.estado_asociacion = 'ACTIVA'
               AND (s.fecha_fin IS NULL OR s.fecha_fin > :instante)) AS sensores_activos
    FROM modulo2.activos_biologicos a
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
    WHERE a.id_activo_biologico = :id_activo
""")

_SQL_AMBIENTE = text("""
    SELECT DISTINCT ON (va.codigo_telemetria) va.codigo_telemetria,
           COALESCE(t.valor_ajustado, t.valor_crudo) AS valor, t.timestamp_captura
    FROM modulo9.sensores_areas_asociadas sa
    JOIN modulo3.telemetrias t ON t.id_sensor = sa.id_sensor
    JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
    WHERE sa.id_infraestructura = :id_area AND sa.fecha_finalizacion IS NULL
      AND va.codigo_telemetria IN ('TEMPERATURA_AMBIENTAL', 'HUMEDAD_RELATIVA')
      AND t.timestamp_captura > :desde AND t.timestamp_captura <= :hasta
      AND COALESCE(t.valor_ajustado, t.valor_crudo) IS NOT NULL
    ORDER BY va.codigo_telemetria, t.timestamp_captura DESC
""")


class ContextoContagioM02M09Adapter(ContextoContagioPort):
    def __init__(self, db: Session) -> None:
        self._db = db

    def obtener(self, id_activo: int, instante: datetime) -> Optional[ContextoContagio]:
        try:
            lote = self._db.execute(_SQL_LOTE, {"id_activo": id_activo, "instante": instante}).first()
            if lote is None:
                return None
            lecturas = self._db.execute(_SQL_AMBIENTE, {
                "id_area": lote.id_infraestructura,
                "desde": instante - VIGENCIA_AMBIENTAL, "hasta": instante + SINCRONIA_MAXIMA,
            }).all()
        except Exception as exc:
            raise_from_db_error(exc)

        if lote.tipo == "POBLACIONAL":
            densidad = Decimal("-1")
        elif lote.superficie:
            densidad = Decimal(lote.individuos) / Decimal(lote.superficie)
        else:
            densidad = None
        porcentaje = (Decimal(100) * lote.sensores_activos / lote.sensores) if lote.sensores else Decimal(100)
        ambiente = None
        if lecturas:
            valores = {codigo: Decimal(valor) for codigo, valor, _ in lecturas}
            ambiente = AmbienteArea(
                temperatura=valores.get("TEMPERATURA_AMBIENTAL"),
                humedad_relativa=valores.get("HUMEDAD_RELATIVA"),
                fecha_captura=min(ts for _, _, ts in lecturas),
            )
        return ContextoContagio(densidad, porcentaje.quantize(Decimal("0.01")), ambiente)
