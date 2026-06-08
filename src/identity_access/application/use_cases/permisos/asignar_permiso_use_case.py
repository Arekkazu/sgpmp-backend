"""Caso de uso: asignación de un permiso (recurso + acción) a un rol.

Valida que el rol exista, que el recurso y la acción pertenezcan a los catálogos
del sistema, y que el permiso no esté duplicado antes de persistirlo.
"""
from sqlalchemy.orm import Session

from src.identity_access.application.ports.permisos_ports import PermisosPort
from src.identity_access.application.ports.roles_ports import RolesPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.roles_dto import AsignarPermisoDTO
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.identity_access.infrastructure.models.permisos_model import Permisos
from src.shared.errors import ConflictError, NotFoundError, ValidationError

TIPO_ASIGNACION_PERMISO = 14


class AsignarPermisoUseCase:
    """Orquesta la asignación de un permiso a un rol con validación de catálogos."""

    def __init__(
        self,
        roles_port: RolesPort,
        permisos_port: PermisosPort,
        sesiones_port: SesionesPort,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            roles_port: Búsqueda del rol destino.
            permisos_port: Validación de catálogos y persistencia del permiso.
            sesiones_port: Registro del evento de auditoría.
            db: Sesión SQLAlchemy activa del request.
        """
        self.roles_port = roles_port
        self.permisos_port = permisos_port
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(self, id_rol: int, dto: AsignarPermisoDTO, usuario_actual: UsuarioActual) -> Permisos:
        """Asigna el permiso indicado al rol y registra el evento de auditoría.

        Args:
            id_rol: ID del rol al que se asignará el permiso.
            dto: Recurso y acción que componen el permiso.
            usuario_actual: Administrador que realiza la asignación.

        Returns:
            Entidad `Permisos` recién creada.

        Raises:
            NotFoundError: Si el rol no existe. HTTP 404.
            ValidationError: Si el recurso o la acción no existen en catálogo. HTTP 400.
            ConflictError: Si el rol ya tiene ese permiso asignado. HTTP 409.
        """
        rol = self.roles_port.buscar_por_id(id_rol)
        if rol is None:
            raise NotFoundError(
                code="ROL_NO_ENCONTRADO",
                message=f"Error: El rol solicitado con ID {id_rol} no existe. La operación de asignación ha sido cancelada.",
            )

        if not self.permisos_port.existe_recurso(dto.id_recurso):
            raise ValidationError(
                code="RECURSO_INVALIDO",
                message=(
                    f"Error de catálogo: El recurso {dto.id_recurso} no es un módulo válido. "
                    "Verifique el catálogo de funcionalidades disponibles."
                ),
                field="id_recurso",
            )

        if not self.permisos_port.existe_accion(dto.id_accion):
            raise ValidationError(
                code="ACCION_INVALIDA",
                message=(
                    f"Error de catálogo: La acción {dto.id_accion} no es válida. "
                    "Las acciones permitidas son: C(1), R(2), U(3), D(4), E(5)."
                ),
                field="id_accion",
            )

        existente = self.permisos_port.buscar(id_rol, dto.id_recurso, dto.id_accion)
        if existente is not None:
            raise ConflictError(
                code="PERMISO_DUPLICADO",
                message=(
                    f"Conflicto de redundancia: El rol '{rol.nombre_rol}' ya cuenta con este permiso "
                    "sobre el recurso indicado. No se admiten registros duplicados."
                ),
            )

        try:
            permiso = self.permisos_port.asignar(id_rol, dto.id_recurso, dto.id_accion, rol.nombre_rol)

            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_ASIGNACION_PERMISO,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "id_rol": id_rol,
                    "nombre_rol": rol.nombre_rol,
                    "id_recurso": dto.id_recurso,
                    "id_accion": dto.id_accion,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return permiso
