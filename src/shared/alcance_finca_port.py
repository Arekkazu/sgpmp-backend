"""Puerto de alcance por finca (RF-25), transversal a todos los módulos.

Determina si un usuario tiene alcance global (ve todas las fincas) o queda
restringido a las fincas que le fueron asignadas por ``modulo9.fincas.id_usuario``.
La regla de "quién es global" se resuelve por RBAC (permiso de gestión sobre el
recurso ``fincas``), nunca por ``id_rol`` quemado en código. Espejo del patrón
``AlcanceActivoPort``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AlcanceFincaPort(ABC):

    @abstractmethod
    def es_global(self, id_rol: int) -> bool:
        """``True`` si el rol ve todas las fincas (permiso de gestión sobre fincas)."""
        raise NotImplementedError

    @abstractmethod
    def listar_ids_fincas_permitidas(self, id_usuario: int, id_rol: int) -> Optional[list[int]]:
        """``None`` si el rol no tiene restricción (ve todas las fincas).

        Una lista (posiblemente vacía) con los ``id_finca`` a los que el
        usuario tiene acceso, si el rol sí está restringido.
        """
        raise NotImplementedError
