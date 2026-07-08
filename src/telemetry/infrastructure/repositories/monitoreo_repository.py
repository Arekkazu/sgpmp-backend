from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.telemetry.domain.entities.monitoreo import EstadoSensorActual, ResumenUnidadProductiva
from src.telemetry.domain.repositories.monitoreo_repository import MonitoreoRepository

_SQL_ESTADOS = text("""
SELECT
    eas.id_sensor,
    eas.id_dispositivo_iot,
    eas.ultimo_valor,
    eas.ultima_unidad,
    eas.ultimo_timestamp_captura,
    eas.estado_semaforo,
    eas.estado_calidad::text        AS estado_calidad,
    eas.estado_desviacion::text     AS estado_desviacion,
    eas.estado_conectividad::text   AS estado_conectividad,
    eas.tiempo_sin_reporte_min,
    eas.dato_desactualizado,
    eas.id_alerta,
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
        t2.categoria_variable::text AS categoria_variable_txt,
        t2.nivel_bateria_pct,
        t2.calidad_senal_rssi,
        t2.calidad_senal_snr
    FROM modulo3.telemetrias t2
    WHERE t2.id_sensor = eas.id_sensor
    ORDER BY t2.timestamp_captura DESC
    LIMIT 1
) t_lat ON true
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
WHERE (:id_infraestructura IS NULL OR saa_lat.id_infraestructura = :id_infraestructura)
""")

_SQL_RESUMEN = text("""
SELECT
    i.id_infraestructura,
    i.nombre                    AS nombre_infraestructura,
    i.id_finca,
    f.nombre                    AS nombre_finca,
    COUNT(eas.id_sensor)        AS total_sensores,
    COUNT(CASE WHEN eas.estado_conectividad::text = 'ACTIVO' THEN 1 END)
                                AS sensores_online,
    COUNT(CASE WHEN eas.estado_conectividad::text IN ('SIN_SEÑAL','SIN_SEÑAL','INACTIVO') THEN 1 END)
                                AS sensores_sin_senal,
    COUNT(CASE WHEN eas.estado_calidad::text = 'ERROR_CALIBRACION' THEN 1 END)
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
    COUNT(CASE WHEN eas.id_alerta IS NOT NULL THEN 1 END)
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
JOIN modulo9.infraestructuras i ON i.id_infraestructura = saa_lat.id_infraestructura
JOIN modulo9.fincas f ON f.id_finca = i.id_finca
GROUP BY i.id_infraestructura, i.nombre, i.id_finca, f.nombre
ORDER BY i.nombre
""")


class SqlAlchemyMonitoreoRepository(MonitoreoRepository):

    def __init__(self, db: Session) -> None:
        self.db = db

    def obtener_estados_sensores(
        self,
        id_infraestructura: Optional[int],
        pagina: int,
        por_pagina: int,
    ) -> tuple[list[EstadoSensorActual], int]:
        offset = (pagina - 1) * por_pagina
        params = {
            'id_infraestructura': id_infraestructura,
            'por_pagina': por_pagina,
            'offset': offset,
        }
        filas = self.db.execute(_SQL_ESTADOS, params).mappings().all()
        total = self.db.execute(_SQL_COUNT, {'id_infraestructura': id_infraestructura}).scalar_one()
        return [self._fila_a_entidad(f) for f in filas], total

    def obtener_resumen_unidades(self) -> list[ResumenUnidadProductiva]:
        filas = self.db.execute(_SQL_RESUMEN).mappings().all()
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
