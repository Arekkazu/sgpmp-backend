# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-94: escritura y consulta de la auditoría financiera |
# | 2026-11-05 | Arekkazu | M06 RF-94: orden descendente, conteo por severidad e identificador del activo |
# | 2026-11-08 | Arekkazu | INC-M06-330-G86 RF-94: filtros por usuario, referencia y origen del registro |
# | 2026-11-11 | Arekkazu | USAB-M05-M06 T-01 RF-75..94: el activo sin identificador se nombra «Lote N», nunca null |
# | 2026-11-13 | Arekkazu | QA-M06 CU13 H-01/H-02 C3 RF-94: precios en la bitácora del período y nombre del autor |
# | 2026-11-14 | Arekkazu | FILTRO-FINCA RF-94: bitácora filtrable por la finca del activo |
# | 2026-11-14 | Arekkazu | INC-M06-365-G93 RF-94: la auditoría se acota a los titulares de las fincas del usuario |
# | 2026-11-15 | Arekkazu | INC-M06-93-G44: el nombre de quien firmó cada evento sale de la ayuda compartida nombres_usuarios |
# | 2026-11-15 | Arekkazu | QA-M06 CU-COT H-01 RF-94: el alcance por fincas se comparte con las cotizaciones |
"""Implementación SQL de :class:`AuditoriaFinancieraRepository` sobre ``modulo6.auditorias_financieras``.

El hash SHA-256 lo calcula el trigger ``trg_hash_auditoria``; ``tgr_m06_27`` corre antes y exige
un valor de 64 caracteres, por eso se envía un marcador que el trigger reemplaza. La escritura va
en la misma transacción de la operación auditada (RF-86 RNF Fiabilidad)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.infrastructure.repositories.sql import (
    ES_ADMINISTRADOR as _ES_ADMINISTRADOR,
    PERIODOS_DE_MIS_FINCAS as _PERIODOS_PROPIOS,
    a_json,
    escribir,
    fila,
    filas,
    nombres_usuarios,
)
from src.shared.fechas import nombre_zona_usuario
from src.shared.nombre_activo import nombre_activo_sql

_LIMITE_PAYLOAD = 64 * 1024
_MARCADOR_HASH = "0" * 64

# Precios, matriz y parámetros valen para todos los titulares y se guardan sin período: la bitácora de un
# período muestra los registrados en sus fechas (CU13 H-01).
_GLOBALES = ["PRECIO_REGISTRADO", "PRECIO_MARCADO_REEMPLAZADO", "PRECIO_REFERENCIA_VENCIDO",
             "PARAMETRO_COSTOS_VENTA_ACTUALIZADO", "MATRIZ_CONTABLE_ACTUALIZADA", "CONFIGURACION_CONTABLE_ACTUALIZADA"]

# Filtros de RF-94 Fase 7 (en AND; uno vacío no filtra).
_FILTROS = (("tipo_evento", "a.tipo_evento::text = ANY(:tipo_evento)"),
            ("id_activo_biologico", "a.id_activo_biologico = :id_activo_biologico"),
            ("id_finca", """a.id_activo_biologico IN (SELECT ab.id_activo_biologico FROM modulo2.activos_biologicos ab
                JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura WHERE i.id_finca = :id_finca)"""),
            ("id_periodo_contable", """(a.id_periodo_contable = :id_periodo_contable OR (
                a.id_periodo_contable IS NULL AND a.tipo_evento::text = ANY(:globales) AND EXISTS (
                    SELECT 1 FROM modulo6.periodos_contables pc WHERE pc.id_periodo_contable = :id_periodo_contable
                      AND (a.fecha_registro AT TIME ZONE :tz)::date BETWEEN pc.fecha_inicio AND pc.fecha_fin)))"""),
            ("severidad", "a.severidad::text = :severidad"), ("id_usuario", "a.id_usuario = :id_usuario"),
            ("id_referencia", "a.id_referencia = :id_referencia"), ("origen_registro", "a.origen_registro = :origen_registro"),
            ("desde", "a.fecha_registro >= :desde"), ("hasta", "a.fecha_registro <= :hasta"))


# INC-M06-365-G93: cada quien ve la auditoría de los titulares de sus fincas, también quien lee el cierre (Contador,
# Revisor Fiscal); el Administrador protegido, toda. Las RLS de `modulo9.fincas` y `modulo2.activos_biologicos` ya
# acotan a las fincas asignadas. Lo global (precios, matriz, parámetros) y lo que firmó el propio usuario se ven siempre.
_ALCANCE = f"""({_ES_ADMINISTRADOR} OR a.id_usuario = modulo1.fn_id_usuario_actual()
    OR a.id_periodo_contable IN ({_PERIODOS_PROPIOS})
    OR (a.id_periodo_contable IS NULL AND (
        a.id_activo_biologico IN (SELECT ab.id_activo_biologico FROM modulo2.activos_biologicos ab)
        OR (a.id_activo_biologico IS NULL AND a.tipo_evento::text = ANY(:globales)))))"""


def _donde(filtros: dict) -> tuple[str, dict]:
    activos = [(campo, sql) for campo, sql in _FILTROS if filtros.get(campo) not in (None, [], "")]
    params = {campo: filtros[campo] for campo, _ in activos}
    params["globales"] = _GLOBALES
    if "id_periodo_contable" in params:
        params["tz"] = nombre_zona_usuario()
    return " AND ".join([_ALCANCE, *(sql for _, sql in activos)]), params


class SqlAlchemyAuditoriaFinancieraRepository(AuditoriaFinancieraRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(self, evento: EventoAuditoria) -> None:
        payload = a_json(evento.payload) or "{}"
        truncado = len(payload.encode("utf-8")) > _LIMITE_PAYLOAD
        if truncado:  # RF-94 R5 / FA-4
            payload = a_json({"resumen": payload[: _LIMITE_PAYLOAD // 2], "payload_truncado": True})
        escribir(self.db, """
            INSERT INTO modulo6.auditorias_financieras (
                tipo, tipo_evento, id_activo_biologico, modulo_origen, id_periodo_contable, monto_afectado,
                metodo_valoracion_anterior, metodo_valoracion_nuevo, datos_nuevos, datos_anteriores, severidad,
                id_usuario, tipo_actor, hash_integridad, origen_registro, id_referencia, id_sistema, es_payload_truncado)
            VALUES (
                CAST(:sev AS modulo6.enum_auditorias_financieras_severidad),
                CAST(:tipo AS modulo6.enum_auditoria_financiera_tipo_evento), :activo, 'M06', :periodo, :monto,
                CAST(:met_ant AS modulo6.enum_auditoria_financiera_metodo_valoracion),
                CAST(:met_nuevo AS modulo6.enum_auditoria_financiera_metodo_valoracion),
                CAST(:datos AS jsonb), CAST(:anteriores AS jsonb),
                CAST(:sev AS modulo6.enum_auditorias_financieras_severidad), :usuario,
                CAST(:actor AS modulo6.enum_actor_auditoria), :hash, 'REPOSITORIO', :ref, :sistema, :truncado)
        """, {
            "sev": evento.severidad, "tipo": evento.tipo_evento, "activo": evento.id_activo_biologico,
            "periodo": evento.id_periodo_contable, "monto": evento.monto_afectado, "met_ant": evento.metodo_anterior,
            "met_nuevo": evento.metodo_nuevo, "datos": payload, "anteriores": a_json(evento.datos_anteriores),
            "usuario": evento.id_usuario, "actor": "USUARIO" if evento.id_usuario else "SISTEMA",
            "hash": _MARCADOR_HASH, "ref": evento.id_referencia,
            "sistema": None if evento.id_usuario else (evento.id_sistema or "M06_PROCESO_AUTOMATICO"),
            "truncado": truncado,
        })

    def consultar(self, filtros: dict, pagina: int, tamano: int, descendente: bool = False) -> tuple[int, list[dict]]:
        donde, params = _donde(filtros)
        params.update(limite=tamano, offset=(pagina - 1) * tamano)
        orden = "DESC" if descendente else "ASC"
        total = fila(self.db, f"SELECT count(*) AS n FROM modulo6.auditorias_financieras a WHERE {donde}", params)["n"]
        eventos = filas(self.db, f"""
            SELECT a.id_auditoria_financiera AS id_evento, a.tipo_evento::text AS tipo_evento, a.modulo_origen AS modulo,
                   a.fecha_registro AS timestamp_evento, a.tipo_actor::text AS tipo_actor, a.id_usuario, a.id_sistema,
                   a.id_activo_biologico, a.id_periodo_contable, a.id_referencia, a.datos_nuevos AS payload_evento,
                   a.datos_anteriores, a.severidad::text AS severidad_evento, a.hash_integridad,
                   a.es_payload_truncado AS payload_truncado, a.origen_registro, a.monto_afectado,
                   {nombre_activo_sql('ab')} AS identificador_activo
            FROM modulo6.auditorias_financieras a
            LEFT JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = a.id_activo_biologico
            WHERE {donde} ORDER BY a.fecha_registro {orden}, a.id_auditoria_financiera {orden} LIMIT :limite OFFSET :offset
        """, params)
        nombres = nombres_usuarios(self.db, (e["id_usuario"] for e in eventos))
        for e in eventos:
            e["nombre_usuario"] = nombres.get(e["id_usuario"]) or ""
        return total, eventos

    def actores(self, filtros: dict) -> list[dict]:
        donde, params = _donde(filtros)
        ids = {f["id_usuario"] for f in filas(self.db, f"""SELECT DISTINCT a.id_usuario FROM modulo6.auditorias_financieras a
                                                         WHERE {donde} AND a.id_usuario IS NOT NULL""", params)}
        nombres = nombres_usuarios(self.db, ids)
        return sorted(({"id_usuario": i, "nombre": nombres.get(i) or "Usuario sin nombre registrado"} for i in ids),
                      key=lambda a: a["nombre"].lower())

    def en_alcance(self, id_periodo_contable: Optional[int], id_activo_biologico: Optional[int]) -> bool:
        return fila(self.db, f"""SELECT {_ES_ADMINISTRADOR}
            OR ((CAST(:p AS integer) IS NULL OR :p IN ({_PERIODOS_PROPIOS}))
                AND (CAST(:a AS integer) IS NULL OR :a IN (SELECT ab.id_activo_biologico FROM modulo2.activos_biologicos ab)))
            AS ok""", {"p": id_periodo_contable, "a": id_activo_biologico})["ok"]

    def conteo_por_severidad(self, filtros: dict) -> dict[str, int]:
        """Eventos por severidad con los mismos filtros de la consulta, sin el de severidad."""
        sin_severidad = {k: v for k, v in filtros.items() if k != "severidad"}
        donde, params = _donde(sin_severidad)
        conteo = {s: 0 for s in ("INFO", "WARNING", "ERROR", "CRITICAL")}
        for f in filas(self.db, f"""SELECT a.severidad::text AS severidad, count(*) AS n FROM modulo6.auditorias_financieras a
                                   WHERE {donde} GROUP BY 1""", params):
            conteo[f["severidad"]] = f["n"]
        return conteo
