# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-45 RF-56: bitácora de eventos Edge rechazados (E1) e intentos no autorizados (E7) |
"""Bitácora RF-63 de los rechazos de ``POST /iot/eventos-edge`` (RF-56 E1 y E7).

E1: el evento que no se procesa queda registrado con su contenido, para
trazabilidad (no se elimina). E7: el intento no autorizado queda como evento
CRITICAL, que es lo que revisa seguridad. Best-effort: nunca cambia la respuesta
que ya se le va a dar al broker.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EntidadAfectadaTipo,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository

_MAX_PAYLOAD = 4000  # caracteres del contenido conservado; un evento Edge real ocupa mucho menos


def _conservar(payload: Any) -> Any:
    texto = json.dumps(payload, default=str, ensure_ascii=False)
    return payload if len(texto) <= _MAX_PAYLOAD else {"truncado": texto[:_MAX_PAYLOAD]}


def registrar_evento_rechazado(
    db: Session, bitacora: BitacoraAuditoriaIotRepository, *, motivo: str, codigo: str, payload: Any,
    serial: Optional[str] = None,
) -> None:
    """E1: estructura inválida o incoherencia temporal."""
    RegistrarEventoAuditoriaIotUseCase(db, bitacora).execute(
        tipo_evento="EVENTO_EDGE_RECHAZADO",
        resultado=TipoResultado.RECHAZADO,
        componente_origen=ComponenteOrigen.RF56,
        severidad_log=SeveridadLog.ERROR,
        descripcion=f"Evento Edge no procesado para inferencia: {motivo}",
        entidad_afectada_tipo=EntidadAfectadaTipo.PAQUETE_IA,
        entidad_afectada_id=serial,
        accion_detallada={"codigo_error": codigo, "evento": _conservar(payload)},
    )


def registrar_intento_no_autorizado(
    db: Session, bitacora: BitacoraAuditoriaIotRepository, *, codigo: str, serial: Optional[str] = None,
    device_id: Optional[int] = None, direccion_ip: Optional[str] = None,
) -> None:
    """E7: credencial del broker inválida o dispositivo que no corresponde/está inactivo."""
    RegistrarEventoAuditoriaIotUseCase(db, bitacora).execute(
        tipo_evento="INTENTO_NO_AUTORIZADO_EVENTO_EDGE",
        resultado=TipoResultado.RECHAZADO,
        componente_origen=ComponenteOrigen.RF56,
        severidad_log=SeveridadLog.CRITICAL,
        descripcion="Envío de evento Edge bloqueado por autenticación.",
        entidad_afectada_tipo=EntidadAfectadaTipo.DISPOSITIVO,
        entidad_afectada_id=serial,
        accion_detallada={"codigo_error": codigo, "device_id": device_id},
        direccion_ip=direccion_ip,
    )
