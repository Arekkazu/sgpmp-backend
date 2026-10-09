"""Schemas de respuesta de `GET /sesiones/me/permisos`."""

from src.shared.base_dto import BaseDTO


class PermisoResumen(BaseDTO):
    """Par recurso + acción que el rol del usuario tiene activo."""
    id_recurso: int
    id_accion: int


class PermisosUsuarioResponse(BaseDTO):
    """Permisos activos del usuario autenticado."""
    permisos: list[PermisoResumen]
