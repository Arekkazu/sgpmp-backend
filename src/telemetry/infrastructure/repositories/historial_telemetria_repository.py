# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-38 RF-59: zona horaria, truncado con aviso, bitácora y vacíos temporales |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-09 RF-58/59: unidad del catálogo I3P-1 antes que la reportada por la lectura |
# | 2026-10-26 | Arekkazu | INC-M03 lote 26-10 RF-59: filtros (código, área, activo), estadísticas por umbral y alertas |
# | 2026-10-30 | Arekkazu | INC-M04-226-G117 RF-59: alertas del sensor o activo del periodo aunque no estén en las lecturas |
# | 2026-10-30 | Arekkazu | INC-M04-226-G117 RF-59: alertas del periodo con SQL fijo y parámetros (Bearer CWE-89) |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M3-09/N-06 RF-59: semáforo y % en rango con el umbral de la especie del área |
from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.fechas import zona_usuario
from src.telemetry.domain.entities.monitoreo import (
    AlertaCorrelacionada,
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
    ab.identificador                                AS identificador_activo,
    ab.tipo::text                                   AS tipo_activo,
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
    STDDEV_SAMP(COALESCE(t.valor_ajustado, t.valor_crudo)) AS desviacion_estandar,
    COUNT(*)                            AS total_lecturas,
    -- INC-M03-190-G119: dentro/fuera contra el umbral operativo (banda normal de RF-17),
    -- como el semáforo histórico; las lecturas sin umbral (GRIS) no cuentan en ninguno.
    COUNT(*) FILTER (WHERE um.existe AND banda.es_normal)          AS dentro_rango,
    COUNT(*) FILTER (WHERE um.existe AND banda.es_normal IS NULL
                     AND COALESCE(t.valor_ajustado, t.valor_crudo) IS NOT NULL) AS fuera_rango,
    -- INC-M03-189-G119: alertas de RF-57 ligadas a las lecturas del periodo.
    COALESCE(SUM(alc.n), 0)             AS total_alertas
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
LEFT JOIN LATERAL (
    -- N-06: sin activo vinculado se usa el umbral de una especie del área, igual que el
    -- semáforo de cada lectura (consultar_historial_use_case). Antes esas lecturas no
    -- contaban y el resumen quedaba en "—".
    SELECT true AS existe, ua.id_umbral_ambiental
    FROM modulo9.umbrales_ambientales ua
    WHERE ua.id_variable_ambiental = t.id_variable AND ua.es_activo
      AND (ua.id_especie = ab.id_especie
           OR (ab.id_especie IS NULL AND ua.id_especie IN (
               SELECT ie.id_especie FROM modulo9.infraestructuras_especies ie
               WHERE ie.id_infraestructura = i.id_infraestructura)))
    ORDER BY ua.id_especie
    LIMIT 1
) um ON true
LEFT JOIN LATERAL (
    SELECT true AS es_normal
    FROM modulo9.niveles_alerta_ambientales n
    WHERE n.id_umbral_ambiental = um.id_umbral_ambiental
      AND n.nivel = 'normal'
      AND COALESCE(t.valor_ajustado, t.valor_crudo) BETWEEN n.limite_inferior AND n.limite_superior
    LIMIT 1
) banda ON true
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS n
    FROM modulo3.alertas al
    WHERE al.id_telemetria = t.id_telemetria AND al.tipo_alerta::text <> 'TECNICA'
) alc ON true
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

# RF-59 Salida 5 / CA-8 (INC-M03-186-G117): alertas de RF-57 del periodo ligadas a las
# lecturas que cumplen los filtros (mismo alcance de finca que el historial). Fase 4
# (INC-M04-226-G117): también las del sensor o activo consultado ocurridas en el periodo,
# aunque su lectura no esté en el resultado o no tengan lectura asociada.
_ALERTAS_HISTORIAL = """
SELECT al.id_alerta, al.tipo_alerta::text AS tipo_alerta, al.severidad::text AS severidad,
       COALESCE(al.fecha_generacion, al.fecha_evento) AS timestamp_generacion,
       al.tipo_variable AS variable_afectada, al.estado_alerta::text AS estado_final
FROM modulo3.alertas al
WHERE al.tipo_alerta::text <> 'TECNICA'
  AND (al.id_telemetria IN ({ids_lecturas})
       OR (COALESCE(al.fecha_generacion, al.fecha_evento) >= :fecha_inicio
           AND COALESCE(al.fecha_generacion, al.fecha_evento) < :fecha_fin_ex
           AND (al.id_sensor = CAST(:alerta_sensor_id AS integer)
                OR al.id_activo_biologico = CAST(:alerta_id_activo AS integer))
           AND (CAST(:alerta_ids_fincas AS integer[]) IS NULL
                OR al.id_infraestructura IN (SELECT i2.id_infraestructura FROM modulo9.infraestructuras i2
                                             WHERE i2.id_finca = ANY(CAST(:alerta_ids_fincas AS integer[]))))))
ORDER BY timestamp_generacion DESC
LIMIT :max_alertas
"""

# INC-M03-181-G112: el filtro acepta el código de telemetría (TEMPERATURA_AMBIENTAL) o el
# nombre visible, sin distinguir mayúsculas. RF-59 nombra TEMPERATURA_CORPORAL a la
# variable que el catálogo I3P-1 codifica TEMP_CORPORAL.
_ALIAS_VARIABLE = {'TEMPERATURA_CORPORAL': 'TEMP_CORPORAL'}

_VARIABLES_NO_RECONOCIDAS = """
SELECT v FROM unnest(CAST(:tipos AS text[])) AS v
WHERE NOT EXISTS (
    SELECT 1 FROM modulo9.variables_ambientales va
    WHERE upper(va.codigo_telemetria) = upper(v) OR lower(va.nombre) = lower(v)
)
"""

_MAX_ALERTAS = 500

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
        tipos = [_ALIAS_VARIABLE.get(v.upper(), v) for v in filtros.tipo_variable]
        conds.append("(upper(va.codigo_telemetria) = ANY(:tipos_codigo) OR lower(va.nombre) = ANY(:tipos_nombre))")
        params['tipos_codigo'] = [v.upper() for v in tipos]
        params['tipos_nombre'] = [v.lower() for v in tipos]
    if filtros.categoria_variable:
        conds.append("t.categoria_variable::text = :categoria_variable")
        params['categoria_variable'] = filtros.categoria_variable
    if filtros.id_infraestructura is not None:
        # INC-M03-182-G112: el mismo campo que devuelve el ítem (vinculación RF-61 o, sin
        # ella, el área del sensor en la fecha de captura).
        conds.append('COALESCE(vl_lat.id_infraestructura, saa_lat.id_infraestructura) = :id_infraestructura')
        params['id_infraestructura'] = filtros.id_infraestructura
    if filtros.id_activo_biologico is not None:
        conds.append('vl_lat.id_activo_biologico = :id_activo_biologico')
        params['id_activo_biologico'] = filtros.id_activo_biologico
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
            evaluadas = dentro + fuera
            result.append(ResumenEstadistico(
                tipo_variable=f['tipo_variable'] or '',
                valor_minimo=f['valor_minimo'],
                valor_maximo=f['valor_maximo'],
                valor_promedio=f['valor_promedio'],
                total_lecturas=total,
                pct_dentro_rango=round(dentro / evaluadas * 100, 2) if evaluadas else None,
                pct_fuera_rango=round(fuera / evaluadas * 100, 2) if evaluadas else None,
                total_alertas_en_periodo=int(f['total_alertas'] or 0),
                desviacion_estandar=f['desviacion_estandar'],
            ))
        return result

    def alertas_correlacionadas(self, filtros: FiltrosHistorial) -> list[AlertaCorrelacionada]:
        sql_ids, params = _build_query(filtros, _COUNT_HISTORIAL.replace('SELECT COUNT(*)', 'SELECT t.id_telemetria', 1))
        params = {k: v for k, v in params.items() if k not in ('por_pagina', 'offset')}
        params['max_alertas'] = _MAX_ALERTAS
        # Sin sensor ni activo las dos igualdades con NULL son falsas: solo las alertas de las lecturas.
        params['alerta_sensor_id'] = filtros.sensor_id
        params['alerta_id_activo'] = filtros.id_activo_biologico
        params['alerta_ids_fincas'] = filtros.ids_fincas_permitidas
        filas = self.db.execute(text(_ALERTAS_HISTORIAL.format(ids_lecturas=sql_ids)), params).mappings().all()
        return [AlertaCorrelacionada(**f) for f in filas]

    def variables_no_reconocidas(self, tipos: list[str]) -> list[str]:
        alias = {v: _ALIAS_VARIABLE.get(v.upper(), v) for v in tipos}
        desconocidas = set(self.db.execute(text(_VARIABLES_NO_RECONOCIDAS), {'tipos': list(alias.values())}).scalars())
        return [v for v, a in alias.items() if a in desconocidas]

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
            identificador_activo=f['identificador_activo'],
            tipo_activo=f['tipo_activo'],
        )
