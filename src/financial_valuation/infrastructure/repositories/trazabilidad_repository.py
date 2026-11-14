# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-91: eslabones de la cadena telemetría → evento → valoración → línea |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-288-G32 RF-91: una cadena de período cerrado no aborta la verificación |
# | 2026-11-13 | Leandro | TC-M06-G52 RF-91: comprobar y guardar los vínculos con RF-52, RF-63 y RF-73. |
"""Implementación SQL de :class:`TrazabilidadRepository`.

Nivel 1: lectura vinculada al activo, apta en RF-62 y auditada en RF-63. Nivel 2: evento
del activo respaldado por RF-52 o evidencia sanitaria respaldada por RF-73, según el origen.
Nivel 3: precio con evidencia documental y justificación si es ESTIMADA. Nivel 4: registro
que originó la línea."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import LineaAsiento
from src.financial_valuation.domain.repositories.trazabilidad_repository import TrazabilidadRepository
from src.financial_valuation.domain.services.trazabilidad import AUDITORIAS_REQUERIDAS
from src.financial_valuation.infrastructure.repositories.sql import a_json, escribir, fila
from src.shared.database import como_sistema

logger = logging.getLogger(__name__)

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

    def _consultar_fuente(self, resultado: dict, eslabon: str, sql: str, parametros: dict) -> Optional[dict]:
        try:
            with self.db.begin_nested():
                with como_sistema(self.db):
                    # Restaurar la identidad después de revertir una consulta fallida.
                    with self.db.begin_nested():
                        return fila(self.db, sql, parametros)
        except DBAPIError as exc:
            if exc.connection_invalidated:
                raise
            logger.warning("RF-91: fuente %s no consultable (SQLSTATE %s).", eslabon, getattr(exc.orig, "pgcode", None))
            resultado.setdefault("fuentes_no_disponibles", []).append(eslabon)
            return None

    def _auditoria_m02(self, resultado, id_evento, id_activo):
        auditoria = self._consultar_fuente(resultado, "auditoria_m02", """
            SELECT id_evento FROM modulo2.bitacora_auditoria_m02
             WHERE id_activo_biologico = :activo AND resultado = 'EXITOSO'
               AND registro_incompleto IS FALSE
               AND detalle_tecnico->'registros_rf46' @> jsonb_build_array(
                   jsonb_build_object('tabla', 'eventos_activos', 'id', CAST(:evento AS integer)))
             ORDER BY timestamp_registro DESC, id_bitacora DESC LIMIT 1
        """, {"activo": id_activo, "evento": id_evento})
        resultado["auditoria_m02"] = auditoria is not None
        if auditoria:
            resultado["ids"]["id_auditoria_m02"] = auditoria["id_evento"]

    def _lecturas_iot(self, resultado, id_activo, fecha):
        lecturas = self._consultar_fuente(resultado, "lecturas_nic41", """
            WITH aptas AS (
                SELECT t.id_telemetria, t.timestamp_captura
                  FROM modulo3.telemetrias t
                  JOIN modulo3.telemetria_calidad q
                    ON q.id_telemetria = t.id_telemetria AND q.id_sensor = t.id_sensor
                  LEFT JOIN modulo3.vinculaciones_lecturas v
                    ON v.id_telemetria = t.id_telemetria AND v.fecha_fin_vinculacion IS NULL
                 WHERE q.estado_evaluacion = 'VIGENTE' AND q.apto_para_nic41
                   AND t.timestamp_captura BETWEEN :fecha - interval '24 hours' AND :fecha + interval '1 hour'
                   AND (
                       (v.id_activo_biologico = :activo AND v.estado_vinculacion = 'CONFIRMADA')
                       OR (v.id_telemetria IS NULL AND EXISTS (
                           SELECT 1 FROM modulo2.asociaciones_activos_sensores s
                            WHERE s.id_activo_biologico = :activo AND s.id_sensor = t.id_sensor
                              AND (s.dispositivo_iot_id IS NULL OR s.dispositivo_iot_id = t.id_dispositivo_iot)
                              AND s.fecha_inicio <= t.timestamp_captura
                              AND (s.fecha_fin IS NULL OR t.timestamp_captura < s.fecha_fin)
                       ))
                   )
                 ORDER BY t.timestamp_captura DESC, t.id_telemetria DESC LIMIT 20
            )
            SELECT array_agg(id_telemetria ORDER BY timestamp_captura DESC, id_telemetria DESC) AS ids
              FROM aptas
        """, {"activo": id_activo, "fecha": fecha})
        ids = (lecturas or {}).get("ids") or []
        resultado["lecturas_nic41"] = bool(ids)
        resultado["ids"]["ids_lectura_iot"] = ids
        if not ids:
            return
        auditoria = self._consultar_fuente(resultado, "auditoria_m03", """
            SELECT id_evento, entidad_afectada_id FROM modulo3.bitacora_auditoria_iot
             WHERE entidad_afectada_id = ANY(:ids)
               AND ((entidad_afectada_tipo = 'CALIDAD_DATO' AND tipo_evento = 'EVALUACION_CALIDAD_COMPLETADA')
                    OR (entidad_afectada_tipo = 'LECTURA' AND tipo_evento IN
                        ('POSTCOMMIT_RF53_AUDITORIA_COMPLETADO', 'POSTCOMMIT_RF62_COMPLETADO')))
               AND resultado IN ('EXITOSO', 'PARCIAL') AND registro_incompleto IS FALSE
             ORDER BY fecha_hora DESC, id_evento DESC LIMIT 1
        """, {"ids": [str(id_lectura) for id_lectura in ids]})
        resultado["auditoria_m03"] = auditoria is not None
        if auditoria:
            resultado["ids"]["id_auditoria_m03"] = auditoria["id_evento"]
            resultado["ids"]["id_lectura_auditada"] = int(auditoria["entidad_afectada_id"])

    def _auditoria_m04(self, resultado, id_activo, fecha):
        auditoria = self._consultar_fuente(resultado, "auditoria_m04", """
            SELECT id_evento FROM modulo4.eventos_auditoria_m04
             WHERE tipo_evento = 'INFERENCIA_EJECUTADA' AND resultado_operacion = 'EXITOSO'
               AND entidad_referencia = 'resultado_inferencia'
               AND NOT es_payload_truncado AND NULLIF(hash_evento, '') IS NOT NULL
               AND payload_evento @> jsonb_build_object('activo_biologico_id', CAST(:activo AS integer))
               AND fecha_evento >= date_trunc('day', CAST(:fecha AS timestamptz), 'America/Bogota')
               AND fecha_evento < date_trunc('day', CAST(:fecha AS timestamptz), 'America/Bogota') + interval '24 hours'
             ORDER BY abs(extract(epoch FROM fecha_evento - CAST(:fecha AS timestamptz))), id_evento LIMIT 1
        """, {"activo": id_activo, "fecha": fecha})
        resultado["auditoria_m04"] = auditoria is not None
        if auditoria:
            resultado["ids"]["id_auditoria_m04"] = auditoria["id_evento"]

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
        resultado.update(dict.fromkeys(AUDITORIAS_REQUERIDAS.get(linea.tipo_evidencia, ()), False))
        if linea.tipo_evidencia == "IOT_DIRECTO":
            resultado["lecturas_nic41"] = False
            resultado["evento_m02"] = False
        if origen is None:
            return resultado
        if linea.tabla_origen == "variaciones_valor_razonable":
            # Navegación al origen aunque la cadena no lo vincule por FK (línea arrastrada de un período cerrado).
            resultado["ids"]["id_variacion_valor_razonable"] = linea.id_origen
        id_evento = origen.get(col_evento) if col_evento else None
        if linea.tabla_origen == "procesamientos_eventos_m02":
            id_evento = linea.id_origen
        if linea.tabla_origen == "deterioros_activos":
            ok = fila(self.db, """SELECT ea.fecha FROM modulo2.eventos_sanitarios es
                                  JOIN modulo2.eventos_activos ea ON ea.id_eventos = es.id_evento
                                  WHERE es.id_evento = :e AND ea.id_activo_biologico = :a""",
                      {"e": id_evento, "a": linea.id_activo_biologico})
            resultado["evento_sanitario"] = ok is not None
            if ok is not None and linea.tipo_evidencia == "EVENTO_SANITARIO":
                resultado["ids"]["id_evento_sanitario"] = id_evento
                self._auditoria_m04(resultado, linea.id_activo_biologico, ok["fecha"])
            id_evento = None
        if id_evento is not None:
            evento = fila(self.db, """SELECT ea.id_eventos, ea.fecha FROM modulo2.eventos_activos ea
                                      WHERE ea.id_eventos = :e AND ea.id_activo_biologico = :a""",
                          {"e": id_evento, "a": linea.id_activo_biologico})
            resultado["evento_m02"] = evento is not None
            resultado["ids"]["id_evento"] = id_evento
            if evento is not None:
                if "auditoria_m02" in resultado:
                    self._auditoria_m02(resultado, id_evento, linea.id_activo_biologico)
                if linea.tipo_evidencia == "IOT_DIRECTO":
                    self._lecturas_iot(resultado, linea.id_activo_biologico, evento["fecha"])
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
              "p": eslabones.get("ids", {}).get("id_precio_mercado"),
              "estado": "PENDIENTE" if estado == "VERIFICACION_PENDIENTE" else _ESTADO_VERIFICACION[nivel],
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
