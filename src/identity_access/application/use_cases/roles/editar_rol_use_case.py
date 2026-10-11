"""Caso de uso: edición del nombre y/o descripción de un rol existente.

Requiere que al menos uno de los dos campos editables sea proporcionado.
El rol protegido (Administrador) conserva su nombre: RF-03 prohíbe tanto
modificar su identificador base como eliminarlo. Su descripción sí es
editable — el trigger de BD tampoco la bloquea.
"""
from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.roles_dto import EditarRolDTO
from src.shared.errors import AuthorizationError, NotFoundError, ValidationError

TIPO_MODIFICACION_ROL = 12


class EditarRolUseCase:
    """Orquesta la edición del nombre y/o descripción de un rol."""

    def __init__(self, roles_repo: RolRepository, eventos_repo: EventoRepository, db: Session):
        """Inicializa el use case.

        Args:
            roles_repo: Repositorio de dominio del agregado Rol.
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.roles_repo = roles_repo
        self.eventos_repo = eventos_repo
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
            AuthorizationError: Si se intenta renombrar un rol protegido. HTTP 403.
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

        # RF-03 exige 403 para la modificación *o* la eliminación del rol
        # protegido. La guarda vive aquí, igual que en EliminarRolUseCase, para
        # no depender del trigger P0004 — que además solo frena el cambio de
        # nombre (el identificador base), no la descripción.
        if rol.es_protegido and dto.nombre_rol is not None and dto.nombre_rol != rol.nombre_rol:
            raise AuthorizationError(
                code="ROL_PROTEGIDO",
                message=(
                    "Acción denegada: El rol 'Administrador' es un objeto protegido "
                    "por el sistema. No se permite su eliminación ni el cambio de su "
                    "identificador base."
                ),
                field="nombre_rol",
            )

        try:
            rol.editar(dto.nombre_rol, dto.descripcion)
            self.roles_repo.guardar(rol)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_MODIFICACION_ROL,
                exitoso=True,
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
