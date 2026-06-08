"""Caso de uso: listado de todos los roles con sus permisos asociados.

Operación de solo lectura; no requiere auditoría ni sesión de DB propia.
"""
from src.identity_access.application.ports.permisos_ports import PermisosPort
from src.identity_access.application.ports.roles_ports import RolesPort


class ListarRolesUseCase:
    """Orquesta la consulta de todos los roles del sistema con sus permisos."""

    def __init__(self, roles_port: RolesPort, permisos_port: PermisosPort):
        """Inicializa el use case.

        Args:
            roles_port: Listado de todos los roles.
            permisos_port: Consulta de permisos por rol.
        """
        self.roles_port = roles_port
        self.permisos_port = permisos_port

    def execute(self) -> list[dict]:
        """Retorna todos los roles con su lista de permisos.

        Returns:
            Lista de diccionarios con claves `rol` (entidad `Roles`) y
            `permisos` (lista de entidades `Permisos` del rol).
        """
        roles = self.roles_port.listar()
        return [
            {
                "rol": rol,
                "permisos": self.permisos_port.listar_por_rol(rol.id_rol),
            }
            for rol in roles
        ]
