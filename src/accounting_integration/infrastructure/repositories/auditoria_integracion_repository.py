# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-102: persistencia append-only de la auditoría de integración |
"""Auditoría de M07 en ``modulo7.eventos_integracion`` (RF-102). Los triggers bloquean UPDATE,
DELETE y TRUNCATE; aquí solo se inserta y se consulta."""
from __future__ import annotations

import logging
from dataclasses import fields
from typing import Callable

from sqlalchemy.orm import Session

from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import (
    AuditoriaIntegracionRepository,
    FiltrosAuditoria,
)
from src.financial_valuation.infrastructure.repositories.sql import a_json, escribir, filas
from src.shared.errors import InfrastructureError

logger = logging.getLogger(__name__)

_CAMPOS = [f.name for f in fields(EventoIntegracion)]
_ENUMS = {"tipo_evento": "enum_evento_integracion_tipo_evento", "severidad": "enum_evento_integracion_severidad",
          "tipo_actor": "enum_evento_integracion_tipo_actor"}


def _valor(campo: str) -> str:
    if campo in _ENUMS:
        return f"CAST(:{campo} AS modulo7.{_ENUMS[campo]})"
    if campo in ("id_evento_integracion", "id_solicitud"):
        return f"CAST(:{campo} AS uuid)"
    if campo == "json_detalle":
        return "CAST(:json_detalle AS jsonb)"
    return f":{campo}"


_INSERT = (f"INSERT INTO modulo7.eventos_integracion ({', '.join(_CAMPOS)}, hash_integridad) "
           f"VALUES ({', '.join(_valor(c) for c in _CAMPOS)}, :hash_integridad)")
_SELECT = ", ".join(f"e.{c}::text AS {c}" if c in _ENUMS or c in ("id_evento_integracion", "id_solicitud") else f"e.{c}"
                    for c in _CAMPOS) + ", e.hash_integridad, u.correo_electronico AS correo_usuario, ce.nombre AS nombre_cliente"


class SqlAlchemyAuditoriaIntegracionRepository(AuditoriaIntegracionRepository):
    def __init__(self, db: Session):
        self.db = db

    def registrar(self, evento: EventoIntegracion) -> None:
        faltantes = evento.faltantes()
        if faltantes:  # RF-102 FA-8: no se guardan registros incompletos
            raise InfrastructureError(code="AUDITORIA_INCOMPLETA",
                                      message=f"Evento {evento.tipo_evento} sin {', '.join(faltantes)}.")
        params = {c: getattr(evento, c) for c in _CAMPOS}
        params["json_detalle"] = a_json(evento.json_detalle)
        params["hash_integridad"] = evento.hash_integridad
        escribir(self.db, _INSERT, params)

    def consultar(self, filtros: FiltrosAuditoria, pagina: int, tamano: int) -> tuple[list[tuple[EventoIntegracion, str, dict]], int]:
        condiciones, params = [], {"limite": tamano, "desplazamiento": (pagina - 1) * tamano}
        if filtros.tipos_evento:
            condiciones.append("e.tipo_evento::text = ANY(:tipos)")
            params["tipos"] = list(filtros.tipos_evento)
        for campo, valor, sql in (
            ("cliente", filtros.id_cliente_externo, "e.id_cliente_externo = :cliente"),
            ("desde", filtros.desde, "e.fecha_evento >= CAST(:desde AS date)"),
            ("hasta", filtros.hasta, "e.fecha_evento < CAST(:hasta AS date) + 1"),
            ("endpoint", filtros.endpoint, "e.endpoint = :endpoint"),
            ("codigo_http", filtros.codigo_http, "e.codigo_http = :codigo_http"),
        ):
            if valor is not None:
                condiciones.append(sql)
                params[campo] = valor
        if filtros.solo_exitosos:
            condiciones.append("e.codigo_resultado = 'OK'")
        donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        resultado = filas(self.db, f"""
            SELECT {_SELECT}, count(*) OVER () AS total FROM modulo7.eventos_integracion e
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = e.id_usuario
            LEFT JOIN modulo7.clientes_externos ce ON ce.id_cliente_externo = e.id_cliente_externo
            {donde} ORDER BY e.fecha_evento DESC, e.id_evento_integracion LIMIT :limite OFFSET :desplazamiento
        """, params)
        total = resultado[0]["total"] if resultado else 0
        return [(EventoIntegracion(**{c: f[c] for c in _CAMPOS}), f["hash_integridad"],
                 {"correo_usuario": f["correo_usuario"], "nombre_cliente": f["nombre_cliente"]}) for f in resultado], total


def registrador_aparte(session_factory: Callable[[], Session], alertar: Callable[[str, dict], None]) -> Callable[[EventoIntegracion], None]:
    """RF-102 4.1 para las lecturas: el evento va en su propia sesión y, si falla, la respuesta sale igual;
    queda en el log técnico y se alerta al Administrador (RF-95 FA-9)."""
    def registrar(evento: EventoIntegracion) -> None:
        db = session_factory()
        try:
            SqlAlchemyAuditoriaIntegracionRepository(db).registrar(evento)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.exception("No se pudo registrar el evento de integración %s.", evento.tipo_evento)
            alertar("No se pudo guardar un registro de la auditoría de la integración contable.",
                    {"tipo_evento": evento.tipo_evento, "id_solicitud": evento.id_solicitud, "error": type(exc).__name__})
        finally:
            db.close()

    return registrar
