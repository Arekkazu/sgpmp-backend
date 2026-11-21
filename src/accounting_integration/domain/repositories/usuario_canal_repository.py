# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-SSO02: puerto de lectura del usuario que actúa por el canal |
"""Usuario de SGPMP a cuyo nombre actúa un cliente externo (RF-SSO02, RF-95 5.3 c)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UsuarioCanal:
    id_usuario: int
    id_rol: int
    nombre_rol: str
    correo: str
    es_activo: bool


class UsuarioCanalRepository(ABC):
    @abstractmethod
    def obtener_por_correo(self, correo: str) -> Optional[UsuarioCanal]: ...

    @abstractmethod
    def obtener(self, id_usuario: int) -> Optional[UsuarioCanal]: ...
