from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.prediction.domain.entities.evento_auditoria_m04 import EventoAuditoriaM04
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.infrastructure.models.evento_auditoria_m04_model import EventoAuditoriaM04Model
from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import NotFoundError

logger = logging.getLogger(__name__)

# Campos mínimos requeridos en payload_evento por tipo_evento (solo eventos que genera Desarrollo)
_PAYLOAD_REQUERIDO: dict[str, list[str]] = {
    "RETROALIMENTACION_REGISTRADA": [
        "id_resultado_inferencia", "estado_retroalimentacion", "id_usuario_veterinario",
    ],
    "CONFLICTO_RETROALIMENTACION": [
        "id_resultado_inferencia", "numero_retroalimentaciones",
    ],
    "VERSION_APROBADA": ["tipo_modelo", "id_version", "f1_score_global", "recall_clase_riesgo_alto"],
    "VERSION_RECHAZADA": ["tipo_modelo", "id_version", "f1_score_global", "recall_clase_riesgo_alto"],
    "VERSION_ACTIVADA": ["tipo_modelo", "id_version_nueva"],
    "VERSION_DEPRECADA": ["tipo_modelo", "id_version"],
    "VERSION_REGISTRADA": ["tipo_modelo", "id_version"],
    "CATALOGO_PATOLOGIA_AGREGADA": ["id_patologia", "nombre"],
    "CATALOGO_PATOLOGIA_MODIFICADA": ["id_patologia"],
    "CATALOGO_PATOLOGIA_INACTIVADA": ["id_patologia"],
    "MOTOR_CONFIG_ACTUALIZADO": ["id_configuracion"],
}

_PAYLOAD_MAX_BYTES = 64 * 1024  # 64 KB


def _calcular_hash(tipo_evento: str, payload: dict, fecha: str) -> str:
    canonical = json.dumps(
        {"tipo_evento": tipo_evento, "payload_evento": payload, "fecha": fecha},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validar_payload(tipo_evento: str, payload: dict) -> list[str]:
    requeridos = _PAYLOAD_REQUERIDO.get(tipo_evento, [])
    return [campo for campo in requeridos if campo not in payload]


def _escribir_fallback(data: dict) -> None:
    try:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        filename = logs_dir / f"audit_fallback_M04_{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
        line = json.dumps({**data, "origen_registro": "FALLBACK"}, default=str)
        with open(filename, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        logger.exception("Error escribiendo fallback de auditoría M04")


def _a_entidad(orm: EventoAuditoriaM04Model) -> EventoAuditoriaM04:
    return EventoAuditoriaM04(
        id_evento=orm.id_evento,
        tipo_evento=orm.tipo_evento,
        modulo=orm.modulo,
        fecha_evento=orm.fecha_evento,
        tipo_actor=orm.tipo_actor,
        correlacion_id=orm.correlacion_id,
        payload_evento=orm.payload_evento,
        es_payload_truncado=orm.es_payload_truncado,
        severidad_evento=orm.severidad_evento,
        origen_registro=orm.origen_registro,
        id_usuario=orm.id_usuario,
        id_sistema=orm.id_sistema,
        id_referencia=orm.id_referencia,
        entidad_referencia=orm.entidad_referencia,
        resultado_operacion=orm.resultado_operacion,
        codigo_error=orm.codigo_error,
        descripcion_error=orm.descripcion_error,
        origen_dato=orm.origen_dato,
        version_modelo=orm.version_modelo,
        latencia_ms=orm.latencia_ms,
        hash_evento=orm.hash_evento,
    )


class SqlAlchemyEventoAuditoriaM04Repository(EventoAuditoriaM04Repository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def registrar(
        self,
        *,
        tipo_evento: str,
        tipo_actor: str,
        payload_evento: dict,
        severidad_evento: str = "INFO",
        id_usuario: Optional[int] = None,
        id_sistema: Optional[str] = None,
        id_referencia: Optional[str] = None,
        entidad_referencia: Optional[str] = None,
        resultado_operacion: Optional[str] = None,
        correlacion_id: Optional[uuid.UUID] = None,
    ) -> None:
        campos_faltantes = _validar_payload(tipo_evento, payload_evento)
        if campos_faltantes:
            self._registrar_invalido(tipo_evento, payload_evento, campos_faltantes, correlacion_id)
            return

        payload_final, truncado = _truncar_payload(payload_evento)
        sev_final = "WARNING" if truncado else severidad_evento
        ahora = datetime.now(timezone.utc).isoformat()
        hash_ev = _calcular_hash(tipo_evento, payload_final, ahora)
        corr = correlacion_id or uuid.uuid4()

        orm = EventoAuditoriaM04Model(
            tipo_evento=tipo_evento,
            tipo_actor=tipo_actor,
            payload_evento=payload_final,
            es_payload_truncado=truncado,
            severidad_evento=sev_final,
            id_usuario=id_usuario,
            id_sistema=id_sistema,
            id_referencia=id_referencia,
            entidad_referencia=entidad_referencia,
            resultado_operacion=resultado_operacion,
            correlacion_id=corr,
            origen_registro="DESARROLLO_M04",
            hash_evento=hash_ev,
        )
        try:
            self._db.add(orm)
            self._db.flush()
        except Exception as exc:
            if severidad_evento in ("ERROR", "CRITICAL"):
                _escribir_fallback({
                    "tipo_evento": tipo_evento,
                    "tipo_actor": tipo_actor,
                    "severidad_evento": severidad_evento,
                    "payload_evento": payload_final,
                    "id_usuario": id_usuario,
                    "id_sistema": id_sistema,
                    "id_referencia": id_referencia,
                    "correlacion_id": str(corr),
                    "hash_evento": hash_ev,
                })
            logger.error("Error al persistir evento de auditoría M04 tipo=%s: %s", tipo_evento, exc)

    def _registrar_invalido(
        self,
        tipo_evento_orig: str,
        payload_orig: dict,
        campos_faltantes: list[str],
        correlacion_id: Optional[uuid.UUID],
    ) -> None:
        try:
            self._db.add(EventoAuditoriaM04Model(
                tipo_evento="AUDITORIA_EVENTO_INVALIDO",
                tipo_actor="SISTEMA",
                payload_evento={
                    "tipo_evento_original": tipo_evento_orig,
                    "campos_faltantes": campos_faltantes,
                    "payload_recibido": payload_orig,
                },
                severidad_evento="ERROR",
                correlacion_id=correlacion_id or uuid.uuid4(),
                origen_registro="DESARROLLO_M04",
            ))
            self._db.flush()
        except Exception as exc:
            logger.error("Error al persistir evento AUDITORIA_EVENTO_INVALIDO: %s", exc)

    def consultar(
        self,
        *,
        tipo_evento: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        id_usuario: Optional[int] = None,
        id_sistema: Optional[str] = None,
        id_referencia: Optional[str] = None,
        severidad_evento: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> tuple[list[EventoAuditoriaM04], int]:
        q = select(EventoAuditoriaM04Model)

        if tipo_evento:
            q = q.where(EventoAuditoriaM04Model.tipo_evento == tipo_evento)
        if fecha_desde:
            q = q.where(EventoAuditoriaM04Model.fecha_evento >= fecha_desde)
        if fecha_hasta:
            q = q.where(EventoAuditoriaM04Model.fecha_evento <= fecha_hasta)
        if id_usuario is not None:
            q = q.where(EventoAuditoriaM04Model.id_usuario == id_usuario)
        if id_sistema:
            q = q.where(EventoAuditoriaM04Model.id_sistema == id_sistema)
        if id_referencia:
            q = q.where(EventoAuditoriaM04Model.id_referencia == id_referencia)
        if severidad_evento:
            q = q.where(EventoAuditoriaM04Model.severidad_evento == severidad_evento)

        total_q = select(func.count()).select_from(q.subquery())
        total = self._db.execute(total_q).scalar_one()

        offset = (pagina - 1) * por_pagina
        items = (
            self._db.execute(
                q.order_by(EventoAuditoriaM04Model.fecha_evento.desc()).offset(offset).limit(por_pagina)
            )
            .scalars()
            .all()
        )
        return [_a_entidad(row) for row in items], total

    def obtener_por_id(self, id_evento: uuid.UUID) -> EventoAuditoriaM04:
        orm = self._db.get(EventoAuditoriaM04Model, id_evento)
        if orm is None:
            raise NotFoundError(
                code="EVENTO_AUDITORIA_NO_ENCONTRADO",
                message=f"No existe el evento de auditoría con id {id_evento}.",
            )
        return _a_entidad(orm)


def _truncar_payload(payload: dict) -> tuple[dict, bool]:
    raw = json.dumps(payload, default=str)
    if len(raw.encode()) <= _PAYLOAD_MAX_BYTES:
        return payload, False
    # Truncar serialización y agregar flag
    truncado = raw.encode()[:_PAYLOAD_MAX_BYTES].decode(errors="ignore")
    try:
        resultado = json.loads(truncado)
    except json.JSONDecodeError:
        resultado = {"payload_truncado_raw": truncado[:500]}
    resultado["payload_truncado"] = True
    return resultado, True
