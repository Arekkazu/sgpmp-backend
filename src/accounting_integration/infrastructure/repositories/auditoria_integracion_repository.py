# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-102: persistencia append-only de la auditoría de integración |
# | 2026-11-14 | Arekkazu | FILTRO-FINCA RF-98: la auditoría de la integración se filtra por el titular (NIT) de una finca del usuario |
# | 2026-11-19 | Leandro | INC-M07-371-G58 RF-102: consultar los dos almacenes y trasladar lotes elegibles. |
# | 2026-11-19 | Arekkazu | M7-11 RF-102: nombre de quien actuó, además del correo |
# | 2026-11-20 | Arekkazu | QA-M07 CU07 H-01 RF-102: Desde/Hasta en la zona del usuario, no en días UTC |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Persistencia de auditoría M07 y acceso al archivo de RF-102. Los triggers bloquean UPDATE, DELETE y
TRUNCATE; aquí solo se inserta, se consulta y se traslada al archivo con la función de BD."""
from __future__ import annotations

import logging
from dataclasses import fields
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import (
    AuditoriaIntegracionRepository,
    FiltrosAuditoria,
)
from src.financial_valuation.infrastructure.repositories.sql import a_json, escribir, filas, nombres_usuarios
from src.shared.errors import InfrastructureError
from src.shared.fechas import fin_dia_usuario, inicio_dia_usuario

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
_COLUMNAS_EVENTO = ", ".join(
    f"e.{c}::text AS {c}" if c in _ENUMS or c in ("id_evento_integracion", "id_solicitud") else f"e.{c}"
    for c in _CAMPOS
) + ", e.hash_integridad"
_SELECT = _COLUMNAS_EVENTO + ", u.correo_electronico AS correo_usuario, ce.nombre AS nombre_cliente"
_VENCIMIENTO = "modulo7.fn_fin_retencion_rf102(e.tipo_evento, e.fecha_evento, e.fecha_registro)"


def _evento(fila: dict) -> EventoIntegracion:
    datos = {c: fila[c] for c in _CAMPOS}
    for campo in ("fecha_evento", "fecha_registro"):
        datos[campo] = datos[campo].astimezone(timezone.utc)
    return EventoIntegracion(**datos)


class SqlAlchemyAuditoriaIntegracionRepository(AuditoriaIntegracionRepository):
    """Implementación SQLAlchemy de la auditoría de integración."""
    def __init__(self, db: Session):
        self.db = db

    def registrar(self, evento: EventoIntegracion) -> None:
        """Registra el evento con su hash.

        Raises:
            InfrastructureError: Si el evento está incompleto.
        """
        faltantes = evento.faltantes()
        if faltantes:  # RF-102 FA-8: no se guardan registros incompletos
            raise InfrastructureError(code="AUDITORIA_INCOMPLETA",
                                      message=f"Evento {evento.tipo_evento} sin {', '.join(faltantes)}.")
        params = {c: getattr(evento, c) for c in _CAMPOS}
        params["json_detalle"] = a_json(evento.json_detalle)
        params["hash_integridad"] = evento.hash_integridad
        escribir(self.db, _INSERT, params)

    def consultar(self, filtros: FiltrosAuditoria, pagina: int, tamano: int) -> tuple[list[tuple[EventoIntegracion, str, dict]], int]:
        """Consulta los eventos filtrados y paginados con su total."""
        condiciones, params = [], {"limite": tamano, "desplazamiento": (pagina - 1) * tamano}
        if filtros.tipos_evento:
            condiciones.append("e.tipo_evento::text = ANY(:tipos)")
            params["tipos"] = list(filtros.tipos_evento)
        # CU07 H-01: el día del filtro es el que el usuario ve en la tabla (su zona), no el día UTC.
        for campo, valor, sql in (
            ("cliente", filtros.id_cliente_externo, "e.id_cliente_externo = :cliente"),
            ("desde", filtros.desde and inicio_dia_usuario(filtros.desde), "e.fecha_evento >= :desde"),
            ("hasta", filtros.hasta and fin_dia_usuario(filtros.hasta), "e.fecha_evento <= :hasta"),
            ("endpoint", filtros.endpoint, "e.endpoint = :endpoint"),
            ("codigo_http", filtros.codigo_http, "e.codigo_http = :codigo_http"),
            ("nit", filtros.numero_id_tributaria, "e.numero_id_tributaria = :nit"),
            ("version", filtros.version_contrato, "e.version_contrato = :version"),
        ):
            if valor is not None:
                condiciones.append(sql)
                params[campo] = valor
        if filtros.solo_exitosos:
            condiciones.append("e.codigo_resultado = 'OK'")
        donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        resultado = filas(self.db, f"""
            SELECT {_SELECT}, count(*) OVER () AS total FROM modulo7.v_historial_eventos_integracion e
            LEFT JOIN modulo1.usuarios u ON u.id_usuario = e.id_usuario
            LEFT JOIN modulo7.clientes_externos ce ON ce.id_cliente_externo = e.id_cliente_externo
            {donde} ORDER BY e.fecha_evento DESC, e.id_evento_integracion LIMIT :limite OFFSET :desplazamiento
        """, params)
        total = resultado[0]["total"] if resultado else 0
        # M7-11: «Quién» muestra el nombre; el correo sigue para la exportación y como respaldo.
        nombres = nombres_usuarios(self.db, (f["id_usuario"] for f in resultado))
        return [(_evento(f), f["hash_integridad"],
                 {"nombre_usuario": nombres.get(f["id_usuario"]), "correo_usuario": f["correo_usuario"],
                  "nombre_cliente": f["nombre_cliente"]}) for f in resultado], total

    def bloquear_archivado(self) -> bool:
        """Toma el lock de archivado sin esperar."""
        return self.db.scalar(text("SELECT pg_try_advisory_xact_lock(102, 7)"))

    def candidatos_archivo(
        self, despues_de: tuple[datetime, str] | None, limite: int,
    ) -> list[tuple[EventoIntegracion, str, datetime]]:
        """Lista los eventos vencidos a partir del cursor."""
        cursor = f"AND ({_VENCIMIENTO}, e.id_evento_integracion) > (:vencimiento, CAST(:id AS uuid))" if despues_de else ""
        parametros = {"limite": limite}
        if despues_de:
            parametros.update(vencimiento=despues_de[0], id=despues_de[1])
        candidatas = filas(self.db, f"""
            SELECT {_COLUMNAS_EVENTO}, {_VENCIMIENTO} AS vencimiento FROM modulo7.eventos_integracion e
            WHERE {_VENCIMIENTO} < statement_timestamp() {cursor}
            ORDER BY {_VENCIMIENTO}, e.id_evento_integracion LIMIT :limite
        """, parametros)
        return [(_evento(f), f["hash_integridad"], f["vencimiento"]) for f in candidatas]

    def archivar(self, ids: list[str]) -> list[tuple[EventoIntegracion, str]]:
        """Traslada los eventos al archivo y los devuelve."""
        archivados = filas(self.db, """
            SELECT id FROM modulo7.fn_archivar_eventos_rf102(CAST(:ids AS uuid[])) AS traslado(id)
        """, {"ids": ids})
        copias = filas(self.db, f"""
            SELECT {_COLUMNAS_EVENTO} FROM modulo7.eventos_integracion_archivados e
            WHERE e.id_evento_integracion = ANY(CAST(:ids AS uuid[]))
        """, {"ids": [str(f["id"]) for f in archivados]})
        return [(_evento(f), f["hash_integridad"]) for f in copias]


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
