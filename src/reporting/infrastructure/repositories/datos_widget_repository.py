# | Fecha      | Nombre   | Que se hizo                                               |
# |------------|----------|-----------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103: consultas de solo lectura de los widgets        |
# | 2026-11-20 | Arekkazu | QA-M08 CU01 H-02 RF-103: el semáforo sale solo de alertas activas, no del riesgo de la inferencia |
# | 2026-11-21 | destroyerban | INC-M08-380-G002 RF-103: valor del inventario leído como sistema y acotado a las fincas del usuario |
# | 2026-11-22 | Arekkazu | A11Y2-M08 TC-DIS-279 RF-103: distribución de riesgo con enfermedad y probabilidad |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Implementación SQLAlchemy de :class:`DatosWidgetRepository` (RF-103).

Lo que ya calcula otro módulo se reutiliza tal cual para que el dashboard muestre lo mismo que la
pantalla del módulo: el semáforo de las lecturas (monitoreo de M03), las inferencias por evaluar
(M04), los activos valorados y los pendientes de reconocimiento (M06). El resto son conteos y
listados simples, siempre acotados a la finca recibida.

No usa las vistas ``modulo8.vw_dashboard_*`` del dump inicial: no filtran por finca, toman el día
UTC (``CURRENT_DATE``) y sus umbrales no son los del RF.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from src.financial_valuation.infrastructure.adapters.activo_financiero_m02_adapter import ActivoFinancieroM02Adapter
from src.financial_valuation.infrastructure.repositories.valoracion_repository import SqlAlchemyValoracionRepository
from src.prediction.application.use_cases.retroalimentacion.consultar_bandeja_retroalimentacion_use_case import (
    ConsultarBandejaRetroalimentacionUseCase,
)
from src.prediction.infrastructure.repositories.bandeja_retroalimentacion_repository import (
    SqlAlchemyBandejaRetroalimentacionRepository,
)
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.reporting.domain.repositories.datos_widget_repository import DatosWidgetRepository, Fila
from src.shared.database import como_sistema
from src.shared.nombre_activo import nombre_activo_sql
from src.telemetry.application.use_cases.monitoreo.obtener_dashboard_use_case import ObtenerDashboardUseCase
from src.telemetry.infrastructure.repositories.monitoreo_repository import SqlAlchemyMonitoreoRepository

# Alertas operativas que todavía piden atención.
_ALERTA_VIGENTE = "a.estado_alerta IN ('ACTIVA', 'EN_ATENCION')"
# Fallas del dispositivo: no pintan el semáforo del Productor, solo lo dejan sin datos (RF-103 R5).
_DISPOSITIVO_CAIDO = "('SIN_SEÑAL', 'EN_MANTENIMIENTO', 'INACTIVO')"
_TIPOS_SANITARIOS = "('PREDICCION_PATOLOGIA', 'FIEBRE', 'SINDROME_RESPIRATORIO', 'RIESGO_CONTAGIO')"

# Última inferencia de M04 de cada activo dentro de la ventana (usa idx_ri_activo_timestamp).
_ULTIMA_INFERENCIA = """
    JOIN LATERAL (
        SELECT r.nivel_riesgo, r.fecha_inferencia, r.id_patologia, r.confianza_global
        FROM modulo4.resultados_inferencia r
        WHERE r.id_activo_biologico = ab.id_activo_biologico
          AND r.fecha_inferencia >= now() - make_interval(hours => :horas)
        ORDER BY r.fecha_inferencia DESC
        LIMIT 1
    ) ri ON true"""

_FILTRO_ESPECIES = "(CAST(:especies AS int[]) IS NULL OR ab.id_especie = ANY(:especies))"


class SqlAlchemyDatosWidgetRepository(DatosWidgetRepository):
    """Implementación SQLAlchemy de las consultas de widgets."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _filas(self, consulta: TextClause, params: Optional[dict[str, Any]] = None) -> list[Fila]:
        return [dict(f._mapping) for f in self.db.execute(consulta, params or {})]

    def _paginado(self, consulta: TextClause, params: dict[str, Any]) -> tuple[list[Fila], int]:
        """``consulta`` trae ``count(*) OVER () AS total``; se separa del resto de columnas."""
        filas = self._filas(consulta, params)
        total = filas[0].pop("total") if filas else 0
        for f in filas[1:]:
            f.pop("total")
        return filas, total

    # --- Opciones ---------------------------------------------------------------------------------

    def areas_de_finca(self, id_finca: int) -> list[Fila]:
        """Lista las áreas activas de la finca."""
        return self._filas(text(
            "SELECT id_infraestructura AS valor, nombre FROM modulo9.infraestructuras "
            "WHERE id_finca = :f AND es_activo ORDER BY nombre"), {"f": id_finca})

    def especies_de_finca(self, id_finca: int) -> list[Fila]:
        """Lista las especies de la finca."""
        return self._filas(text("""
            SELECT DISTINCT e.id_especie AS valor, e.nombre
            FROM modulo9.infraestructuras_especies ie
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = ie.id_infraestructura
            JOIN modulo9.especies e ON e.id_especie = ie.id_especie
            WHERE i.id_finca = :f AND e.es_activo
            ORDER BY e.nombre"""), {"f": id_finca})

    def sensores_de_finca(self, id_finca: int) -> list[Fila]:
        """Lista los sensores de la finca con su área."""
        return self._filas(text("""
            SELECT DISTINCT s.id_sensores AS valor, s.nombre, i.nombre AS area
            FROM modulo9.sensores s
            JOIN modulo9.sensores_areas_asociadas saa ON saa.id_sensor = s.id_sensores AND saa.fecha_finalizacion IS NULL
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = saa.id_infraestructura
            WHERE i.id_finca = :f AND s.es_activo
            ORDER BY i.nombre, s.nombre"""), {"f": id_finca})

    # --- Telemetría y predicción ------------------------------------------------------------------

    def semaforo_areas(self, id_finca: int, areas: Optional[list[int]]) -> list[Fila]:
        """Devuelve el semáforo de cada área de la finca."""
        return self._filas(text(f"""
            WITH areas AS (
                SELECT i.id_infraestructura, i.nombre
                FROM modulo9.infraestructuras i
                WHERE i.id_finca = :f AND i.es_activo
                  AND (CAST(:areas AS int[]) IS NULL OR i.id_infraestructura = ANY(:areas))
            ), alertas AS (
                SELECT a.id_infraestructura,
                       count(*) FILTER (WHERE a.severidad = 'CRITICO') AS criticas,
                       count(*) FILTER (WHERE a.severidad <> 'CRITICO') AS advertencias
                FROM modulo3.alertas a
                JOIN areas ar ON ar.id_infraestructura = a.id_infraestructura
                WHERE {_ALERTA_VIGENTE} AND a.tipo_alerta <> 'TECNICA'
                GROUP BY a.id_infraestructura
            ), inferencias AS (
                -- Una predicción reciente solo dice que el área tiene datos: el color sale de las alertas
                -- activas de RF-57 y RF-66 (las de M04 son PREDICCION_PATOLOGIA en modulo3.alertas), no del
                -- nivel de riesgo de la última inferencia (QA M08 CU01 H-02).
                SELECT DISTINCT ab.id_infraestructura
                FROM modulo2.activos_biologicos ab
                JOIN areas ar ON ar.id_infraestructura = ab.id_infraestructura
                {_ULTIMA_INFERENCIA}
            ), sensores AS (
                SELECT saa.id_infraestructura, count(*) AS total,
                       count(*) FILTER (WHERE ed.estado_actual::text IN {_DISPOSITIVO_CAIDO}) AS caidos
                FROM modulo9.sensores_areas_asociadas saa
                JOIN areas ar ON ar.id_infraestructura = saa.id_infraestructura
                JOIN modulo9.sensores s ON s.id_sensores = saa.id_sensor AND s.es_activo
                LEFT JOIN modulo3.estados_dispositivos_iot ed ON ed.id_dispositivo_iot = s.id_dispositivo_iot
                WHERE saa.fecha_finalizacion IS NULL
                GROUP BY saa.id_infraestructura
            )
            SELECT ar.id_infraestructura, ar.nombre,
                   COALESCE(al.criticas, 0) AS criticas,
                   COALESCE(al.advertencias, 0) AS advertencias,
                   (inf.id_infraestructura IS NULL AND COALESCE(se.total, 0) = COALESCE(se.caidos, 0)) AS sin_datos
            FROM areas ar
            LEFT JOIN alertas al ON al.id_infraestructura = ar.id_infraestructura
            LEFT JOIN inferencias inf ON inf.id_infraestructura = ar.id_infraestructura
            LEFT JOIN sensores se ON se.id_infraestructura = ar.id_infraestructura
            ORDER BY ar.nombre"""), {"f": id_finca, "areas": areas, "horas": 24})

    def lecturas(self, id_finca: int, id_area: Optional[int]) -> list[Fila]:
        """Devuelve las lecturas actuales con el mismo semáforo del monitoreo."""
        # El mismo semáforo efectivo que la pantalla de monitoreo (umbral vigente y tolerancia).
        sensores, _, _ = ObtenerDashboardUseCase(SqlAlchemyMonitoreoRepository(self.db)).execute(
            id_infraestructura=id_area, pagina=1, por_pagina=50,
            ver_datos_tecnicos=False, ids_fincas_permitidas=[id_finca],
        )
        return [{
            "id_sensor": s.id_sensor,
            "sensor": s.nombre_sensor,
            "area": s.nombre_infraestructura,
            "variable": s.tipo_variable,
            "categoria": s.categoria_variable,
            "valor": float(s.ultimo_valor) if s.ultimo_valor is not None else None,
            "unidad": s.ultima_unidad,
            "semaforo": s.estado_semaforo,
            "tendencia": s.tendencia,
            "fecha": s.ultimo_timestamp_captura,
            "desactualizado": s.dato_desactualizado,
        } for s in sensores]

    def historico(self, id_finca: int, id_area: Optional[int], patron_variable: str,
                  desde: datetime, paso: str) -> list[Fila]:
        """Devuelve la serie histórica agregada de la variable."""
        return self._filas(text("""
            SELECT s.nombre AS sensor, va.nombre AS variable, va.unidad,
                   date_bin(CAST(:paso AS interval), t.timestamp_captura, TIMESTAMPTZ '2000-01-01') AS instante,
                   round(avg(COALESCE(t.valor_ajustado, t.valor_crudo))::numeric, 2) AS valor
            FROM modulo3.telemetrias t
            JOIN modulo9.sensores s ON s.id_sensores = t.id_sensor
            JOIN modulo9.sensores_areas_asociadas saa ON saa.id_sensor = s.id_sensores AND saa.fecha_finalizacion IS NULL
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = saa.id_infraestructura
            JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable
            WHERE i.id_finca = :f AND (CAST(:area AS int) IS NULL OR i.id_infraestructura = :area)
              AND t.timestamp_captura >= :desde
              AND t.estado_calidad = 'LECTURA_VALIDA'
              AND lower(va.nombre) LIKE :patron AND COALESCE(va.categoria_variable, '') <> 'ANIMAL'
            GROUP BY 1, 2, 3, 4
            ORDER BY 1, 4"""), {"f": id_finca, "area": id_area, "desde": desde, "paso": paso, "patron": patron_variable})

    def alertas_activas(self, id_finca: int, areas: Optional[list[int]], solo_criticas: bool,
                        limite: int) -> tuple[list[Fila], int]:
        """Lista las alertas activas de la finca con su total."""
        return self._paginado(text(f"""
            SELECT a.id_alerta, a.tipo_alerta::text AS tipo, a.severidad::text AS severidad,
                   i.nombre AS area, a.tipo_variable AS variable, a.valor, a.unidad, a.fecha_generacion,
                   count(*) OVER () AS total
            FROM modulo3.alertas a
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            WHERE i.id_finca = :f AND {_ALERTA_VIGENTE} AND a.tipo_alerta <> 'TECNICA'
              AND (CAST(:areas AS int[]) IS NULL OR i.id_infraestructura = ANY(:areas))
              AND (NOT :solo OR a.severidad = 'CRITICO')
            ORDER BY (a.severidad = 'CRITICO') DESC, a.fecha_generacion DESC
            LIMIT :limite"""), {"f": id_finca, "areas": areas, "solo": solo_criticas, "limite": limite})

    def alertas_sanitarias(self, id_finca: int) -> list[Fila]:
        """Cuenta las alertas sanitarias de la finca por tipo."""
        return self._filas(text(f"""
            SELECT a.tipo_alerta::text AS tipo, count(*) AS total,
                   count(*) FILTER (WHERE a.severidad = 'CRITICO') AS criticas
            FROM modulo3.alertas a
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
            WHERE i.id_finca = :f AND {_ALERTA_VIGENTE} AND a.tipo_alerta::text IN {_TIPOS_SANITARIOS}
            GROUP BY 1
            ORDER BY 2 DESC"""), {"f": id_finca})

    def riesgo_alto(self, id_finca: int, especies: Optional[list[int]], limite: int) -> tuple[list[Fila], int]:
        """Lista los activos con riesgo alto con su total."""
        return self._paginado(text(f"""
            SELECT ab.id_activo_biologico, {nombre_activo_sql('ab')} AS activo, e.nombre AS especie,
                   i.nombre AS area, p.nombre AS patologia, ri.fecha_inferencia,
                   count(*) OVER () AS total
            FROM modulo2.activos_biologicos ab
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
            JOIN modulo9.especies e ON e.id_especie = ab.id_especie
            {_ULTIMA_INFERENCIA}
            LEFT JOIN modulo9.patologias p ON p.id_patologia = ri.id_patologia
            WHERE i.id_finca = :f AND ri.nivel_riesgo = 3 AND {_FILTRO_ESPECIES}
            ORDER BY ri.fecha_inferencia DESC
            LIMIT :limite"""), {"f": id_finca, "especies": especies, "horas": 24, "limite": limite})

    def distribucion_riesgo(self, id_finca: int, especies: Optional[list[int]], horas: int) -> list[Fila]:
        """Cuenta los activos por nivel de riesgo y especie en las últimas horas."""
        return self._filas(text(f"""
            SELECT e.nombre AS especie,
                   count(*) FILTER (WHERE ri.nivel_riesgo = 0) AS normal,
                   count(*) FILTER (WHERE ri.nivel_riesgo IN (1, 2)) AS moderado,
                   count(*) FILTER (WHERE ri.nivel_riesgo = 3) AS alto,
                   -- TC-DIS-279: la enfermedad más probable de la especie y su probabilidad (la inferencia de mayor
                   -- riesgo y confianza entre las de riesgo).
                   (array_agg(p.nombre ORDER BY ri.nivel_riesgo DESC, ri.confianza_global DESC)
                        FILTER (WHERE ri.nivel_riesgo > 0 AND p.nombre IS NOT NULL))[1] AS patologia,
                   (array_agg(ri.confianza_global::float ORDER BY ri.nivel_riesgo DESC, ri.confianza_global DESC)
                        FILTER (WHERE ri.nivel_riesgo > 0 AND p.nombre IS NOT NULL))[1] AS probabilidad
            FROM modulo2.activos_biologicos ab
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
            JOIN modulo9.especies e ON e.id_especie = ab.id_especie
            {_ULTIMA_INFERENCIA}
            LEFT JOIN modulo9.patologias p ON p.id_patologia = ri.id_patologia
            WHERE i.id_finca = :f AND {_FILTRO_ESPECIES}
            GROUP BY e.nombre
            ORDER BY e.nombre"""), {"f": id_finca, "especies": especies, "horas": horas})

    def retroalimentacion_pendiente(self, id_finca: int, id_usuario: int, hasta: datetime,
                                    limite: int) -> tuple[list[Fila], int]:
        """Lista las predicciones pendientes de retroalimentación del usuario."""
        pagina = ConsultarBandejaRetroalimentacionUseCase(
            SqlAlchemyBandejaRetroalimentacionRepository(self.db), SqlAlchemyParametrosMLOpsRepository(self.db),
        ).execute(ids_fincas=[id_finca], id_usuario=id_usuario, estado_evaluacion="PENDIENTE",
                  hasta=hasta, pagina=1, por_pagina=limite)
        return [{
            "id_activo_biologico": i.id_activo_biologico,
            "activo": i.identificador_activo,
            "especie": i.especie,
            "area": i.nombre_area,
            "nivel_riesgo": i.nivel_riesgo,
            "patologia": i.nombre_patologia,
            "fecha_inferencia": i.fecha_inferencia,
        } for i in pagina.items], pagina.total

    # --- Activos biológicos y suministros ---------------------------------------------------------

    def inventario(self, id_finca: int, especies: Optional[list[int]]) -> list[Fila]:
        """Cuenta los activos de la finca por especie y estado."""
        return self._filas(text(f"""
            SELECT e.nombre AS especie,
                   count(*) FILTER (WHERE est.nombre = 'ACTIVO') AS activos,
                   count(*) FILTER (WHERE est.nombre = 'EN_TRATAMIENTO') AS en_tratamiento,
                   count(*) FILTER (WHERE est.nombre = 'BAJA') AS bajas
            FROM modulo2.activos_biologicos ab
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
            JOIN modulo9.especies e ON e.id_especie = ab.id_especie
            JOIN modulo2.estados_activos_biologicos est ON est.id_estado_activo_biologico = ab.id_estado
            WHERE i.id_finca = :f AND {_FILTRO_ESPECIES}
            GROUP BY e.nombre
            ORDER BY e.nombre"""), {"f": id_finca, "especies": especies})

    def eventos(self, id_finca: int, limite: int) -> list[Fila]:
        """Lista los eventos recientes de la finca."""
        return self._filas(text(f"""
            SELECT ev.id_eventos AS id_evento, ev.fecha, {nombre_activo_sql('ab')} AS activo, e.nombre AS especie,
                   CASE WHEN es.id_evento IS NOT NULL THEN 'SANITARIO'
                        WHEN ep.id_evento IS NOT NULL THEN 'PRODUCTIVO'
                        WHEN eb.id_evento IS NOT NULL THEN 'BAJA'
                        WHEN ei.id_evento IS NOT NULL THEN 'INGRESO'
                        WHEN ec.id_evento IS NOT NULL THEN 'CRECIMIENTO'
                        WHEN er.id_evento_reproductivo IS NOT NULL THEN 'REPRODUCTIVO'
                        ELSE 'OTRO' END AS tipo
            FROM modulo2.eventos_activos ev
            JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ev.id_activo_biologico
            JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
            JOIN modulo9.especies e ON e.id_especie = ab.id_especie
            LEFT JOIN modulo2.eventos_sanitarios es ON es.id_evento = ev.id_eventos
            LEFT JOIN modulo2.eventos_productivos ep ON ep.id_evento = ev.id_eventos
            LEFT JOIN modulo2.eventos_bajas eb ON eb.id_evento = ev.id_eventos
            LEFT JOIN modulo2.eventos_ingresos ei ON ei.id_evento = ev.id_eventos
            LEFT JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ev.id_eventos
            LEFT JOIN modulo2.eventos_reproductivos er ON er.id_evento_reproductivo = ev.id_eventos
            WHERE i.id_finca = :f
            ORDER BY ev.fecha DESC, ev.id_eventos DESC
            LIMIT :limite"""), {"f": id_finca, "limite": limite})

    def conversion(self, id_finca: int, especies: Optional[list[int]]) -> list[Fila]:
        """Devuelve la conversión alimenticia por especie."""
        # Una fila por especie: la conversión de un estanque y la de un hato no se promedian entre sí.
        return self._filas(text(f"""
            WITH vigentes AS (
                SELECT DISTINCT ON (r.id_activo_biologico)
                       ab.id_especie, r.alimento_consumido_total_kg, r.ganancia_peso_kg,
                       r.clasificacion_ca::text AS clasificacion, r.fecha_fin_periodo
                FROM modulo5.resultado_ica r
                JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = r.id_activo_biologico
                JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
                WHERE i.id_finca = :f AND r.es_vigente AND r.ca_calculado IS NOT NULL AND {_FILTRO_ESPECIES}
                ORDER BY r.id_activo_biologico, r.fecha_fin_periodo DESC
            )
            SELECT e.nombre AS especie,
                   round(sum(v.alimento_consumido_total_kg) / NULLIF(sum(v.ganancia_peso_kg), 0), 2) AS valor,
                   count(*) AS activos,
                   count(*) FILTER (WHERE v.clasificacion IN ('BAJA', 'CRITICA')) AS en_alerta,
                   count(*) FILTER (WHERE v.clasificacion = 'CRITICA') AS criticos,
                   max(v.fecha_fin_periodo) AS fecha_fin_periodo
            FROM vigentes v
            JOIN modulo9.especies e ON e.id_especie = v.id_especie
            GROUP BY e.nombre
            ORDER BY e.nombre"""), {"f": id_finca, "especies": especies})

    # --- Finanzas e integración contable ---------------------------------------------------------

    def activos_valorados(self, id_finca: Optional[int],
                          fincas_permitidas: Optional[list[int]]) -> list[Fila]:
        """Lista los activos valorados de las fincas permitidas."""
        # INC-M08-380-G002: la RLS de modulo6 abre los reconocimientos y valoraciones solo a quien
        # lee la valoración en Finanzas, y el Productor no; con su sesión el widget le daba $0. Se lee
        # como sistema y el alcance lo pone el filtro de fincas (la regla de fn_fincas_del_usuario,
        # que como sistema ya no aplican los joins con activos y fincas).
        with como_sistema(self.db):
            filas = SqlAlchemyValoracionRepository(self.db).activos_valorados()
        return [f for f in filas
                if (id_finca is None or f["id_finca"] == id_finca)
                and (fincas_permitidas is None or f["id_finca"] in fincas_permitidas)]

    def periodos_abiertos(self, id_finca: Optional[int]) -> list[Fila]:
        """Lista los periodos contables abiertos."""
        return self._filas(text("""
            SELECT p.id_periodo_contable, p.fecha_inicio, p.fecha_fin, p.estado::text AS estado,
                   (SELECT f.razon_social FROM modulo9.fincas f
                    WHERE f.numero_id_tributaria = p.numero_id_tributaria AND f.razon_social IS NOT NULL
                    ORDER BY f.id_finca LIMIT 1) AS titular
            FROM modulo6.periodos_contables p
            WHERE p.estado IN ('ABIERTO', 'EN_CIERRE')
              AND (CAST(:f AS int) IS NULL OR p.numero_id_tributaria =
                   (SELECT numero_id_tributaria FROM modulo9.fincas WHERE id_finca = :f))
            ORDER BY p.fecha_fin, p.id_periodo_contable"""), {"f": id_finca})

    def sin_reconocimiento(self, id_finca: Optional[int]) -> list[Fila]:
        """Lista los activos sin reconocimiento contable."""
        return [{"id_activo_biologico": a.id_activo_biologico, "activo": a.identificador, "especie": a.especie,
                 "finca": a.finca, "fecha_ingreso": a.fecha_ingreso}
                for a in ActivoFinancieroM02Adapter(self.db).listar_sin_reconocimiento()
                if id_finca is None or a.id_finca == id_finca]

    def integraciones_fallidas(self, dias: int, limite: int) -> tuple[list[Fila], int]:
        """Lista las integraciones fallidas recientes con su total."""
        return self._paginado(text("""
            SELECT s.id_integracion_solicitud, s.estado::text AS estado, s.fecha_comienzoo AS fecha,
                   c.nombre AS cliente, count(*) OVER () AS total
            FROM modulo7.integraciones_solicitudes s
            LEFT JOIN modulo7.clientes_externos c ON c.id_cliente_externo = s.id_cliente_externo
            WHERE s.estado <> 'SUCCESS' AND s.fecha_comienzoo >= now() - make_interval(days => :dias)
            ORDER BY s.fecha_comienzoo DESC
            LIMIT :limite"""), {"dias": dias, "limite": limite})

    def precios_por_vencer(self, dias: int, limite: int) -> tuple[list[Fila], int]:
        """Lista los precios de mercado por vencer con su total."""
        return self._paginado(text("""
            SELECT pm.id_precio_mercado, e.nombre AS especie, pm.precio_unitario, pm.unidad_medida,
                   pm.fecha_vencimiento, pm.fecha_vencimiento - modulo1.fn_hoy_usuario() AS dias_restantes,
                   count(*) OVER () AS total
            FROM modulo6.precios_mercado pm
            JOIN modulo9.especies e ON e.id_especie = pm.id_especie
            WHERE pm.estado = 'ACTIVO'
              AND pm.fecha_vencimiento BETWEEN modulo1.fn_hoy_usuario() AND modulo1.fn_hoy_usuario() + :dias
            ORDER BY pm.fecha_vencimiento, e.nombre
            LIMIT :limite"""), {"dias": dias, "limite": limite})

    # --- Configuración ----------------------------------------------------------------------------

    def dispositivos(self, id_finca: int, areas: Optional[list[int]]) -> list[Fila]:
        """Lista los dispositivos de la finca con su última calibración."""
        return self._filas(text("""
            SELECT DISTINCT ON (v.id_dispositivo_iot)
                   v.id_dispositivo_iot, v.serial, v.area, v.ultima_calibracion,
                   COALESCE(ed.estado_actual::text, 'DESCONOCIDO') AS estado, ed.fecha_ultimo_contacto
            FROM modulo9.vw_rf28_widget_estado_dispositivos v
            LEFT JOIN modulo3.estados_dispositivos_iot ed ON ed.id_dispositivo_iot = v.id_dispositivo_iot
            WHERE v.id_finca = :f AND v.es_activo
              AND (CAST(:areas AS int[]) IS NULL OR v.id_infraestructura = ANY(:areas))
            ORDER BY v.id_dispositivo_iot, v.area"""), {"f": id_finca, "areas": areas})

    def configuracion_pendiente(self, id_finca: int, areas: Optional[list[int]]) -> list[Fila]:
        """Lista los dispositivos con configuración pendiente."""
        return self._filas(text("""
            SELECT id_dispositivo_iot, serial, descripcion, area
            FROM modulo9.vw_rf28_widget_dispositivos_sin_configuracion
            WHERE id_finca = :f AND (CAST(:areas AS int[]) IS NULL OR id_infraestructura = ANY(:areas))
            ORDER BY area, serial
            LIMIT 50"""), {"f": id_finca, "areas": areas})

    def estado_fincas(self, ids_fincas: Optional[list[int]]) -> list[Fila]:
        """Devuelve el estado general de las fincas."""
        return self._filas(text("""
            SELECT id_finca, nombre, es_activo, departamento, areas_activas, dispositivos_activos
            FROM modulo9.vw_rf28_widget_estado_fincas
            WHERE CAST(:ids AS int[]) IS NULL OR id_finca = ANY(:ids)
            ORDER BY nombre
            LIMIT 50"""), {"ids": ids_fincas})
