"""Puerto de alcance por finca (RF-25), transversal a todos los módulos.

Determina a qué fincas tiene acceso un usuario: las que le fueron asignadas en
``modulo9.usuarios_fincas``. Hoy ningún rol es global (decisión del DBA en el
PR #485, la misma regla que aplica RLS); el contrato conserva ``es_global`` y
el ``None`` de "sin restricción" para no tocar a los consumidores. Espejo del
patrón ``AlcanceActivoPort``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AlcanceFincaPort(ABC):

    @abstractmethod
    def es_global(self, id_rol: int) -> bool:
        """``True`` si el rol ve todas las fincas. Hoy siempre ``False``."""
        raise NotImplementedError

    @abstractmethod
    def listar_ids_fincas_permitidas(self, id_usuario: int, id_rol: int) -> Optional[list[int]]:
        """``None`` si el rol no tiene restricción (ve todas las fincas).

        Una lista (posiblemente vacía) con los ``id_finca`` a los que el
        usuario tiene acceso, si el rol sí está restringido.
        """
        raise NotImplementedError
