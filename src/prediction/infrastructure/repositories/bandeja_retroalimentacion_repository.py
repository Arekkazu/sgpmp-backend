# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-72: bandeja de inferencias por evaluar (la pantalla mostraba datos de ejemplo) |
# | 2026-11-03 | Claude   | RF-72: una sola consulta para página e indicadores, filtros antes del escaneo |
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

# Una sola sentencia devuelve la página y los indicadores: antes eran dos consultas que repetían
# todo el trabajo (y con la ventana de 90 días más el margen pasaban de los 15 s del frontend).
#
# - activos: los animales de las fincas del alcance (o el pedido) van primero y entran como
#   ANY(ARRAY) en la condición del índice: el escaneo de resultados_inferencia solo lee sus filas
#   (y nada si la finca no tiene animales) en vez de filtrar por finca al final.
# - base: inferencias del rango con el nivel de la anterior del mismo animal
#   (idx_ri_activo_timestamp). La primera del rango cuenta como cambio.
# - evaluaciones / ampliaciones: se agregan una vez y se cruzan por id, en vez de tres
#   subconsultas por fila (cada una con su RLS).
# - candidatas: abren un episodio de riesgo moderado o alto, generaron alerta o ya tienen una
#   evaluación (estado_registro 'ACTIVO', como el resto de RF-72). MATERIALIZED para que el
#   planificador filtre aquí, antes de cruzar nombres: sin eso cruzaba el millón de filas de base.
# - en_ventana: la regla de RegistrarRetroalimentacionUseCase, días completos transcurridos
#   <= ventana_dias (EXTRACT(DAY) de la resta es lo mismo que timedelta.days), o una ampliación
#   vigente de ese resultado.
# - Al final, indicadores (sin el filtro de estado) LEFT JOIN página: siempre sale al menos una
#   fila, así los totales llegan aunque la página quede vacía.
# La RLS (pol_resultado_inferencia_select y la de retroalimentaciones) limita a las fincas del
# usuario; el filtro de fincas es el alcance de la finca activa, igual que el monitor.
_SQL = text("""
    WITH activos AS (
        SELECT ab.id_activo_biologico, ab.identificador, ab.id_estado, ab.id_especie,
               i.id_finca, i.nombre AS nombre_area
        FROM modulo2.activos_biologicos ab
        LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
        WHERE (CAST(:fincas AS int[]) IS NULL OR i.id_finca = ANY(CAST(:fincas AS int[])))
          AND (CAST(:activo AS int) IS NULL OR ab.id_activo_biologico = CAST(:activo AS int))
    ),
    base AS (
        SELECT r.id_resultado_inferencia, r.id_activo_biologico, r.fecha_inferencia, r.nivel_riesgo,
               r.id_patologia, r.confianza_global, r.tiene_alerta_generada, r.modo_sombra,
               r.fecha_inicio_ventana, r.fecha_fin_ventana,
               LAG(r.nivel_riesgo) OVER (PARTITION BY r.id_activo_biologico
                                         ORDER BY r.fecha_inferencia, r.id_resultado_inferencia) AS nivel_anterior
        FROM modulo4.resultados_inferencia r
        WHERE r.id_activo_biologico IN (SELECT a.id_activo_biologico FROM activos a)
          AND r.fecha_inferencia >= CAST(:desde AS timestamptz)
          AND r.fecha_inferencia <= CAST(:hasta AS timestamptz)
    ),
    evaluaciones AS (
        SELECT rc.id_resultado_inferencia, count(*) AS numero_evaluaciones,
               bool_or(rc.id_usuario_veterinario = CAST(:usuario AS int)) AS evaluada_por_mi
        FROM modulo4.retroalimentaciones_clinicas rc
        WHERE rc.estado_registro = 'ACTIVO'
        GROUP BY rc.id_resultado_inferencia
    ),
    ampliaciones AS (
        SELECT a.id_resultado_inferencia, max(a.fecha_limite) AS fecha_limite_ampliada
        FROM modulo4.ampliaciones_ventana_retroalimentacion a
        GROUP BY a.id_resultado_inferencia
    ),
    candidatas AS MATERIALIZED (
        SELECT b.*,
               COALESCE(ev.numero_evaluaciones, 0) AS numero_evaluaciones,
               COALESCE(ev.evaluada_por_mi, false) AS evaluada_por_mi,
               am.fecha_limite_ampliada
        FROM base b
        LEFT JOIN evaluaciones ev ON ev.id_resultado_inferencia = b.id_resultado_inferencia
        LEFT JOIN ampliaciones am ON am.id_resultado_inferencia = b.id_resultado_inferencia
        WHERE ((b.nivel_riesgo >= 2 AND b.nivel_anterior IS DISTINCT FROM b.nivel_riesgo)
               OR b.tiene_alerta_generada
               OR ev.id_resultado_inferencia IS NOT NULL)
          AND (CAST(:nivel AS int) IS NULL OR b.nivel_riesgo = CAST(:nivel AS int))
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
               a.identificador AS identificador_activo, a.id_estado, a.nombre_area,
               esp.nombre AS especie, f.nombre AS nombre_finca, p.nombre AS nombre_patologia
        FROM con_estado e
        JOIN activos a ON a.id_activo_biologico = e.id_activo_biologico
        LEFT JOIN modulo9.fincas f ON f.id_finca = a.id_finca
        LEFT JOIN modulo9.especies esp ON esp.id_especie = a.id_especie
        LEFT JOIN modulo9.patologias p ON p.id_patologia = e.id_patologia
    ),
    indicadores AS (
        SELECT count(*) FILTER (WHERE estado_evaluacion = 'PENDIENTE') AS pendientes,
               count(*) FILTER (WHERE estado_evaluacion = 'EVALUADO') AS evaluadas,
               count(*) FILTER (WHERE estado_evaluacion = 'VENTANA_VENCIDA') AS vencidas
        FROM bandeja
    ),
    pagina AS (
        SELECT bandeja.*, count(*) OVER () AS total
        FROM bandeja
        WHERE (CAST(:estado AS text) IS NULL OR bandeja.estado_evaluacion = CAST(:estado AS text))
        ORDER BY (bandeja.estado_evaluacion = 'PENDIENTE') DESC, bandeja.fecha_inferencia DESC,
                 bandeja.id_resultado_inferencia
        LIMIT :limite OFFSET :desplazamiento
    )
    SELECT ind.pendientes, ind.evaluadas, ind.vencidas, pagina.*
    FROM indicadores ind
    LEFT JOIN pagina ON true
    ORDER BY (pagina.estado_evaluacion = 'PENDIENTE') DESC, pagina.fecha_inferencia DESC,
             pagina.id_resultado_inferencia
""")

_COLUMNAS = (
    "id_resultado_inferencia", "id_activo_biologico", "identificador_activo", "especie", "nombre_finca",
    "nombre_area", "nivel_riesgo", "id_patologia", "nombre_patologia", "confianza_global",
    "fecha_inferencia", "fecha_inicio_ventana", "fecha_fin_ventana", "tiene_alerta_generada",
    "modo_sombra", "estado_evaluacion", "en_ventana", "fecha_limite", "numero_evaluaciones",
    "evaluada_por_mi",
)


class SqlAlchemyBandejaRetroalimentacionRepository(BandejaRetroalimentacionRepository):

    def __init__(self, db: Session) -> None:
        self._db = db

    def consultar(self, filtros):
        try:
            filas = self._db.execute(_SQL, {
                "desde": filtros.desde, "hasta": filtros.hasta, "ahora": filtros.ahora,
                "ventana": filtros.ventana_dias, "usuario": filtros.id_usuario, "fincas": filtros.ids_fincas,
                "nivel": filtros.nivel_riesgo, "activo": filtros.id_activo_biologico,
                "estado": filtros.estado_evaluacion, "limite": filtros.por_pagina,
                "desplazamiento": (filtros.pagina - 1) * filtros.por_pagina,
            }).mappings().all()
        except Exception as exc:
            raise_from_db_error(exc)
        primera = filas[0]  # indicadores LEFT JOIN página: siempre hay una fila
        indicadores = IndicadoresBandejaRetroalimentacion(
            pendientes=int(primera["pendientes"] or 0), evaluadas=int(primera["evaluadas"] or 0),
            vencidas=int(primera["vencidas"] or 0),
        )
        con_datos = [f for f in filas if f["id_resultado_inferencia"] is not None]
        total = int(con_datos[0]["total"]) if con_datos else 0
        items = [
            InferenciaPorEvaluar(
                **{c: f[c] for c in _COLUMNAS},
                activo_en_baja=f["id_estado"] == EstadoActivo.BAJA,
            )
            for f in con_datos
        ]
        return items, total, indicadores
