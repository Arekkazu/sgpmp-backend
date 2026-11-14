# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-101: cliente externo, credencial y canales |
"""Cliente externo de la integración (RF-101 v2.0)."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.shared.errors import ConflictError

CANALES = ("IDENTIDAD_M2M", "CONSULTA_AAEF")
ESTADOS = ("ACTIVO", "SUSPENDIDO", "REVOCADO")


@dataclass
class Credencial:
    id_identificador_api: Optional[int]
    hash_secreto: str
    fecha_emision: datetime
    fecha_expiracion: datetime
    estado: str = "ACTIVA"


@dataclass
class ClienteExterno:
    id_cliente_externo: Optional[int]
    codigo: str
    nombre: str
    identificador_publico: str
    estado: str = "ACTIVO"
    tipo: str = "SISTEMA_INTERMEDIARIO"
    ip_permitida: Optional[str] = None
    ttl_token_canal_minutos: int = 15
    canales: dict[str, int] = field(default_factory=dict)  # canal -> límite por minuto
    fecha_actualizacion: Optional[datetime] = None

    def suspender(self) -> None:
        self.exigir_no_revocado("suspender")
        self.estado = "SUSPENDIDO"

    def reactivar(self) -> None:
        self.exigir_no_revocado("reactivar")  # FA-7
        self.estado = "ACTIVO"

    def revocar(self) -> None:
        self.exigir_no_revocado("revocar")
        self.estado = "REVOCADO"

    def exigir_no_revocado(self, accion: str) -> None:
        if self.estado == "REVOCADO":
            raise ConflictError(code="CLIENTE_REVOCADO",
                                message=f"El cliente {self.nombre} está revocado de forma definitiva; no se puede {accion}.")

    def ip_aceptada(self, ip: Optional[str]) -> bool:
        """RF-101 5.8: sin restricción configurada se acepta cualquier IP."""
        if not self.ip_permitida:
            return True
        try:
            return ip is not None and ipaddress.ip_address(ip) in ipaddress.ip_network(self.ip_permitida, strict=False)
        except ValueError:
            return False

    def snapshot(self) -> dict:
        return {"estado": self.estado, "ip_permitida": self.ip_permitida, "ttl_token_canal_minutos": self.ttl_token_canal_minutos,
                "canales": dict(sorted(self.canales.items()))}
