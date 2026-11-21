# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-25 RF-17: nombre_recurso en el resumen de permisos |
"""Schemas de respuesta de `GET /sesiones/me/permisos`."""
from typing import Optional

from src.shared.base_dto import BaseDTO


class PermisoResumen(BaseDTO):
    """Par recurso + acción que el rol del usuario tiene activo."""
    id_recurso: int
    id_accion: int
    # Para recursos cuyo id difiere entre ambientes (p. ej. variables_ambientales_criticas).
    nombre_recurso: Optional[str] = None


class PermisosUsuarioResponse(BaseDTO):
    """Permisos activos del usuario autenticado."""
    permisos: list[PermisoResumen]
