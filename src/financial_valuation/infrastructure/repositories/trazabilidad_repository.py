# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-91: eslabones de la cadena telemetría → evento → valoración → línea |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-288-G32 RF-91: una cadena de período cerrado no aborta la verificación |
"""Implementación SQL de :class:`TrazabilidadRepository`.

Nivel 1 (IoT): lecturas del dispositivo del activo marcadas ``apto_para_nic41`` en RF-62, en las
24 h previas al evento. Nivel 2: el evento existe en M02 y es del mismo activo de la línea
(coherencia semántica, RF-91 R6). Nivel 3: el precio usado existe y tiene evidencia documental
(y justificación si es ESTIMADA). Nivel 4: el registro que originó la línea existe."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import LineaAsiento
from src.financial_valuation.domain.repositories.trazabilidad_repository import TrazabilidadRepository
from src.financial_valuation.infrastructure.repositories.sql import a_json, escribir, fila

_ORIGENES = {  # tabla de origen -> (PK, columna de evento, columna de precio)
    "variaciones_valor_razonable": ("id_variacion_valor_razonable", "id_evento", "id_precio_mercado"),
    "reconocimientos_iniciales": ("id_reconocimiento_inicial", None, "id_precio_mercado"),
    "reconocimientos_productos_agricolas": ("id_reconocimiento_producto_agricola", "id_evento_productivo", None),
    "registros_costos": ("id_registro_costo", None, None),
    "revisiones_reconocimiento": ("id_revision_reconocimiento", None, None),
    "valoraciones_por_costos": ("id_valoracion_por_costo", None, None),
    "deterioros_activos": ("id_deterioro_activo", "id_evento_sanitario", None),
    "procesamientos_eventos_m02": ("id_evento", "id_evento", None),
}
_ESTADO_VERIFICACION = {None: "VERIFICADO", 1: "FALLO_NIVEL_1", 2: "FALLO_NIVEL_2", 3: "FALLO_NIVEL_3", 4: "FALLO_NIVEL_3"}


class SqlAlchemyTrazabilidadRepository(TrazabilidadRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def eslabones(self, linea: LineaAsiento) -> dict:
        pk, col_evento, col_precio = _ORIGENES.get(linea.tabla_origen, (None, None, None))
        origen = None
        if pk is not None:
            tabla = "modulo2.eventos_activos" if linea.tabla_origen == "procesamientos_eventos_m02" else f"modulo6.{linea.tabla_origen}"
            columna = "id_eventos" if tabla == "modulo2.eventos_activos" else pk
            columnas = ", ".join(c for c in {columna, col_evento if tabla != 'modulo2.eventos_activos' else None, col_precio} if c)
            origen = fila(self.db, f"SELECT {columnas} FROM {tabla} WHERE {columna} = :id", {"id": linea.id_origen})
        resultado: dict = {"origen": origen is not None, "evento_m02": None, "lecturas_nic41": None,
                           "precio_documentado": None, "cierre": None, "evento_sanitario": None, "ids": {}}
        if origen is None:
            return resultado
        if linea.tabla_origen == "variaciones_valor_razonable":
            # Navegación al origen aunque la cadena no lo vincule por FK (línea arrastrada de un período cerrado).
            resultado["ids"]["id_variacion_valor_razonable"] = linea.id_origen
        id_evento = origen.get(col_evento) if col_evento else None
        if linea.tabla_origen == "procesamientos_eventos_m02":
            id_evento = linea.id_origen
        if linea.tabla_origen == "deterioros_activos":
            ok = fila(self.db, """SELECT 1 AS ok FROM modulo2.eventos_sanitarios es
                                  JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
                                  WHERE es.id_evento = :e AND ea.id_activo_biologico = :a""",
                      {"e": id_evento, "a": linea.id_activo_biologico})
            resultado["evento_sanitario"] = ok is not None
            id_evento = None
        if id_evento is not None:
            evento = fila(self.db, """SELECT ea.id_eventos, ea.fecha, a.id_dispositivo_iot FROM modulo2.eventos_activos ea
                                      JOIN modulo2.activos_biologicos a ON a.id_activo_biologico = ea.id_activo_biologico
                                      WHERE ea.id_eventos = :e AND ea.id_activo_biologico = :a""",
                          {"e": id_evento, "a": linea.id_activo_biologico})
            resultado["evento_m02"] = evento is not None
            resultado["ids"]["id_evento"] = id_evento
            if evento is not None and linea.tipo_evidencia == "IOT_DIRECTO":
                lecturas = fila(self.db, """
                    SELECT array_agg(t.id_telemetria ORDER BY t.timestamp_captura DESC) AS ids, count(*) AS n
                    FROM (SELECT id_telemetria, timestamp_captura FROM modulo3.telemetrias
                          WHERE id_dispositivo_iot = :d AND apto_para_nic41
                            AND timestamp_captura BETWEEN :f - interval '24 hours' AND :f + interval '1 hour'
                          ORDER BY timestamp_captura DESC LIMIT 20) t""",
                                {"d": evento["id_dispositivo_iot"], "f": evento["fecha"]})
                resultado["lecturas_nic41"] = bool(lecturas and lecturas["n"])
                resultado["ids"]["ids_lectura_iot"] = (lecturas or {}).get("ids") or []
        id_precio = origen.get(col_precio) if col_precio else None
        if id_precio is not None:
            precio = fila(self.db, """SELECT id_precio_mercado FROM modulo6.precios_mercado WHERE id_precio_mercado = :p
                                        AND length(trim(evidencia)) > 0
                                        AND (fuente <> 'ESTIMADA' OR length(trim(coalesce(justificacion, ''))) > 0)""",
                          {"p": id_precio})
            resultado["precio_documentado"] = precio is not None
            resultado["ids"]["id_precio_mercado"] = id_precio
        if linea.tipo_evidencia == "CIERRE_PERIODO" and linea.tabla_origen == "variaciones_valor_razonable":
            cierre = fila(self.db, """SELECT v.id_cierre FROM modulo6.variaciones_valor_razonable v
                                      JOIN modulo6.ejecuciones_cierre_periodo e ON e.id_cierre = v.id_cierre
                                      WHERE v.id_variacion_valor_razonable = :id""", {"id": linea.id_origen})
            resultado["cierre"] = cierre is not None
        return resultado

    def registrar_verificacion(self, id_linea, estado, tipo_evidencia, eslabones, id_usuario) -> None:
        """Una cadena nueva por verificación, en su propio savepoint.

        INC-M06-288-G32: el cierre (RF-87 paso 3) pasa al período siguiente las líneas con la trazabilidad
        incompleta, pero su variación se queda en el período CERRADO. TGR-M06-26 (RF-91 R4) prohíbe
        escribir cadenas vinculadas a esa variación, así que la cadena nueva de la línea arrastrada se
        vincula solo a la línea (el id de la variación queda en ``json_eslabones``). El savepoint hace que
        un rechazo de la BD deshaga solo esta línea y no la verificación entera del período.
        """
        nivel = eslabones.get("nivel_fallo")
        with self.db.begin_nested():
            self._insertar_cadena(id_linea, estado, tipo_evidencia, eslabones, id_usuario, nivel)

    def _insertar_cadena(self, id_linea, estado, tipo_evidencia, eslabones, id_usuario, nivel) -> None:
        escribir(self.db, """
            INSERT INTO modulo6.cadenas_trazabilidad_contable (id_variacion_valor_razonable, id_evento, id_precio_mercado,
                estado_verificacion, nivel_fallo, fecha_verificacion, verificado_por, justificacion_verificacion,
                id_linea_asiento_nic41, tipo_evidencia_origen, json_eslabones)
            SELECT CASE WHEN l.tabla_origen = 'variaciones_valor_razonable'
                         AND pc.estado IS DISTINCT FROM 'CERRADO' THEN l.id_origen END, :e, :p,
                   CAST(:estado AS modulo6.enum_estado_verificacion), :nivel, now(), :u, :j, l.id_linea_asiento_nic41, :t,
                   CAST(:es AS jsonb)
            FROM modulo6.lineas_asiento_nic41 l
            LEFT JOIN modulo6.variaciones_valor_razonable v
                   ON l.tabla_origen = 'variaciones_valor_razonable' AND v.id_variacion_valor_razonable = l.id_origen
            LEFT JOIN modulo6.periodos_contables pc ON pc.id_periodo_contable = v.id_periodo_contable
            WHERE l.id_linea_asiento_nic41 = :id
        """, {"id": id_linea, "e": eslabones.get("ids", {}).get("id_evento"),
              "p": eslabones.get("ids", {}).get("id_precio_mercado"), "estado": _ESTADO_VERIFICACION.get(nivel, "PENDIENTE"),
              "nivel": nivel, "u": id_usuario, "j": ", ".join(eslabones.get("faltantes", [])) or None, "t": tipo_evidencia,
              "es": a_json(eslabones)})

    def cadena(self, id_linea: int) -> Optional[dict]:
        return fila(self.db, """
            SELECT l.id_linea_asiento_nic41, l.tipo_hecho::text AS tipo_hecho, l.sentido::text AS sentido, l.valor,
                   l.tabla_origen, l.id_origen, l.tipo_evidencia, l.estado_trazabilidad::text AS estado_trazabilidad,
                   l.id_activo_biologico, l.fecha_hecho, l.cuenta_debito, l.cuenta_credito,
                   c.estado_verificacion::text AS estado_verificacion, c.nivel_fallo, c.fecha_verificacion,
                   c.justificacion_verificacion AS eslabones_faltantes, c.json_eslabones AS eslabones
            FROM modulo6.lineas_asiento_nic41 l
            LEFT JOIN LATERAL (SELECT * FROM modulo6.cadenas_trazabilidad_contable c
                               WHERE c.id_linea_asiento_nic41 = l.id_linea_asiento_nic41
                               ORDER BY c.id_asiento DESC LIMIT 1) c ON true
            WHERE l.id_linea_asiento_nic41 = :id""", {"id": id_linea})
