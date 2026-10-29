# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-76: rol del usuario sin id quemado     |
"""Puerto para saber si un usuario es el Veterinario responsable (RF-76 paso 9).

No decide acceso (eso es RBAC en el router): solo identifica a quién notificar
como Veterinario. Los roles son dinámicos, así que se resuelve por nombre.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class RolUsuarioPort(ABC):
    @abstractmethod
    def es_veterinario(self, id_usuario: int) -> bool:
        raise NotImplementedError
