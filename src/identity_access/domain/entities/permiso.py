"""Entidad de dominio ``Permiso`` del contexto de identidad y acceso.

Representa una entrada de la matriz RBAC: la capacidad de un rol de ejecutar
una acción sobre un recurso. Python puro, independiente del ORM. Se identifica
por ``id_permiso``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(eq=False)
class Permiso:
    """Permiso RBAC (rol + recurso + acción).

    Attributes:
        id_rol: Rol al que se concede el permiso.
        id_recurso: Recurso del sistema sobre el que aplica.
        id_accion: Acción autorizada (C=1, R=2, U=3, D=4, E=5).
        nombre: Nombre descriptivo y único del permiso.
        es_activo: Si el permiso está vigente y se evalúa en el control de acceso.
        descripcion: Descripción opcional del alcance.
        id_permiso: Identidad del permiso. ``None`` hasta que se persiste.
    """

    id_rol: int
    id_recurso: int
    id_accion: int
    nombre: str
    es_activo: bool
    descripcion: Optional[str] = None
    id_permiso: Optional[int] = None

    def pertenece_a_rol(self, id_rol: int) -> bool:
        """Indica si el permiso pertenece al rol dado.

        Args:
            id_rol: Rol contra el que se comprueba la pertenencia.

        Returns:
            ``True`` si el permiso es de ese rol, ``False`` en caso contrario.
        """
        return self.id_rol == id_rol

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Permiso):
            return NotImplemented
        if self.id_permiso is None or other.id_permiso is None:
            return self is other
        return self.id_permiso == other.id_permiso

    def __hash__(self) -> int:
        return hash(self.id_permiso)
