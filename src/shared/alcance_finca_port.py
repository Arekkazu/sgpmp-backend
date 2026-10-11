"""Puerto de alcance por finca (RF-25), transversal a todos los módulos.

Determina a qué fincas tiene acceso un usuario: las que le fueron asignadas en
``modulo9.usuarios_fincas``, salvo el rol protegido (Administrador del sistema,
RF-19), que es global y recibe ``None`` ("sin restricción"). Es la misma regla
que aplica RLS (migración ``f68851f9a433``). Espejo del patrón
``AlcanceActivoPort``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AlcanceFincaPort(ABC):

    @abstractmethod
    def es_global(self, id_rol: int) -> bool:
        """``True`` si el rol ve todas las fincas (solo el rol protegido)."""
        raise NotImplementedError

    @abstractmethod
    def listar_ids_fincas_permitidas(self, id_usuario: int, id_rol: int) -> Optional[list[int]]:
        """``None`` si el rol no tiene restricción (ve todas las fincas).

        Una lista (posiblemente vacía) con los ``id_finca`` a los que el
        usuario tiene acceso, si el rol sí está restringido.
        """
        raise NotImplementedError
