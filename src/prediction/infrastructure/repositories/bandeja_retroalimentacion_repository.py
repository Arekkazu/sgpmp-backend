# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-72: bandeja de inferencias por evaluar (la pantalla mostraba datos de ejemplo) |
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.prediction.domain.entities.bandeja_retroalimentacion import (
    FiltrosBandejaRetroalimentacion, IndicadoresBandejaRetroalimentacion, InferenciaPorEvaluar,
)
from src.prediction.domain.repositories.bandeja_retroalimentacion_repository import (
    BandejaRetroalimentacionRepository,
)
from src.shared.db_error_translator import raise_from_db_error

# Literales fijos: las dos consultas comparten esta CTE por concatenación de constantes (sin
# f-strings ni datos del usuario en el texto; los filtros van como parámetros).
#
# - base: inferencias del rango con el nivel de la inferencia anterior del mismo animal
#   (idx_ri_activo_timestamp). La primera del rango cuenta como cambio.
# - candidatas: abren un episodio de riesgo moderado o alto, generaron alerta o ya tienen una
#   evaluación (estado_registro 'ACTIVO', como el resto de RF-72).
# - en_ventana: la regla de RegistrarRetroalimentacionUseCase, días completos transcurridos
#   <= ventana_dias (EXTRACT(DAY) de la resta es lo mismo que timedelta.days), o una ampliación
#   vigente de ese resultado.
# La RLS (pol_resultado_inferencia_select y la de retroalimentaciones) limita a las fincas del
# usuario; el filtro de fincas es el alcance de la finca activa, igual que el monitor.
_CTE = """
    WITH base AS (
        SELECT r.id_resultado_inferencia, r.id_activo_biologico, r.fecha_inferencia, r.nivel_riesgo,
               r.id_patologia, r.confianza_global, r.tiene_alerta_generada, r.modo_sombra,
               r.fecha_inicio_ventana, r.fecha_fin_ventana,
               LAG(r.nivel_riesgo) OVER (PARTITION BY r.id_activo_biologico
                                         ORDER BY r.fecha_inferencia, r.id_resultado_inferencia) AS nivel_anterior
        FROM modulo4.resultados_inferencia r
        WHERE r.fecha_inferencia >= CAST(:desde AS timestamptz)
          AND r.fecha_inferencia <= CAST(:hasta AS timestamptz)
          AND (CAST(:activo AS int) IS NULL OR r.id_activo_biologico = CAST(:activo AS int))
    ),
    candidatas AS (
        SELECT b.*,
               (SELECT count(*) FROM modulo4.retroalimentaciones_clinicas rc
                 WHERE rc.id_resultado_inferencia = b.id_resultado_inferencia
                   AND rc.estado_registro = 'ACTIVO') AS numero_evaluaciones,
               EXISTS (SELECT 1 FROM modulo4.retroalimentaciones_clinicas rc
                        WHERE rc.id_resultado_inferencia = b.id_resultado_inferencia
                          AND rc.estado_registro = 'ACTIVO'
                          AND rc.id_usuario_veterinario = CAST(:usuario AS int)) AS evaluada_por_mi,
               (SELECT max(a.fecha_limite) FROM modulo4.ampliaciones_ventana_retroalimentacion a
                 WHERE a.id_resultado_inferencia = b.id_resultado_inferencia) AS fecha_limite_ampliada
        FROM base b
        WHERE (b.nivel_riesgo >= 2 AND b.nivel_anterior IS DISTINCT FROM b.nivel_riesgo)
           OR b.tiene_alerta_generada
           OR EXISTS (SELECT 1 FROM modulo4.retroalimentaciones_clinicas rc
                       WHERE rc.id_resultado_inferencia = b.id_resultado_inferencia
                         AND rc.estado_registro = 'ACTIVO')
    ),
    con_estado AS (
        SELECT c.*,
               (EXTRACT(DAY FROM (CAST(:ahora AS timestamptz) - c.fecha_inferencia)) <= CAST(:ventana AS int)
                 OR (c.fecha_limite_ampliada IS NOT NULL
                     AND CAST(:ahora AS timestamptz) <= c.fecha_limite_ampliada)) AS en_ventana,
               GREATEST(c.fecha_inferencia + make_interval(days => CAST(:ventana AS int)),
                        c.fecha_limite_ampliada) AS fecha_limite
        FROM candidatas c
    ),
    bandeja AS (
        SELECT e.*,
               CASE WHEN e.numero_evaluaciones > 0 THEN 'EVALUADO'
                    WHEN e.en_ventana THEN 'PENDIENTE'
                    ELSE 'VENTANA_VENCIDA' END AS estado_evaluacion,
               ab.identificador AS identificador_activo, ab.id_estado,
               esp.nombre AS especie, f.nombre AS nombre_finca, i.nombre AS nombre_area,
               p.nombre AS nombre_patologia
        FROM con_estado e
        JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = e.id_activo_biologico
        LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
        LEFT JOIN modulo9.fincas f ON f.id_finca = i.id_finca
        LEFT JOIN modulo9.especies esp ON esp.id_especie = ab.id_especie
        LEFT JOIN modulo9.patologias p ON p.id_patologia = e.id_patologia
        WHERE (CAST(:fincas AS int[]) IS NULL OR i.id_finca = ANY(CAST(:fincas AS int[])))
          AND (CAST(:nivel AS int) IS NULL OR e.nivel_riesgo = CAST(:nivel AS int))
    )
"""

_SQL_LISTAR = text(_CTE + """
    SELECT bandeja.*, count(*) OVER () AS total
    FROM bandeja
    WHERE (CAST(:estado AS text) IS NULL OR bandeja.estado_evaluacion = CAST(:estado AS text))
    ORDER BY (bandeja.estado_evaluacion = 'PENDIENTE') DESC, bandeja.fecha_inferencia DESC,
             bandeja.id_resultado_inferencia
    LIMIT :limite OFFSET :desplazamiento
""")

_SQL_INDICADORES = text(_CTE + """
    SELECT count(*) FILTER (WHERE estado_evaluacion = 'PENDIENTE') AS pendientes,
           count(*) FILTER (WHERE estado_evaluacion = 'EVALUADO') AS evaluadas,
           count(*) FILTER (WHERE estado_evaluacion = 'VENTANA_VENCIDA') AS vencidas
    FROM bandeja
""")

_COLUMNAS = (
    "id_resultado_inferencia", "id_activo_biologico", "identificador_activo", "especie", "nombre_finca",
    "nombre_area", "nivel_riesgo", "id_patologia", "nombre_patologia", "confianza_global",
    "fecha_inferencia", "fecha_inicio_ventana", "fecha_fin_ventana", "tiene_alerta_generada",
    "modo_sombra", "estado_evaluacion", "en_ventana", "fecha_limite", "numero_evaluaciones",
    "evaluada_por_mi",
)


def _parametros(filtros: FiltrosBandejaRetroalimentacion) -> dict:
    return {
        "desde": filtros.desde, "hasta": filtros.hasta, "ahora": filtros.ahora,
        "ventana": filtros.ventana_dias, "usuario": filtros.id_usuario, "fincas": filtros.ids_fincas,
        "nivel": filtros.nivel_riesgo, "activo": filtros.id_activo_biologico,
    }


class SqlAlchemyBandejaRetroalimentacionRepository(BandejaRetroalimentacionRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def listar(self, filtros):
        try:
            filas = self._db.execute(_SQL_LISTAR, {
                **_parametros(filtros), "estado": filtros.estado_evaluacion,
                "limite": filtros.por_pagina, "desplazamiento": (filtros.pagina - 1) * filtros.por_pagina,
            }).mappings().all()
        except Exception as exc:
            raise_from_db_error(exc)
        total = int(filas[0]["total"]) if filas else 0
        items = [
            InferenciaPorEvaluar(
                **{c: f[c] for c in _COLUMNAS},
                activo_en_baja=f["id_estado"] == EstadoActivo.BAJA,
            )
            for f in filas
        ]
        return items, total

    def indicadores(self, filtros):
        try:
            f = self._db.execute(_SQL_INDICADORES, _parametros(filtros)).mappings().one()
        except Exception as exc:
            raise_from_db_error(exc)
        return IndicadoresBandejaRetroalimentacion(
            pendientes=int(f["pendientes"] or 0), evaluadas=int(f["evaluadas"] or 0),
            vencidas=int(f["vencidas"] or 0),
        )
