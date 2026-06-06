from sqlalchemy.orm import Session

from src.identity_access.application.ports.permisos_ports import PermisosPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import AuthorizationError, NotFoundError

TIPO_REVOCACION_PERMISO = 15


class RetirarPermisoUseCase:

    def __init__(
        self,
        permisos_port: PermisosPort,
        sesiones_port: SesionesPort,
        db: Session,
    ):
        self.permisos_port = permisos_port
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(self, id_rol: int, id_permiso: int, usuario_actual: UsuarioActual) -> None:
        permiso = self.permisos_port.buscar_por_id(id_permiso)
        if permiso is None:
            raise NotFoundError(
                code="PERMISO_NO_ENCONTRADO",
                message=f"El permiso con ID {id_permiso} no existe.",
            )

        if permiso.id_rol != id_rol:
            raise AuthorizationError(
                code="PERMISO_ROL_MISMATCH",
                message=f"El permiso {id_permiso} no pertenece al rol {id_rol}.",
            )

        detalle = {
            "id_permiso": id_permiso,
            "id_rol": id_rol,
            "id_recurso": permiso.id_recurso,
            "id_accion": permiso.id_accion,
        }

        try:
            self.permisos_port.retirar(permiso)

            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_REVOCACION_PERMISO,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle=detalle,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
