# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-76: rol del usuario por nombre (M01)   |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Adaptador de :class:`RolUsuarioPort` contra ``modulo1`` (rol por nombre, no por id)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.supplies.domain.repositories.rol_usuario_port import RolUsuarioPort

_SQL_ES_VETERINARIO = text(
    "SELECT EXISTS (SELECT 1 FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol "
    "WHERE u.id_usuario = :id_usuario AND r.nombre_rol = 'Veterinario')"
)


class RolUsuarioM01Adapter(RolUsuarioPort):
    """Consulta el rol del usuario en identidad y acceso."""
    def __init__(self, db: Session) -> None:
        self.db = db

    def es_veterinario(self, id_usuario: int) -> bool:
        """Indica si el usuario tiene rol de veterinario."""
        return bool(self.db.execute(_SQL_ES_VETERINARIO, {"id_usuario": id_usuario}).scalar())
