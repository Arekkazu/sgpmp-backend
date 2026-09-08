"""Caso de uso: listado de todos los roles con sus permisos asociados.

Operación de solo lectura; no requiere auditoría ni sesión de DB propia.
"""
from src.identity_access.domain.repositories.permiso_repository import PermisoRepository
from src.identity_access.domain.repositories.rol_repository import RolRepository


class ListarRolesUseCase:
    """Orquesta la consulta de todos los roles del sistema con sus permisos."""

    def __init__(self, roles_repo: RolRepository, permisos_repo: PermisoRepository):
        """Inicializa el use case.

        Args:
            roles_repo: Repositorio de dominio del agregado Rol.
            permisos_repo: Repositorio de dominio del agregado Permiso.
        """
        self.roles_repo = roles_repo
        self.permisos_repo = permisos_repo

    def execute(self) -> list[dict]:
        """Retorna todos los roles con su lista de permisos.

        Returns:
            Lista de diccionarios con claves ``rol`` (entidad :class:`Rol`) y
            ``permisos`` (lista de entidades :class:`Permiso` del rol).
        """
        roles = self.roles_repo.listar()
        # Una sola consulta para todos los permisos (evita el N+1 de preguntar
        # por cada rol con listar_por_rol). INC-M01-127: el listado de roles se
        # ralentizaba proporcionalmente al número de roles por los round-trips.
        ids_roles = [rol.id_rol for rol in roles if rol.id_rol is not None]
        permisos_por_rol = self.permisos_repo.listar_por_roles(ids_roles)

        resultado: list[dict] = []
        for rol in roles:
            if rol.id_rol is None:
                permisos: list = []
            else:
                permisos = permisos_por_rol.get(rol.id_rol, [])
            resultado.append({"rol": rol, "permisos": permisos})
        return resultado
