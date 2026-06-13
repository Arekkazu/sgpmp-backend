"""Entidad de dominio ``Sesion`` del contexto de identidad y acceso.

Representa una sesión de acceso (dispositivo, IP, vigencia). Python puro,
independiente del ORM. Se identifica por ``id_sesion``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(eq=False)
class Sesion:
    """Sesión de acceso de una cuenta.

    Attributes:
        id_token: Token de acceso asociado (1:1 con la sesión).
        direccion_ip: IP desde la que se inició.
        agente_usuario: User-Agent del cliente.
        fecha_inicio: Inicio de la sesión.
        fecha_finalizacion: Fin o expiración esperada.
        es_activa: Si la sesión sigue vigente.
        id_cuenta_usuario: Cuenta propietaria de la sesión.
        id_sesion: Identidad de la sesión. ``None`` hasta que se persiste.
    """

    id_token: int
    direccion_ip: str
    agente_usuario: str
    fecha_inicio: datetime
    fecha_finalizacion: datetime
    es_activa: bool
    id_cuenta_usuario: int
    id_sesion: Optional[int] = None

    def invalidar(self, ahora: datetime) -> None:
        """Marca la sesión como cerrada en el instante dado."""
        self.es_activa = False
        self.fecha_finalizacion = ahora

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Sesion):
            return NotImplemented
        if self.id_sesion is None or other.id_sesion is None:
            return self is other
        return self.id_sesion == other.id_sesion

    def __hash__(self) -> int:
        return hash(self.id_sesion)
