# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-94: escritura y consulta de la auditoría financiera |
# | 2026-11-05 | Arekkazu | M06 RF-94: orden descendente, conteo por severidad e identificador del activo |
# | 2026-11-08 | Arekkazu | INC-M06-330-G86 RF-94: filtros por usuario, referencia y origen del registro |
"""Implementación SQL de :class:`AuditoriaFinancieraRepository` sobre ``modulo6.auditorias_financieras``.

El hash SHA-256 lo calcula el trigger ``trg_hash_auditoria``; ``tgr_m06_27`` corre antes y exige
un valor de 64 caracteres, por eso se envía un marcador que el trigger reemplaza. La escritura va
en la misma transacción de la operación auditada (RF-86 RNF Fiabilidad)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.infrastructure.repositories.sql import a_json, escribir, fila, filas

_LIMITE_PAYLOAD = 64 * 1024
_MARCADOR_HASH = "0" * 64

# Filtros de RF-94 Fase 7 (en AND; uno vacío no filtra).
_FILTROS = (("tipo_evento", "a.tipo_evento::text = ANY(:tipo_evento)"),
            ("id_activo_biologico", "a.id_activo_biologico = :id_activo_biologico"),
            ("id_periodo_contable", "a.id_periodo_contable = :id_periodo_contable"),
            ("severidad", "a.severidad::text = :severidad"), ("id_usuario", "a.id_usuario = :id_usuario"),
            ("id_referencia", "a.id_referencia = :id_referencia"), ("origen_registro", "a.origen_registro = :origen_registro"),
            ("desde", "a.fecha_registro >= :desde"), ("hasta", "a.fecha_registro <= :hasta"))


def _donde(filtros: dict) -> tuple[str, dict]:
    activos = [(campo, sql) for campo, sql in _FILTROS if filtros.get(campo) not in (None, [], "")]
    return " AND ".join(["true", *(sql for _, sql in activos)]), {campo: filtros[campo] for campo, _ in activos}


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
                   a.fecha_registro AS timestamp_evento, a.tipo_actor::text AS tipo_actor, a.id_usuario,
                   trim(coalesce(u.nombre, '') || ' ' || coalesce(u.apellidos, '')) AS nombre_usuario, a.id_sistema,
                   a.id_activo_biologico, a.id_periodo_contable, a.id_referencia, a.datos_nuevos AS payload_evento,
                   a.datos_anteriores, a.severidad::text AS severidad_evento, a.hash_integridad,
                   a.es_payload_truncado AS payload_truncado, a.origen_registro, a.monto_afectado,
                   ab.identificador AS identificador_activo
            FROM modulo6.auditorias_financieras a LEFT JOIN modulo1.usuarios u ON u.id_usuario = a.id_usuario
            LEFT JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = a.id_activo_biologico
            WHERE {donde} ORDER BY a.fecha_registro {orden}, a.id_auditoria_financiera {orden} LIMIT :limite OFFSET :offset
        """, params)
        return total, eventos

    def conteo_por_severidad(self, filtros: dict) -> dict[str, int]:
        """Eventos por severidad con los mismos filtros de la consulta, sin el de severidad."""
        sin_severidad = {k: v for k, v in filtros.items() if k != "severidad"}
        donde, params = _donde(sin_severidad)
        conteo = {s: 0 for s in ("INFO", "WARNING", "ERROR", "CRITICAL")}
        for f in filas(self.db, f"""SELECT a.severidad::text AS severidad, count(*) AS n FROM modulo6.auditorias_financieras a
                                   WHERE {donde} GROUP BY 1""", params):
            conteo[f["severidad"]] = f["n"]
        return conteo
