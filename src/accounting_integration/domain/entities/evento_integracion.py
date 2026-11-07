# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-102: evento de auditoría de integración con hash de integridad |
"""Evento de auditoría de M07 (RF-102 v1.1). Se crea una vez y no cambia nunca."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from src.financial_valuation.domain.services.nic41 import hash_sha256

# Tipos que el Auditor externo puede ver (RF-102 4.3).
TIPOS_AUDITOR = ("PAQUETE_AAEF_CONSULTADO", "VISTA_AAEF_GENERADA", "CONTRATO_ACTIVADO")

# RF-102 8.2: campos obligatorios por fuente del evento. Sin ellos el registro se rechaza.
_OBLIGATORIOS = {
    "PAQUETE_AAEF_CONSULTADO": ("endpoint", "metodo_http", "codigo_http", "latencia_ms", "id_cliente_externo",
                                "numero_id_tributaria", "hash_contenido", "tamano_payload_bytes"),
    "SOLICITUD_RECHAZADA": ("endpoint", "metodo_http", "codigo_http", "codigo_resultado"),
    "CREDENCIALES_EN_URL": ("endpoint", "metodo_http", "codigo_http"),
    "RATE_LIMIT_EXCEDIDO": ("endpoint", "codigo_http"),
    "VISTA_AAEF_GENERADA": ("numero_id_tributaria", "hash_contenido", "tamano_payload_bytes", "version_contrato"),
    "TOKEN_CANAL_EMITIDO": ("id_cliente_externo", "id_usuario"),
    "TOKEN_CANAL_RECHAZADO": ("codigo_resultado",),
    "SECRETO_ROTADO": ("id_cliente_externo",),
    "CONTRATO_ACTIVADO": ("version_contrato",),
    "CONTRATO_DEPRECADO": ("version_contrato",),
    "CONTRATO_INACTIVADO": ("version_contrato",),
    "CONTRATO_REGISTRADO": ("version_contrato",),
}


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class EventoIntegracion:
    tipo_evento: str
    severidad: str = "INFO"
    tipo_actor: str = "SISTEMA"
    id_cliente_externo: Optional[int] = None
    id_usuario: Optional[int] = None
    id_solicitud: Optional[str] = None
    endpoint: Optional[str] = None
    metodo_http: Optional[str] = None
    codigo_http: Optional[int] = None
    codigo_resultado: Optional[str] = None
    latencia_ms: Optional[int] = None
    ip_origen: Optional[str] = None
    numero_id_tributaria: Optional[str] = None
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    version_contrato: Optional[str] = None
    hash_contenido: Optional[str] = None
    id_intercambio: Optional[str] = None
    tamano_payload_bytes: Optional[int] = None
    json_detalle: Optional[dict] = None
    modulo: str = "M07"
    fecha_evento: datetime = field(default_factory=ahora_utc)
    fecha_registro: datetime = field(default_factory=ahora_utc)
    id_evento_integracion: str = field(default_factory=lambda: str(uuid.uuid4()))

    def faltantes(self) -> list[str]:
        """RF-102 FA-8: campos obligatorios del tipo de evento que vienen vacíos."""
        return [c for c in _OBLIGATORIOS.get(self.tipo_evento, ()) if getattr(self, c) is None]

    @property
    def hash_integridad(self) -> str:
        """SHA-256 de todos los campos menos el propio hash (RF-102 4.6)."""
        return hash_sha256({k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in asdict(self).items()})
