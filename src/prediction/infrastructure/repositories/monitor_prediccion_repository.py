# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | PEND-456 RF-66/RF-68: monitor de predicción con datos reales       |
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.monitor_prediccion import InferenciaMonitor, RiesgoContagioMonitor
from src.prediction.domain.repositories.monitor_prediccion_repository import MonitorPrediccionRepository
from src.shared.db_error_translator import raise_from_db_error

# Dónde está el activo hoy: el área y la finca del activo biológico (M02).
_UBICACION = """
    JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = r.id_activo_biologico
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
    JOIN modulo9.fincas f ON f.id_finca = i.id_finca
    LEFT JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
"""
_FILTROS = """
      (CAST(:fincas AS int[]) IS NULL OR i.id_finca = ANY(CAST(:fincas AS int[])))
  AND (CAST(:desde AS timestamptz) IS NULL OR {fecha} >= CAST(:desde AS timestamptz))
  AND (CAST(:hasta AS timestamptz) IS NULL OR {fecha} <= CAST(:hasta AS timestamptz))
"""

_SQL_INFERENCIAS = text(f"""
    SELECT r.id_resultado_inferencia, r.id_activo_biologico, ab.identificador AS identificador_activo,
           i.nombre AS nombre_area, f.nombre AS nombre_finca, esp.nombre AS especie,
           r.tipo_modelo, r.id_version_modelo, v.nombre_version, r.nivel_riesgo, r.probabilidad_riesgo,
           r.id_patologia, p.nombre AS nombre_patologia, r.probabilidad_enfermedad, r.confianza_global,
           r.contexto_incompleto, r.latencia_excedida, r.modo_ejecucion, r.latencia_ms,
           r.fecha_inicio_ventana, r.fecha_fin_ventana, r.fecha_inferencia,
           r.tiene_alerta_generada, r.id_alerta_generada
    FROM modulo4.resultados_inferencia r
    {_UBICACION}
    LEFT JOIN modulo4.versiones_modelos v ON v.id_version_modelo = r.id_version_modelo
    LEFT JOIN modulo9.patologias p ON p.id_patologia = r.id_patologia
    WHERE {_FILTROS.format(fecha='r.fecha_inferencia')}
      AND (CAST(:tipo AS text) IS NULL OR r.tipo_modelo::text = CAST(:tipo AS text))
      AND (CAST(:nivel AS int) IS NULL OR r.nivel_riesgo = CAST(:nivel AS int))
    ORDER BY r.fecha_inferencia DESC, r.id_resultado_inferencia
    LIMIT :limite
""")

_SQL_CONTAGIO = text(f"""
    SELECT r.id_resultado_contagio, r.id_activo_biologico, ab.identificador AS identificador_activo,
           i.nombre AS nombre_area, f.nombre AS nombre_finca, esp.nombre AS especie,
           r.probabilidad_contagio, r.nivel_riesgo_contagio, r.factor_sanitario_fs, r.factor_ambiental_fa,
           r.factor_densidad_fd, r.w_fs_aplicado, r.w_fa_aplicado, r.w_fd_aplicado, r.confianza_baja,
           r.data_quality_score, r.factores_ausentes, r.modo_ejecucion_calculo, r.n_enfermos_detectados,
           r.total_activos_lote, r.porcentaje_sensores_activos, r.fecha_calculo, r.id_alerta_generada
    FROM modulo4.resultados_riesgo_contagio r
    {_UBICACION}
    WHERE {_FILTROS.format(fecha='r.fecha_calculo')}
      AND (CAST(:nivel AS int) IS NULL OR r.nivel_riesgo_contagio = CAST(:nivel AS int))
    ORDER BY r.fecha_calculo DESC, r.id_resultado_contagio DESC
    LIMIT :limite
""")


class SqlAlchemyMonitorPrediccionRepository(MonitorPrediccionRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def listar_inferencias(self, *, ids_fincas, tipo_modelo, nivel_riesgo, desde, hasta, limite):
        filas = self._leer(_SQL_INFERENCIAS, ids_fincas=ids_fincas, tipo=tipo_modelo, nivel=nivel_riesgo,
                           desde=desde, hasta=hasta, limite=limite)
        return [InferenciaMonitor(**f) for f in filas]

    def listar_riesgo_contagio(self, *, ids_fincas, nivel_riesgo, desde, hasta, limite):
        filas = self._leer(_SQL_CONTAGIO, ids_fincas=ids_fincas, nivel=nivel_riesgo,
                           desde=desde, hasta=hasta, limite=limite)
        return [RiesgoContagioMonitor(**f) for f in filas]

    def _leer(self, sql, *, ids_fincas, **parametros):
        try:
            return [dict(f) for f in self._db.execute(sql, {"fincas": ids_fincas, **parametros}).mappings().all()]
        except Exception as exc:
            raise_from_db_error(exc)
