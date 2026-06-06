from sqlalchemy.orm import Session

from src.identity_access.application.ports.roles_ports import RolesPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.roles_dto import EditarRolDTO
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import NotFoundError, ValidationError

TIPO_MODIFICACION_ROL = 12


class EditarRolUseCase:

    def __init__(self, roles_port: RolesPort, sesiones_port: SesionesPort, db: Session):
        self.roles_port = roles_port
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(self, id_rol: int, dto: EditarRolDTO, usuario_actual: UsuarioActual) -> None:
        rol = self.roles_port.buscar_por_id(id_rol)
        if rol is None:
            raise NotFoundError(
                code="ROL_NO_ENCONTRADO",
                message=f"Error: El rol solicitado con ID {id_rol} no existe. La operación de modificación ha sido cancelada.",
            )

        if dto.nombre_rol is None and dto.descripcion is None:
            raise ValidationError(
                code="SIN_CAMBIOS",
                message="Debe proporcionar al menos un campo a modificar: nombre_rol o descripcion.",
            )

        try:
            self.roles_port.editar(rol, dto.nombre_rol, dto.descripcion)

            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_MODIFICACION_ROL,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "id_rol": id_rol,
                    "nombre_rol_nuevo": dto.nombre_rol,
                    "descripcion_nueva": dto.descripcion,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
