# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | RF-56/RF-66: ventana de lecturas del activo para el motor IA     |
"""Ventana de lecturas del activo individual para el motor IA (contrato IA-1 v1).

El sensor del paquete se ubica en su activo por la asociación M02 ``directa`` vigente (la
misma regla de ``contexto_activo_alerta_m02_adapter``). La ventana son las lecturas de todos
los sensores directos de ese activo en las 2 h previas al paquete más reciente del lote, solo
de las variables que usa ET-02, con el nombre que ET-02 espera.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.db_error_translator import raise_from_db_error
from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.ventana_inferencia_port import (
    DURACION_VENTANA,
    VentanaActivo,
    VentanaInferenciaPort,
)

#: codigo_telemetria (modulo9.variables_ambientales) → variable de ET-02.
VARIABLE_ET02 = {
    "FRECUENCIA_CARDIACA": "frecuencia_cardiaca",
    "TEMP_CORPORAL": "temperatura_corporal",
    "TEMPERATURA_CORPORAL": "temperatura_corporal",
    "ACTIVIDAD": "actividad_indice",
}

_SQL_ACTIVO_DEL_SENSOR = text("""
    SELECT DISTINCT ON (id_sensor) id_sensor, id_activo_biologico
    FROM modulo2.asociaciones_activos_sensores
    WHERE id_sensor = ANY(CAST(:sensores AS int[])) AND tipo::text = 'directa'
      AND estado_asociacion = 'ACTIVA'
      AND fecha_inicio <= :momento AND (fecha_fin IS NULL OR fecha_fin > :momento)
    ORDER BY id_sensor, fecha_inicio DESC
""")

_SQL_LECTURAS = text("""
    SELECT t.timestamp_captura, va.codigo_telemetria,
           COALESCE(t.valor_ajustado, t.valor_crudo) AS valor, t.apto_para_ia
    FROM modulo2.asociaciones_activos_sensores a
    JOIN modulo3.telemetrias t ON t.id_sensor = a.id_sensor
    JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
    WHERE a.id_activo_biologico = :activo AND a.tipo::text = 'directa' AND a.estado_asociacion = 'ACTIVA'
      AND va.codigo_telemetria = ANY(CAST(:codigos AS text[]))
      AND t.timestamp_captura > :desde AND t.timestamp_captura <= :hasta
      AND t.timestamp_captura >= a.fecha_inicio AND (a.fecha_fin IS NULL OR t.timestamp_captura < a.fecha_fin)
      AND COALESCE(t.valor_ajustado, t.valor_crudo) IS NOT NULL
    ORDER BY t.timestamp_captura
""")


class VentanaInferenciaM02Adapter(VentanaInferenciaPort):
    def __init__(self, db: Session) -> None:
        self._db = db

    def ventanas(self, paquetes: list[PaqueteInferencia]) -> dict[int, VentanaActivo]:
        if not paquetes:
            return {}
        try:
            momento = max(p.fecha_envio for p in paquetes)
            activo_de = dict(self._db.execute(_SQL_ACTIVO_DEL_SENSOR, {
                "sensores": sorted({p.id_sensor for p in paquetes}), "momento": momento,
            }).all())
            # Ventana por activo, anclada en su paquete más reciente del lote.
            hasta: dict[int, object] = {}
            for p in paquetes:
                activo = activo_de.get(p.id_sensor)
                if activo is not None and (activo not in hasta or p.fecha_envio > hasta[activo]):
                    hasta[activo] = p.fecha_envio
            lecturas = {activo: self._lecturas(activo, fin) for activo, fin in hasta.items()}
        except Exception as exc:
            raise_from_db_error(exc)
        return {
            p.id_paquetes_inferencia: VentanaActivo(
                activo_de.get(p.id_sensor), lecturas.get(activo_de.get(p.id_sensor), [])
            )
            for p in paquetes
        }

    def _lecturas(self, activo: int, fin) -> list[dict]:
        filas = self._db.execute(_SQL_LECTURAS, {
            "activo": activo, "codigos": list(VARIABLE_ET02), "desde": fin - DURACION_VENTANA, "hasta": fin,
        }).all()
        return [
            {"timestamp": ts.isoformat(), "variable": VARIABLE_ET02[codigo], "valor": float(valor),
             "apto_para_ia": apto}
            for ts, codigo, valor, apto in filas
        ]
