"""Caso de uso: retiro de un permiso específico de un rol.

Valida que el permiso exista y pertenezca al rol indicado antes de eliminarlo,
para evitar retiros cruzados entre roles.
"""
from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.permiso_repository import PermisoRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AuthorizationError, NotFoundError

TIPO_REVOCACION_PERMISO = 15


class RetirarPermisoUseCase:
    """Orquesta la eliminación de un permiso de un rol con validación de pertenencia."""

    def __init__(
        self,
        permisos_repo: PermisoRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            permisos_repo: Repositorio de dominio del agregado Permiso.
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.permisos_repo = permisos_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, id_rol: int, id_permiso: int, usuario_actual: UsuarioActual) -> None:
        """Elimina el permiso del rol y registra el evento de auditoría.

        Args:
            id_rol: ID del rol del que se retirará el permiso.
            id_permiso: ID del permiso a eliminar.
            usuario_actual: Administrador que realiza la operación.

        Raises:
            NotFoundError: Si el permiso no existe. HTTP 404.
            AuthorizationError: Si el permiso no pertenece al rol indicado. HTTP 403.
        """
        permiso = self.permisos_repo.buscar_por_id(id_permiso)
        if permiso is None:
            raise NotFoundError(
                code="PERMISO_NO_ENCONTRADO",
                message=f"El permiso con ID {id_permiso} no existe.",
            )

        if not permiso.pertenece_a_rol(id_rol):
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
            self.permisos_repo.retirar(permiso)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_REVOCACION_PERMISO,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle=detalle,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
