# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-07 RF-53: lectura paginada de modulo3.bitacora_ingest con datos de la lectura |
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.lectura_ingesta import FiltrosIngesta, IndicadoresIngesta, LecturaIngesta
from src.telemetry.domain.repositories.ingesta_repository import IngestaRepository

# Literales fijos (sin f-strings en text()). El rango de fechas siempre va: con ~100 k eventos
# por semana en TEST, la consulta se apoya en idx_bitacora_dispositivo_fecha /
# idx_bitacora_tipo_evento. La lectura se une por id y por timestamp_captura para que
# PostgreSQL pode las particiones mensuales de telemetrias.
# Un evento sin dispositivo (p. ej. un rechazo de autenticación) solo lo ve el alcance global.
_SQL_LISTAR = text("""
    SELECT b.id_bitacora_ingest, b.fecha_evento, b.fecha_captura_dato, b.tipo_evento, b.estado_calidad,
           b.severidad, b.descripcion_text AS descripcion, b.id_sensor, s.nombre AS nombre_sensor,
           b.id_dispositivo_iot, d.serial AS serial_dispositivo, i.nombre AS nombre_area,
           b.gatway_id AS gateway_id, b.id_telemetria,
           va.nombre AS nombre_variable, t.categoria_variable, t.valor_crudo, t.valor_ajustado, t.unidad_medida,
           t.origen, t.tipo_dato, t.latencia_procesamiento_ms AS latencia_ms, t.calibrado, t.valor_agregado,
           t.latencia_alta, t.frecuencia_anomala, t.posible_drift, b.payload_recibido,
           count(*) OVER () AS total
    FROM modulo3.bitacora_ingest b
    LEFT JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = b.id_dispositivo_iot
    LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
    LEFT JOIN modulo9.sensores s ON s.id_sensores = b.id_sensor
    LEFT JOIN modulo3.telemetrias t
           ON t.id_telemetria = b.id_telemetria AND t.timestamp_captura = b.fecha_captura_dato
    LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
    WHERE b.fecha_evento >= :desde AND b.fecha_evento <= :hasta
      AND (CAST(:fincas AS int[]) IS NULL OR i.id_finca = ANY(CAST(:fincas AS int[])))
      AND (CAST(:estado AS text) IS NULL OR b.estado_calidad = CAST(:estado AS text))
      AND (CAST(:origen AS text) IS NULL OR t.origen = CAST(:origen AS text))
      AND (CAST(:dispositivo AS int) IS NULL OR b.id_dispositivo_iot = CAST(:dispositivo AS int))
      AND (CAST(:sensor AS int) IS NULL OR b.id_sensor = CAST(:sensor AS int))
    ORDER BY b.fecha_evento DESC, b.id_bitacora_ingest DESC
    LIMIT :limite OFFSET :desplazamiento
""")

_SQL_INDICADORES = text("""
    SELECT count(*) AS total,
           count(*) FILTER (WHERE b.estado_calidad = 'LECTURA_VALIDA') AS validas,
           count(*) FILTER (WHERE b.estado_calidad = 'FUERA_DE_RANGO') AS fuera_de_rango,
           count(*) FILTER (WHERE b.estado_calidad LIKE 'ERROR%' OR b.tipo_evento = 'ERROR_PROCESAMIENTO') AS errores
    FROM modulo3.bitacora_ingest b
    LEFT JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = b.id_dispositivo_iot
    LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
    WHERE b.fecha_evento >= :desde AND b.fecha_evento <= :hasta
      AND (CAST(:fincas AS int[]) IS NULL OR i.id_finca = ANY(CAST(:fincas AS int[])))
""")


class SqlAlchemyIngestaRepository(IngestaRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def listar(self, filtros: FiltrosIngesta):
        try:
            filas = self._db.execute(_SQL_LISTAR, {
                'desde': filtros.desde, 'hasta': filtros.hasta, 'fincas': filtros.ids_fincas,
                'estado': filtros.estado_calidad, 'origen': filtros.origen,
                'dispositivo': filtros.id_dispositivo_iot, 'sensor': filtros.id_sensor,
                'limite': filtros.por_pagina, 'desplazamiento': (filtros.pagina - 1) * filtros.por_pagina,
            }).mappings().all()
        except Exception as exc:
            raise_from_db_error(exc)
        total = int(filas[0]['total']) if filas else 0
        return [LecturaIngesta(**{k: v for k, v in f.items() if k != 'total'}) for f in filas], total

    def indicadores(self, desde, hasta, ids_fincas):
        try:
            f = self._db.execute(_SQL_INDICADORES, {'desde': desde, 'hasta': hasta, 'fincas': ids_fincas}).mappings().one()
        except Exception as exc:
            raise_from_db_error(exc)
        return IndicadoresIngesta(**{k: int(f[k] or 0) for k in ('total', 'validas', 'fuera_de_rango', 'errores')})
