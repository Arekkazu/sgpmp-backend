"""Entidad de dominio ``Token`` del contexto de identidad y acceso.

Representa un token de acceso (JWT) registrado. ``fecha_uso`` no nula indica que
el token fue consumido (forma la blacklist). Python puro, independiente del ORM.
Se identifica por ``id_token``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(eq=False)
class Token:
    """Token de acceso registrado.

    Attributes:
        token_tipo: Tipo del token como texto (``.value`` del enum), o ``None``.
        fecha_expiracion: Instante en que deja de ser válido, o ``None``.
        fecha_uso: Instante en que fue consumido, o ``None`` si sigue vigente.
        fecha_creacion: Marca de creación, o ``None``.
        id_token: Identidad del token. ``None`` hasta que se persiste.
        hash_valor: Hash SHA-256 del valor en claro (solo tokens de refresco).
        id_sesion: Sesión que emitió este token (solo tokens de refresco).
    """

    token_tipo: Optional[str] = None
    fecha_expiracion: Optional[datetime] = None
    fecha_uso: Optional[datetime] = None
    fecha_creacion: Optional[datetime] = None
    id_token: Optional[int] = None
    hash_valor: Optional[str] = None
    id_sesion: Optional[int] = None

    def esta_usado(self) -> bool:
        """Indica si el token ya fue consumido."""
        return self.fecha_uso is not None

    def marcar_usado(self, ahora: datetime) -> None:
        """Marca el token como consumido en el instante dado."""
        self.fecha_uso = ahora

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Token):
            return NotImplemented
        if self.id_token is None or other.id_token is None:
            return self is other
        return self.id_token == other.id_token

    def __hash__(self) -> int:
        return hash(self.id_token)
