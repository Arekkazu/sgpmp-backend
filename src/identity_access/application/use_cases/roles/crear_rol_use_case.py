from sqlalchemy.orm import Session

from src.identity_access.application.ports.roles_ports import RolesPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.roles_dto import CrearRolDTO
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado

TIPO_CREACION_ROL = 11


class CrearRolUseCase:

    def __init__(self, roles_port: RolesPort, sesiones_port: SesionesPort, db: Session):
        self.roles_port = roles_port
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(self, dto: CrearRolDTO, usuario_actual: UsuarioActual) -> int:
        try:
            id_rol = self.roles_port.crear_con_sp(
                nombre_rol=dto.nombre_rol,
                descripcion=dto.descripcion,
                permisos_json=[p.model_dump() for p in dto.permisos],
            )

            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_CREACION_ROL,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle={"nombre_rol": dto.nombre_rol, "id_rol_creado": id_rol},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return id_rol
