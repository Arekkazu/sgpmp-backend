"""Caso de uso: edición del nombre y/o descripción de un rol existente.

Requiere que al menos uno de los dos campos editables sea proporcionado.
El rol protegido (Administrador) puede editarse en nombre/descripción pero
no eliminarse (eso lo controla el caso de uso de eliminación).
"""
from sqlalchemy.orm import Session

from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.roles_dto import EditarRolDTO
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import NotFoundError, ValidationError

TIPO_MODIFICACION_ROL = 12


class EditarRolUseCase:
    """Orquesta la edición del nombre y/o descripción de un rol."""

    def __init__(self, roles_repo: RolRepository, sesiones_port: SesionesPort, db: Session):
        """Inicializa el use case.

        Args:
            roles_repo: Repositorio de dominio del agregado Rol.
            sesiones_port: Registro del evento de auditoría.
            db: Sesión SQLAlchemy activa del request.
        """
        self.roles_repo = roles_repo
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(self, id_rol: int, dto: EditarRolDTO, usuario_actual: UsuarioActual) -> None:
        """Aplica los cambios de nombre/descripción al rol indicado.

        Args:
            id_rol: ID del rol a editar.
            dto: Nuevos valores para nombre y/o descripción (ambos opcionales).
            usuario_actual: Administrador que realiza la operación.

        Raises:
            NotFoundError: Si el rol no existe. HTTP 404.
            ValidationError: Si ningún campo editable fue proporcionado. HTTP 400.
            ConflictError: Si el nuevo nombre ya está en uso por otro rol. HTTP 409.
        """
        rol = self.roles_repo.obtener_por_id(id_rol)
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
            rol.editar(dto.nombre_rol, dto.descripcion)
            self.roles_repo.guardar(rol)

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
