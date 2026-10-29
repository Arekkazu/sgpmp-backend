# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | USAB-M03 M3-08 RF-58: conteo del semáforo sobre todos los sensores, no la página |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-09 RF-58/59: unidad del catálogo I3P-1 antes que la reportada por la lectura |
# | 2026-10-26 | Arekkazu | INC-M03-205-G93 RF-58: unidades sin sensores en el resumen (GRIS, sin datos) |
# | 2026-10-26 | Leandro | ISSUE-678 G87 RF-58: proyectar última lectura válida y condición más reciente de forma independiente. |
# | 2026-10-26 | Arekkazu | Lote fixes M03 RF-58: resumen con unidades sin sensores (G93) y calidad actual (ISSUE-678) juntos |
# | 2026-10-28 | destroyerban | INC-M03-177-G57B RF-58: conteo del semáforo sin repetir la consulta de estados |
# | 2026-10-29 | Arekkazu | INC-M03-211-G98 RF-58: panel integrado de alertas activas en el dashboard |
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.monitoreo import (
    MENSAJE_UNIDAD_SIN_DATOS,
    EstadoSensorActual,
    ResumenUnidadProductiva,
    SemaforoBaseSensor,
)
from src.telemetry.domain.repositories.monitoreo_repository import MonitoreoRepository

_SQL_ACTUALIZAR_SEMAFORO = text("""
UPDATE modulo3.estados_actuales_sensores
SET estado_semaforo = :estado_semaforo
WHERE id_sensor = :id_sensor
  AND ultimo_timestamp_captura <= :timestamp_captura
""")

_SQL_ESTADOS = text("""
SELECT
    eas.id_sensor,
    eas.id_dispositivo_iot,
    CASE WHEN t_valida.id_telemetria IS NOT NULL THEN t_valida.valor_ajustado
         WHEN t_lat.id_variable IS NULL AND eas.estado_calidad::text = 'LECTURA_VALIDA' THEN eas.ultimo_valor
    END AS ultimo_valor,
    -- M3-09: el pH se mostraba en "%" porque la unidad venía de la lectura; manda I3P-1.
    COALESCE(va.unidad, t_valida.unidad_medida, eas.ultima_unidad) AS ultima_unidad,
    CASE WHEN t_valida.id_telemetria IS NOT NULL THEN t_valida.timestamp_captura
         WHEN t_lat.id_variable IS NULL AND eas.estado_calidad::text = 'LECTURA_VALIDA' THEN eas.ultimo_timestamp_captura
    END AS ultimo_timestamp_captura,
    eas.estado_semaforo,
    COALESCE(t_lat.estado_calidad::text, eas.estado_calidad::text) AS estado_calidad,
    CASE WHEN t_valida.id_telemetria IS NOT NULL OR (t_lat.id_variable IS NULL AND eas.estado_calidad::text = 'LECTURA_VALIDA')
         THEN 'LECTURA_VALIDA' END AS estado_calidad_valor_operativo,
    COALESCE(t_lat.timestamp_captura, eas.ultimo_timestamp_captura) AS timestamp_estado_actual,
    eas.estado_desviacion::text     AS estado_desviacion,
    eas.estado_conectividad::text   AS estado_conectividad,
    eas.tiempo_sin_reporte_min,
    eas.dato_desactualizado,
    -- G98: la caché conserva id_alerta aunque la alerta ya no esté ACTIVA (severidad nula).
    a.id_alerta,
    eas.tendencia,
    s.nombre                        AS nombre_sensor,
    va.nombre                       AS tipo_variable,
    t_lat.categoria_variable_txt    AS categoria_variable,
    t_lat.nivel_bateria_pct,
    t_lat.calidad_senal_rssi,
    t_lat.calidad_senal_snr,
    saa_lat.id_infraestructura,
    i.nombre                        AS nombre_infraestructura,
    i.id_finca,
    f.nombre                        AS nombre_finca,
    a.severidad                     AS severidad_alerta
FROM modulo3.estados_actuales_sensores eas
JOIN modulo9.sensores s ON s.id_sensores = eas.id_sensor
LEFT JOIN LATERAL (
    SELECT
        t2.id_variable,
        t2.estado_calidad,
        t2.timestamp_captura,
        t2.categoria_variable::text AS categoria_variable_txt,
        t2.nivel_bateria_pct,
        t2.calidad_senal_rssi,
        t2.calidad_senal_snr
    FROM modulo3.telemetrias t2
    WHERE t2.id_sensor = eas.id_sensor
    ORDER BY t2.timestamp_captura DESC, t2.id_telemetria DESC
    LIMIT 1
) t_lat ON true
LEFT JOIN LATERAL (
    SELECT tv.id_telemetria, tv.valor_ajustado, tv.unidad_medida, tv.timestamp_captura
    FROM modulo3.telemetrias tv
    WHERE tv.id_sensor = eas.id_sensor
      AND tv.id_variable = t_lat.id_variable
      AND tv.estado_calidad = 'LECTURA_VALIDA'
    ORDER BY tv.timestamp_captura DESC, tv.id_telemetria DESC
    LIMIT 1
) t_valida ON true
LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t_lat.id_variable
LEFT JOIN LATERAL (
    SELECT saa2.id_infraestructura
    FROM modulo9.sensores_areas_asociadas saa2
    WHERE saa2.id_sensor = eas.id_sensor AND saa2.fecha_finalizacion IS NULL
    ORDER BY saa2.fecha_asociacion DESC
    LIMIT 1
) saa_lat ON true
LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = saa_lat.id_infraestructura
LEFT JOIN modulo9.fincas f ON f.id_finca = i.id_finca
LEFT JOIN modulo3.alertas a ON a.id_alerta = eas.id_alerta AND a.estado_alerta = 'ACTIVA'
WHERE (:id_infraestructura IS NULL OR saa_lat.id_infraestructura = :id_infraestructura)
  AND (:filtro_finca = FALSE OR i.id_finca = ANY(:ids_fincas))
ORDER BY eas.id_sensor
LIMIT :por_pagina OFFSET :offset
""")

_SQL_COUNT = text("""
SELECT COUNT(*)
FROM modulo3.estados_actuales_sensores eas
LEFT JOIN LATERAL (
    SELECT saa2.id_infraestructura
    FROM modulo9.sensores_areas_asociadas saa2
    WHERE saa2.id_sensor = eas.id_sensor AND saa2.fecha_finalizacion IS NULL
    ORDER BY saa2.fecha_asociacion DESC
    LIMIT 1
) saa_lat ON true
LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = saa_lat.id_infraestructura
WHERE (:id_infraestructura IS NULL OR saa_lat.id_infraestructura = :id_infraestructura)
  AND (:filtro_finca = FALSE OR i.id_finca = ANY(:ids_fincas))
""")

# G57B: mismo alcance que _SQL_ESTADOS (sensores visibles, área vigente, fincas), sin las
# laterales sobre telemetrias: el conteo del semáforo solo usa la caché y la alerta activa.
_SQL_SEMAFOROS = text("""
SELECT eas.estado_semaforo, eas.dato_desactualizado, a.id_alerta, a.severidad AS severidad_alerta
FROM modulo3.estados_actuales_sensores eas
JOIN modulo9.sensores s ON s.id_sensores = eas.id_sensor
LEFT JOIN LATERAL (
    SELECT saa2.id_infraestructura
    FROM modulo9.sensores_areas_asociadas saa2
    WHERE saa2.id_sensor = eas.id_sensor AND saa2.fecha_finalizacion IS NULL
    ORDER BY saa2.fecha_asociacion DESC
    LIMIT 1
) saa_lat ON true
LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = saa_lat.id_infraestructura
LEFT JOIN modulo3.alertas a ON a.id_alerta = eas.id_alerta AND a.estado_alerta = 'ACTIVA'
WHERE (:id_infraestructura IS NULL OR saa_lat.id_infraestructura = :id_infraestructura)
  AND (:filtro_finca = FALSE OR i.id_finca = ANY(:ids_fincas))
""")

_SQL_RESUMEN = text("""
WITH agg AS (
    SELECT
        saa_lat.id_infraestructura,
        COUNT(eas.id_sensor)        AS total_sensores,
        COUNT(CASE WHEN eas.estado_conectividad::text = 'ACTIVO' THEN 1 END)
                                    AS sensores_online,
        COUNT(CASE WHEN eas.estado_conectividad::text IN ('SIN_SEÑAL','SIN_SEÑAL','INACTIVO') THEN 1 END)
                                    AS sensores_sin_senal,
        COUNT(CASE WHEN COALESCE(t_actual.estado_calidad::text, eas.estado_calidad::text) = 'ERROR_CALIBRACION' THEN 1 END)
                                    AS sensores_con_error,
        CASE MAX(CASE eas.estado_semaforo
                    WHEN 'ROJO'     THEN 4
                    WHEN 'AMARILLO' THEN 3
                    WHEN 'GRIS'     THEN 2
                    WHEN 'VERDE'    THEN 1
                    ELSE 0 END)
            WHEN 4 THEN 'ROJO'
            WHEN 3 THEN 'AMARILLO'
            WHEN 2 THEN 'GRIS'
            WHEN 1 THEN 'VERDE'
            ELSE 'SIN_DATOS'
        END                         AS estado_general,
        COUNT(CASE WHEN EXISTS (SELECT 1 FROM modulo3.alertas a
                                WHERE a.id_alerta = eas.id_alerta AND a.estado_alerta = 'ACTIVA') THEN 1 END)
                                    AS alertas_activas_count,
        MAX(eas.ultimo_timestamp_captura)
                                    AS ultimo_dato_recibido
    FROM modulo3.estados_actuales_sensores eas
    JOIN LATERAL (
        SELECT saa2.id_infraestructura
        FROM modulo9.sensores_areas_asociadas saa2
        WHERE saa2.id_sensor = eas.id_sensor AND saa2.fecha_finalizacion IS NULL
        ORDER BY saa2.fecha_asociacion DESC
        LIMIT 1
    ) saa_lat ON true
    LEFT JOIN LATERAL (
        SELECT t.estado_calidad
        FROM modulo3.telemetrias t
        WHERE t.id_sensor = eas.id_sensor
        ORDER BY t.timestamp_captura DESC, t.id_telemetria DESC
        LIMIT 1
    ) t_actual ON true
    GROUP BY saa_lat.id_infraestructura
)
-- INC-M03-205-G93 (CU04 E1): la unidad sin sensores también sale, en GRIS y con la
-- fecha de su último dato histórico (de sensores que tuvo asociados), si existe.
SELECT
    i.id_infraestructura,
    i.nombre                                    AS nombre_infraestructura,
    i.id_finca,
    f.nombre                                    AS nombre_finca,
    COALESCE(agg.total_sensores, 0)             AS total_sensores,
    COALESCE(agg.sensores_online, 0)            AS sensores_online,
    COALESCE(agg.sensores_sin_senal, 0)         AS sensores_sin_senal,
    COALESCE(agg.sensores_con_error, 0)         AS sensores_con_error,
    COALESCE(agg.estado_general, 'GRIS')        AS estado_general,
    COALESCE(agg.alertas_activas_count, 0)      AS alertas_activas_count,
    COALESCE(agg.ultimo_dato_recibido, hist.ultimo) AS ultimo_dato_recibido
FROM modulo9.infraestructuras i
JOIN modulo9.fincas f ON f.id_finca = i.id_finca
LEFT JOIN agg ON agg.id_infraestructura = i.id_infraestructura
LEFT JOIN LATERAL (
    SELECT MAX(t.timestamp_captura) AS ultimo
    FROM modulo9.sensores_areas_asociadas saa
    JOIN modulo3.telemetrias t
      ON t.id_sensor = saa.id_sensor
     AND t.timestamp_captura >= saa.fecha_asociacion
     AND (saa.fecha_finalizacion IS NULL OR t.timestamp_captura < saa.fecha_finalizacion)
    WHERE saa.id_infraestructura = i.id_infraestructura
      AND agg.id_infraestructura IS NULL
) hist ON true
WHERE (i.es_activo OR agg.id_infraestructura IS NOT NULL)
  AND (:filtro_finca = FALSE OR i.id_finca = ANY(:ids_fincas))
ORDER BY i.nombre
""")



class SqlAlchemyMonitoreoRepository(MonitoreoRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def actualizar_estado_semaforo_si_vigente(
        self,
        id_sensor: int,
        timestamp_captura: datetime,
        estado_semaforo: str,
    ) -> None:
        self.db.execute(_SQL_ACTUALIZAR_SEMAFORO, {
            'id_sensor': id_sensor,
            'timestamp_captura': timestamp_captura,
            'estado_semaforo': estado_semaforo,
        })

    def obtener_estados_sensores(
        self,
        id_infraestructura: Optional[int],
        pagina: int,
        por_pagina: Optional[int],
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[list[EstadoSensorActual], int]:
        # por_pagina None → LIMIT NULL: todos los sensores (conteo del semáforo, M3-08).
        offset = (pagina - 1) * (por_pagina or 0)
        params = {
            'id_infraestructura': id_infraestructura,
            'por_pagina': por_pagina,
            'offset': offset,
            'filtro_finca': ids_fincas_permitidas is not None,
            'ids_fincas': ids_fincas_permitidas or [],
        }
        filas = self.db.execute(_SQL_ESTADOS, params).mappings().all()
        total = self.db.execute(_SQL_COUNT, {
            'id_infraestructura': id_infraestructura,
            'filtro_finca': ids_fincas_permitidas is not None,
            'ids_fincas': ids_fincas_permitidas or [],
        }).scalar_one()
        return [self._fila_a_entidad(f) for f in filas], total

    def obtener_semaforos_sensores(
        self,
        id_infraestructura: Optional[int],
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[SemaforoBaseSensor]:
        filas = self.db.execute(_SQL_SEMAFOROS, {
            'id_infraestructura': id_infraestructura,
            'filtro_finca': ids_fincas_permitidas is not None,
            'ids_fincas': ids_fincas_permitidas or [],
        }).mappings().all()
        return [
            SemaforoBaseSensor(
                estado_semaforo=f['estado_semaforo'],
                dato_desactualizado=bool(f['dato_desactualizado']),
                id_alerta=f['id_alerta'],
                severidad_alerta=f['severidad_alerta'],
            )
            for f in filas
        ]

    def obtener_resumen_unidades(
        self,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[ResumenUnidadProductiva]:
        filas = self.db.execute(_SQL_RESUMEN, {
            'filtro_finca': ids_fincas_permitidas is not None,
            'ids_fincas': ids_fincas_permitidas or [],
        }).mappings().all()
        return [
            ResumenUnidadProductiva(
                id_infraestructura=f['id_infraestructura'],
                nombre_infraestructura=f['nombre_infraestructura'] or '',
                id_finca=f['id_finca'],
                nombre_finca=f['nombre_finca'] or '',
                total_sensores=f['total_sensores'],
                sensores_online=f['sensores_online'],
                sensores_sin_senal=f['sensores_sin_senal'],
                sensores_con_error=f['sensores_con_error'],
                estado_general=f['estado_general'],
                alertas_activas_count=f['alertas_activas_count'],
                ultimo_dato_recibido=f['ultimo_dato_recibido'],
                mensaje_estado=MENSAJE_UNIDAD_SIN_DATOS if f['total_sensores'] == 0 else None,
            )
            for f in filas
        ]

    @staticmethod
    def _fila_a_entidad(f: dict) -> EstadoSensorActual:
        return EstadoSensorActual(
            id_sensor=f['id_sensor'],
            id_dispositivo_iot=f['id_dispositivo_iot'],
            nombre_sensor=f['nombre_sensor'] or '',
            tipo_variable=f['tipo_variable'] or '',
            categoria_variable=f['categoria_variable'] or '',
            ultimo_valor=f['ultimo_valor'],
            ultima_unidad=f['ultima_unidad'],
            ultimo_timestamp_captura=f['ultimo_timestamp_captura'],
            estado_semaforo=f['estado_semaforo'] or 'GRIS',
            estado_calidad=f['estado_calidad'],
            estado_calidad_valor_operativo=f.get('estado_calidad_valor_operativo'),
            timestamp_estado_actual=f.get('timestamp_estado_actual'),
            estado_desviacion=f['estado_desviacion'],
            estado_conectividad=f['estado_conectividad'],
            tiempo_sin_reporte_min=f['tiempo_sin_reporte_min'],
            dato_desactualizado=bool(f['dato_desactualizado']),
            id_alerta=f['id_alerta'],
            severidad_alerta=f['severidad_alerta'],
            tendencia=f['tendencia'],
            id_infraestructura=f['id_infraestructura'],
            nombre_infraestructura=f['nombre_infraestructura'],
            id_finca=f['id_finca'],
            nombre_finca=f['nombre_finca'],
            nivel_bateria_pct=f['nivel_bateria_pct'],
            calidad_senal_rssi=f['calidad_senal_rssi'],
            calidad_senal_snr=f['calidad_senal_snr'],
        )
