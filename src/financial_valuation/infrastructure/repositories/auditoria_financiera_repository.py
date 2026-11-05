# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-94: escritura y consulta de la auditoría financiera |
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

    def consultar(self, filtros: dict, pagina: int, tamano: int) -> tuple[int, list[dict]]:
        condiciones, params = ["true"], {"limite": tamano, "offset": (pagina - 1) * tamano}
        for campo, sql in (("tipo_evento", "a.tipo_evento::text = ANY(:tipo_evento)"),
                           ("id_activo_biologico", "a.id_activo_biologico = :id_activo_biologico"),
                           ("id_periodo_contable", "a.id_periodo_contable = :id_periodo_contable"),
                           ("severidad", "a.severidad::text = :severidad"), ("id_usuario", "a.id_usuario = :id_usuario"),
                           ("desde", "a.fecha_registro >= :desde"), ("hasta", "a.fecha_registro <= :hasta")):
            if filtros.get(campo) not in (None, [], ""):
                condiciones.append(sql)
                params[campo] = filtros[campo]
        donde = " AND ".join(condiciones)
        total = fila(self.db, f"SELECT count(*) AS n FROM modulo6.auditorias_financieras a WHERE {donde}", params)["n"]
        eventos = filas(self.db, f"""
            SELECT a.id_auditoria_financiera AS id_evento, a.tipo_evento::text AS tipo_evento, a.modulo_origen AS modulo,
                   a.fecha_registro AS timestamp_evento, a.tipo_actor::text AS tipo_actor, a.id_usuario,
                   trim(coalesce(u.nombre, '') || ' ' || coalesce(u.apellidos, '')) AS nombre_usuario, a.id_sistema,
                   a.id_activo_biologico, a.id_periodo_contable, a.id_referencia, a.datos_nuevos AS payload_evento,
                   a.datos_anteriores, a.severidad::text AS severidad_evento, a.hash_integridad,
                   a.es_payload_truncado AS payload_truncado, a.origen_registro, a.monto_afectado
            FROM modulo6.auditorias_financieras a LEFT JOIN modulo1.usuarios u ON u.id_usuario = a.id_usuario
            WHERE {donde} ORDER BY a.fecha_registro, a.id_auditoria_financiera LIMIT :limite OFFSET :offset
        """, params)
        return total, eventos
