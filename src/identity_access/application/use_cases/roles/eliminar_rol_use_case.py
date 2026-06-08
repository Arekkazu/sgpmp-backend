"""Caso de uso: eliminación de un rol del sistema.

Bloquea la eliminación del rol protegido (Administrador) y de cualquier rol
que tenga usuarios asignados, para mantener la integridad referencial.
"""
from sqlalchemy.orm import Session

from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import BusinessRuleError, NotFoundError

TIPO_ELIMINACION_ROL = 13


class EliminarRolUseCase:
    """Orquesta la eliminación de un rol con las guardas de integridad correspondientes."""

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

    def execute(self, id_rol: int, usuario_actual: UsuarioActual) -> None:
        """Elimina el rol del sistema si no está protegido y no tiene usuarios asignados.

        Args:
            id_rol: ID del rol a eliminar.
            usuario_actual: Administrador que realiza la operación.

        Raises:
            NotFoundError: Si el rol no existe. HTTP 404.
            BusinessRuleError: Si el rol es protegido o tiene usuarios asignados. HTTP 422.
        """
        rol = self.roles_repo.obtener_por_id(id_rol)
        if rol is None:
            raise NotFoundError(
                code="ROL_NO_ENCONTRADO",
                message=f"Error: El rol solicitado con ID {id_rol} no existe. La operación de eliminación ha sido cancelada.",
            )

        if rol.es_protegido:
            raise BusinessRuleError(
                code="ROL_PROTEGIDO",
                message=(
                    "Acción denegada: El rol 'Administrador' es un objeto protegido por el sistema. "
                    "No se permite su eliminación ni el cambio de su identificador base."
                ),
            )

        n_usuarios = self.roles_repo.contar_usuarios(id_rol)
        if n_usuarios > 0:
            raise BusinessRuleError(
                code="ROL_EN_USO",
                message=(
                    f"No se puede eliminar el rol: Existen {n_usuarios} usuario(s) vinculado(s) a "
                    f"'{rol.nombre_rol}'. Para proceder, debe reasignar estos usuarios a un rol diferente."
                ),
            )

        nombre_rol = rol.nombre_rol
        try:
            self.roles_repo.eliminar(rol)

            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_ELIMINACION_ROL,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle={"id_rol": id_rol, "nombre_rol": nombre_rol},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
