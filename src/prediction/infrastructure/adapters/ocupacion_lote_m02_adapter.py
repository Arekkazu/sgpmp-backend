# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-218-G029 RF-68: leer densidades auditadas de M02 con acceso por lote y fechas UTC. |
"""RF-68 E2: estados registrados por el trigger existente de auditoría de M02.

Se consultan únicamente densidad, fecha e id; nunca SQL ni datos personales.
El EXISTS sobre activos conserva RLS con la identidad original del solicitante.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.ocupacion_lote import MuestraOcupacion
from src.prediction.domain.repositories.ocupacion_lote_port import OcupacionLotePort
from src.shared.db_error_translator import raise_from_db_error


_SQL_MUESTRAS = text("""
    WITH accesible AS (
        SELECT 1 FROM modulo2.activos_biologicos
        WHERE id_activo_biologico = :id_lote AND tipo = 'POBLACIONAL'
    ), anteriores AS (
        SELECT id_log, fecha_evento, tipo_operacion, datos_nuevos
        FROM auditoria.logs_dml
        WHERE esquema_afectado = 'modulo2'
          AND tabla_afectada = 'detalles_activos_biologicos_poblacionales'
          AND COALESCE(datos_nuevos->>'id_activo_biologico', datos_anteriores->>'id_activo_biologico') = :lote_texto
          AND fecha_evento < (CAST(:desde AS timestamptz) AT TIME ZONE 'UTC')
          AND EXISTS (SELECT 1 FROM accesible)
        ORDER BY fecha_evento DESC, id_log DESC LIMIT 1
    ), ventana AS (
        SELECT id_log, fecha_evento, tipo_operacion, datos_nuevos
        FROM auditoria.logs_dml
        WHERE esquema_afectado = 'modulo2'
          AND tabla_afectada = 'detalles_activos_biologicos_poblacionales'
          AND COALESCE(datos_nuevos->>'id_activo_biologico', datos_anteriores->>'id_activo_biologico') = :lote_texto
          AND fecha_evento >= (CAST(:desde AS timestamptz) AT TIME ZONE 'UTC')
          AND fecha_evento <= (CAST(:hasta AS timestamptz) AT TIME ZONE 'UTC')
          AND EXISTS (SELECT 1 FROM accesible)
    ), estados AS (
        SELECT * FROM anteriores UNION ALL SELECT * FROM ventana
    )
    SELECT id_log, fecha_evento AT TIME ZONE 'UTC' AS fecha,
           CASE WHEN tipo_operacion = 'DELETE' THEN NULL ELSE datos_nuevos->>'densidad' END AS densidad
    FROM estados ORDER BY fecha_evento, id_log
""")


def _densidad(valor) -> Decimal | None:
    if valor is None:
        return None
    try:
        decimal = Decimal(valor)
    except (InvalidOperation, ValueError, TypeError):
        return None
    return decimal if decimal.is_finite() and decimal >= 0 else None


class OcupacionLoteM02Adapter(OcupacionLotePort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_muestras(self, id_lote: int, *, desde: datetime, hasta: datetime) -> list[MuestraOcupacion]:
        try:
            filas = self.db.execute(_SQL_MUESTRAS, {
                'id_lote': id_lote, 'lote_texto': str(id_lote), 'desde': desde, 'hasta': hasta,
            }).mappings().all()
        except Exception as exc:
            raise_from_db_error(exc)
        return [MuestraOcupacion(f['id_log'], f['fecha'], _densidad(f['densidad'])) for f in filas]
