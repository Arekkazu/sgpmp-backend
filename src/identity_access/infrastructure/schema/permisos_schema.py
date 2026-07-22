from src.shared.base_dto import BaseDTO


class PermisoResumen(BaseDTO):
    id_recurso: int
    id_accion: int


class PermisosUsuarioResponse(BaseDTO):
    permisos: list[PermisoResumen]
