from src.identity_access.application.ports.permisos_ports import PermisosPort
from src.identity_access.application.ports.roles_ports import RolesPort


class ListarRolesUseCase:

    def __init__(self, roles_port: RolesPort, permisos_port: PermisosPort):
        self.roles_port = roles_port
        self.permisos_port = permisos_port

    def execute(self) -> list[dict]:
        roles = self.roles_port.listar()
        return [
            {
                "rol": rol,
                "permisos": self.permisos_port.listar_por_rol(rol.id_rol),
            }
            for rol in roles
        ]
