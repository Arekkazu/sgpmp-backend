"""Entidad de dominio ``Rol`` del contexto de identidad y acceso.

Representa un rol RBAC como concepto de negocio, independiente del ORM. Guarda
los mismos datos que la tabla ``roles`` y expone la conducta propia del rol
(editar nombre/descripción). Se identifica por ``id_rol``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(eq=False)
class Rol:
    """Rol RBAC del sistema.

    Attributes:
        nombre_rol: Nombre único del rol.
        es_protegido: Si es ``True``, el rol es de sistema y no puede eliminarse.
        descripcion: Descripción opcional del alcance del rol.
        id_rol: Identidad del rol. ``None`` hasta que se persiste.
    """

    nombre_rol: str
    es_protegido: bool
    descripcion: Optional[str] = None
    id_rol: Optional[int] = None

    def editar(self, nombre_rol: Optional[str] = None, descripcion: Optional[str] = None) -> None:
        """Aplica cambios de nombre y/o descripción, ignorando los valores ``None``.

        Args:
            nombre_rol: Nuevo nombre, o ``None`` para conservarlo.
            descripcion: Nueva descripción, o ``None`` para conservarla.
        """
        if nombre_rol is not None:
            self.nombre_rol = nombre_rol
        if descripcion is not None:
            self.descripcion = descripcion

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Rol):
            return NotImplemented
        if self.id_rol is None or other.id_rol is None:
            return self is other
        return self.id_rol == other.id_rol

    def __hash__(self) -> int:
        return hash(self.id_rol)
