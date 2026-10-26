# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-38 RF-59: zona horaria, truncado con aviso, bitácora y vacíos temporales |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-09 RF-58/59: unidad del catálogo I3P-1 antes que la reportada por la lectura |
from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.fechas import zona_usuario
from src.telemetry.domain.entities.monitoreo import (
    FiltrosHistorial,
    LecturaHistorica,
    ResumenEstadistico,
    VacioTemporal,
)
from src.telemetry.domain.repositories.historial_telemetria_repository import HistorialTelemetriaRepository

# Filtros base siempre presentes; los opcionales se agregan dinámicamente
_SELECT_HISTORIAL = """
SELECT
    t.id_telemetria,
    t.id_sensor,
    s.nombre                                        AS nombre_sensor,
    t.id_variable,
    va.nombre                                       AS tipo_variable,
    t.categoria_variable::text                      AS categoria_variable,
    COALESCE(t.valor_ajustado, t.valor_crudo)       AS valor,
    t.valor_ajustado,
    -- M3-09: la lectura traía "%" para el pH; manda la unidad del catálogo I3P-1.
    COALESCE(va.unidad, t.unidad_medida)            AS unidad_medida,
    t.timestamp_captura,
    t.estado_calidad::text                          AS estado_calidad,
    t.origen::text                                  AS origen_dato,
    COALESCE(vl_lat.id_infraestructura, saa_lat.id_infraestructura) AS id_infraestructura,
    i.nombre                                        AS infraestructura,
    f.nombre                                        AS finca,
    vl_lat.id_activo_biologico,
    esp.nombre                                      AS especie,
    ab.id_especie,
    {alerta_col}
    t.nivel_bateria_pct,
    t.calidad_senal_rssi,
    t.calidad_senal_snr
FROM modulo3.telemetrias t
LEFT JOIN modulo9.sensores s ON s.id_sensores = t.id_sensor
LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
LEFT JOIN LATERAL (
    SELECT v.id_activo_biologico, v.id_infraestructura
    FROM modulo3.vinculaciones_lecturas v
    WHERE v.id_telemetria = t.id_telemetria
    ORDER BY v.fecha_creacion DESC LIMIT 1
) vl_lat ON true
LEFT JOIN LATERAL (
    SELECT saa2.id_infraestructura
    FROM modulo9.sensores_areas_asociadas saa2
    WHERE saa2.id_sensor = t.id_sensor
      AND saa2.fecha_asociacion <= t.timestamp_captura
      AND (saa2.fecha_finalizacion IS NULL OR saa2.fecha_finalizacion > t.timestamp_captura)
    ORDER BY saa2.fecha_asociacion DESC LIMIT 1
) saa_lat ON true
LEFT JOIN modulo9.infraestructuras i
    ON i.id_infraestructura = COALESCE(vl_lat.id_infraestructura, saa_lat.id_infraestructura)
LEFT JOIN modulo9.fincas f ON f.id_finca = i.id_finca
LEFT JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = vl_lat.id_activo_biologico
LEFT JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
{alerta_join}
WHERE t.timestamp_captura >= :fecha_inicio
  AND t.timestamp_captura < :fecha_fin_ex
  {filtros_where}
ORDER BY t.timestamp_captura {orden}
LIMIT :por_pagina OFFSET :offset
"""

_COUNT_HISTORIAL = """
SELECT COUNT(*)
FROM modulo3.telemetrias t
LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
LEFT JOIN LATERAL (
    SELECT v.id_activo_biologico, v.id_infraestructura
    FROM modulo3.vinculaciones_lecturas v
    WHERE v.id_telemetria = t.id_telemetria
    ORDER BY v.fecha_creacion DESC LIMIT 1
) vl_lat ON true
LEFT JOIN LATERAL (
    SELECT saa2.id_infraestructura
    FROM modulo9.sensores_areas_asociadas saa2
    WHERE saa2.id_sensor = t.id_sensor
      AND saa2.fecha_asociacion <= t.timestamp_captura
      AND (saa2.fecha_finalizacion IS NULL OR saa2.fecha_finalizacion > t.timestamp_captura)
    ORDER BY saa2.fecha_asociacion DESC LIMIT 1
) saa_lat ON true
LEFT JOIN modulo9.infraestructuras i
    ON i.id_infraestructura = COALESCE(vl_lat.id_infraestructura, saa_lat.id_infraestructura)
LEFT JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = vl_lat.id_activo_biologico
LEFT JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
WHERE t.timestamp_captura >= :fecha_inicio
  AND t.timestamp_captura < :fecha_fin_ex
  {filtros_where}
"""

_STATS_HISTORIAL = """
SELECT
    va.nombre                           AS tipo_variable,
    MIN(COALESCE(t.valor_ajustado, t.valor_crudo)) AS valor_minimo,
    MAX(COALESCE(t.valor_ajustado, t.valor_crudo)) AS valor_maximo,
    AVG(COALESCE(t.valor_ajustado, t.valor_crudo)) AS valor_promedio,
    COUNT(*)                            AS total_lecturas,
    COUNT(CASE WHEN t.estado_calidad::text = 'LECTURA_VALIDA' THEN 1 END)  AS dentro_rango,
    COUNT(CASE WHEN t.estado_calidad::text != 'LECTURA_VALIDA' THEN 1 END) AS fuera_rango
FROM modulo3.telemetrias t
LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
-- DEV-38: mismas uniones que el conteo. Sin vl_lat/ab/esp, filtrar por especie
-- daba 500 (esp no existía) y el área/finca no coincidía con la de las lecturas.
LEFT JOIN LATERAL (
    SELECT v.id_activo_biologico, v.id_infraestructura
    FROM modulo3.vinculaciones_lecturas v
    WHERE v.id_telemetria = t.id_telemetria
    ORDER BY v.fecha_creacion DESC LIMIT 1
) vl_lat ON true
LEFT JOIN LATERAL (
    SELECT saa2.id_infraestructura
    FROM modulo9.sensores_areas_asociadas saa2
    WHERE saa2.id_sensor = t.id_sensor
      AND saa2.fecha_asociacion <= t.timestamp_captura
      AND (saa2.fecha_finalizacion IS NULL OR saa2.fecha_finalizacion > t.timestamp_captura)
    ORDER BY saa2.fecha_asociacion DESC LIMIT 1
) saa_lat ON true
LEFT JOIN modulo9.infraestructuras i
    ON i.id_infraestructura = COALESCE(vl_lat.id_infraestructura, saa_lat.id_infraestructura)
LEFT JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = vl_lat.id_activo_biologico
LEFT JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
WHERE t.timestamp_captura >= :fecha_inicio
  AND t.timestamp_captura < :fecha_fin_ex
  {filtros_where}
GROUP BY va.nombre
ORDER BY va.nombre
"""

# RF-59 E7 / CA-17 (DEV-38): vacío = hueco entre dos lecturas consecutivas del mismo
# sensor y variable mayor que 3 × la frecuencia de muestreo (la de la lectura anterior,
# o la global de RF-18 si la lectura no la trae). Mismos filtros que el conteo.
_VACIOS_HISTORIAL = """
WITH serie AS (
    SELECT
        t.id_sensor,
        va.nombre AS tipo_variable,
        t.timestamp_captura,
        LAG(t.timestamp_captura) OVER w AS anterior,
        COALESCE(
            LAG(t.frecuencia_muestreo_min) OVER w,
            t.frecuencia_muestreo_min,
            (SELECT cg.frecuencia_muestreo FROM modulo9.vw_rf18_configuracion_global_activa cg LIMIT 1)
        ) AS frecuencia_min
    FROM modulo3.telemetrias t
    LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
    LEFT JOIN LATERAL (
        SELECT v.id_activo_biologico, v.id_infraestructura
        FROM modulo3.vinculaciones_lecturas v
        WHERE v.id_telemetria = t.id_telemetria
        ORDER BY v.fecha_creacion DESC LIMIT 1
    ) vl_lat ON true
    LEFT JOIN LATERAL (
        SELECT saa2.id_infraestructura
        FROM modulo9.sensores_areas_asociadas saa2
        WHERE saa2.id_sensor = t.id_sensor
          AND saa2.fecha_asociacion <= t.timestamp_captura
          AND (saa2.fecha_finalizacion IS NULL OR saa2.fecha_finalizacion > t.timestamp_captura)
        ORDER BY saa2.fecha_asociacion DESC LIMIT 1
    ) saa_lat ON true
    LEFT JOIN modulo9.infraestructuras i
        ON i.id_infraestructura = COALESCE(vl_lat.id_infraestructura, saa_lat.id_infraestructura)
    LEFT JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = vl_lat.id_activo_biologico
    LEFT JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
    WHERE t.timestamp_captura >= :fecha_inicio
      AND t.timestamp_captura < :fecha_fin_ex
      {filtros_where}
    WINDOW w AS (PARTITION BY t.id_sensor, t.id_variable ORDER BY t.timestamp_captura)
)
SELECT id_sensor, tipo_variable, anterior AS desde, timestamp_captura AS hasta, frecuencia_min,
       CAST(EXTRACT(EPOCH FROM (timestamp_captura - anterior)) / 60 AS integer) AS duracion_min
FROM serie
WHERE anterior IS NOT NULL
  AND frecuencia_min IS NOT NULL AND frecuencia_min > 0
  AND timestamp_captura - anterior > make_interval(mins => 3 * frecuencia_min)
ORDER BY anterior
LIMIT :max_vacios
"""

# Tope de vacíos devueltos: con un sensor caído muchos días la lista no crece sin límite.
_MAX_VACIOS = 500


def _build_query(filtros: FiltrosHistorial, template: str) -> tuple[str, dict]:
    conds: list[str] = []
    # RF-59 E2 (DEV-38): las fechas son días calendario del usuario (su zona llega en
    # X-Zona-Horaria). Cortar a medianoche UTC dejaba fuera, en Colombia, las lecturas
    # de 19:00 a 24:00 del último día (y metía las del día anterior).
    zona = zona_usuario()
    params: dict = {
        'fecha_inicio': datetime.combine(filtros.fecha_inicio, time.min, tzinfo=zona),
        'fecha_fin_ex': datetime.combine(filtros.fecha_fin + timedelta(days=1), time.min, tzinfo=zona),
        'por_pagina': filtros.por_pagina,
        'offset': (filtros.pagina - 1) * filtros.por_pagina,
    }

    if filtros.sensor_id is not None:
        conds.append('t.id_sensor = :sensor_id')
        params['sensor_id'] = filtros.sensor_id
    if filtros.tipo_variable:
        conds.append("va.nombre = :tipo_variable")
        params['tipo_variable'] = filtros.tipo_variable
    if filtros.categoria_variable:
        conds.append("t.categoria_variable::text = :categoria_variable")
        params['categoria_variable'] = filtros.categoria_variable
    if filtros.id_infraestructura is not None:
        conds.append('saa_lat.id_infraestructura = :id_infraestructura')
        params['id_infraestructura'] = filtros.id_infraestructura
    if filtros.especie:
        conds.append("esp.nombre = :especie")
        params['especie'] = filtros.especie
    if filtros.estado_dato:
        conds.append("t.estado_calidad::text = :estado_dato")
        params['estado_dato'] = filtros.estado_dato
    if filtros.origen_dato:
        conds.append("t.origen::text = :origen_dato")
        params['origen_dato'] = filtros.origen_dato
    if filtros.ids_fincas_permitidas is not None:
        conds.append('i.id_finca = ANY(:ids_fincas)')
        params['ids_fincas'] = filtros.ids_fincas_permitidas

    filtros_where = ('AND ' + ' AND '.join(conds)) if conds else ''
    orden = 'ASC' if filtros.orden.upper() == 'ASC' else 'DESC'

    alerta_col = 'a_lat.id_alerta,' if filtros.incluir_alertas else 'NULL::integer AS id_alerta,'
    alerta_join = (
        """LEFT JOIN LATERAL (
    SELECT al.id_alerta
    FROM modulo3.alertas al
    WHERE al.id_telemetria = t.id_telemetria
    ORDER BY al.fecha_evento DESC LIMIT 1
) a_lat ON true"""
        if filtros.incluir_alertas
        else ''
    )

    sql = template.format(
        filtros_where=filtros_where,
        orden=orden,
        alerta_col=alerta_col,
        alerta_join=alerta_join,
    )
    return sql, params


class SqlAlchemyHistorialTelemetriaRepository(HistorialTelemetriaRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def consultar(self, filtros: FiltrosHistorial) -> tuple[list[LecturaHistorica], int]:
        sql_data, params = _build_query(filtros, _SELECT_HISTORIAL)
        sql_count, params_count = _build_query(filtros, _COUNT_HISTORIAL)

        filas = self.db.execute(text(sql_data), params).mappings().all()
        total = self.db.execute(text(sql_count), {
            k: v for k, v in params_count.items()
            if k not in ('por_pagina', 'offset')
        }).scalar_one()

        return [self._fila_a_entidad(f) for f in filas], total

    def calcular_estadisticas(self, filtros: FiltrosHistorial) -> list[ResumenEstadistico]:
        sql_stats, params = _build_query(filtros, _STATS_HISTORIAL)
        params_stats = {k: v for k, v in params.items() if k not in ('por_pagina', 'offset')}
        filas = self.db.execute(text(sql_stats), params_stats).mappings().all()
        result = []
        for f in filas:
            total = f['total_lecturas'] or 0
            dentro = f['dentro_rango'] or 0
            fuera = f['fuera_rango'] or 0
            result.append(ResumenEstadistico(
                tipo_variable=f['tipo_variable'] or '',
                valor_minimo=f['valor_minimo'],
                valor_maximo=f['valor_maximo'],
                valor_promedio=f['valor_promedio'],
                total_lecturas=total,
                pct_dentro_rango=round(dentro / total * 100, 2) if total else None,
                pct_fuera_rango=round(fuera / total * 100, 2) if total else None,
                total_alertas_en_periodo=0,
            ))
        return result

    def detectar_vacios(self, filtros: FiltrosHistorial) -> list[VacioTemporal]:
        sql, params = _build_query(filtros, _VACIOS_HISTORIAL)
        params = {k: v for k, v in params.items() if k not in ('por_pagina', 'offset')}
        params['max_vacios'] = _MAX_VACIOS
        filas = self.db.execute(text(sql), params).mappings().all()
        return [
            VacioTemporal(
                sensor_id=f['id_sensor'],
                tipo_variable=f['tipo_variable'] or '',
                desde=f['desde'],
                hasta=f['hasta'],
                duracion_min=f['duracion_min'],
                frecuencia_esperada_min=f['frecuencia_min'],
            )
            for f in filas
        ]

    @staticmethod
    def _fila_a_entidad(f: dict) -> LecturaHistorica:
        return LecturaHistorica(
            id_telemetria=f['id_telemetria'],
            id_sensor=f['id_sensor'],
            nombre_sensor=f['nombre_sensor'],
            id_variable=f['id_variable'],
            tipo_variable=f['tipo_variable'] or '',
            categoria_variable=f['categoria_variable'] or '',
            valor=f['valor'],
            valor_ajustado=f['valor_ajustado'],
            unidad_medida=f['unidad_medida'] or '',
            timestamp_captura=f['timestamp_captura'],
            estado_calidad=f['estado_calidad'] or '',
            estado_semaforo_historico='GRIS',  # el use case lo sobrescribe
            origen_dato=f['origen_dato'] or '',
            id_infraestructura=f['id_infraestructura'],
            infraestructura=f['infraestructura'],
            finca=f['finca'],
            id_activo_biologico=f['id_activo_biologico'],
            especie=f['especie'],
            id_especie=f['id_especie'],
            id_alerta=f['id_alerta'],
            nivel_bateria_pct=f['nivel_bateria_pct'],
            calidad_senal_rssi=f['calidad_senal_rssi'],
            calidad_senal_snr=f['calidad_senal_snr'],
        )
