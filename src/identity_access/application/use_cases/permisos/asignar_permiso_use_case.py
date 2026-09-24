"""Caso de uso: asignación de un permiso (recurso + acción) a un rol.

Valida que el rol exista, que el recurso y la acción pertenezcan a los catálogos
del sistema, que la acción aplique al recurso (RF-04) y que el permiso no esté
duplicado antes de persistirlo.
"""
from sqlalchemy.orm import Session

from src.identity_access.domain.entities.permiso import Permiso
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.permiso_repository import PermisoRepository
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.roles_dto import AsignarPermisoDTO
from src.shared.errors import ConflictError, NotFoundError, ValidationError

TIPO_ASIGNACION_PERMISO = 14

# `modulo1.acciones`: 1=C, 2=R, 3=U, 4=D, 5=E.
ACCION_EJECUTAR = 5


class AsignarPermisoUseCase:
    """Orquesta la asignación de un permiso a un rol con validación de catálogos."""

    def __init__(
        self,
        roles_repo: RolRepository,
        permisos_repo: PermisoRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            roles_repo: Repositorio de dominio del agregado Rol (busca el rol destino).
            permisos_repo: Repositorio de dominio del agregado Permiso.
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.roles_repo = roles_repo
        self.permisos_repo = permisos_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, id_rol: int, dto: AsignarPermisoDTO, usuario_actual: UsuarioActual) -> Permiso:
        """Asigna el permiso indicado al rol y registra el evento de auditoría.

        Args:
            id_rol: ID del rol al que se asignará el permiso.
            dto: Recurso y acción que componen el permiso.
            usuario_actual: Administrador que realiza la asignación.

        Returns:
            La entidad :class:`Permiso` recién creada.

        Raises:
            NotFoundError: Si el rol no existe. HTTP 404.
            ValidationError: Si el recurso o la acción no existen en catálogo, o
                si la acción no aplica al recurso. HTTP 400.
            ConflictError: Si el rol ya tiene ese permiso asignado. HTTP 409.
        """
        rol = self.roles_repo.obtener_por_id(id_rol)
        if rol is None:
            raise NotFoundError(
                code="ROL_NO_ENCONTRADO",
                message=f"Error: El rol solicitado con ID {id_rol} no existe. La operación de asignación ha sido cancelada.",
            )

        if not self.permisos_repo.existe_recurso(dto.id_recurso):
            raise ValidationError(
                code="RECURSO_INVALIDO",
                message=(
                    f"Error de catálogo: El recurso {dto.id_recurso} no es un módulo válido. "
                    "Verifique el catálogo de funcionalidades disponibles."
                ),
                field="id_recurso",
            )

        if not self.permisos_repo.existe_accion(dto.id_accion):
            raise ValidationError(
                code="ACCION_INVALIDA",
                message=(
                    f"Error de catálogo: La acción {dto.id_accion} no es válida. "
                    "Las acciones permitidas son: C(1), R(2), U(3), D(4), E(5)."
                ),
                field="id_accion",
            )

        # RF-04: la acción Ejecutar solo aplica a procesos especiales del
        # catálogo (`modulo1.recursos.es_proceso_especial`). La otra mitad del
        # caso —"acción CRUD a un recurso que no las soporta"— no es exigible
        # hoy: el catálogo no declara qué CRUD admite cada recurso.
        if dto.id_accion == ACCION_EJECUTAR and not self.permisos_repo.es_proceso_especial(
            dto.id_recurso
        ):
            raise ValidationError(
                code="ACCION_NO_PERMITIDA_PARA_RECURSO",
                message=(
                    f"Acción inválida: El recurso {dto.id_recurso} no admite la operación "
                    "'E'. Solo se permiten acciones de ejecución en procesos especiales "
                    "del catálogo."
                ),
                field="id_accion",
            )

        existente = self.permisos_repo.buscar(id_rol, dto.id_recurso, dto.id_accion)
        if existente is not None:
            raise ConflictError(
                code="PERMISO_DUPLICADO",
                message=(
                    f"Conflicto de redundancia: El rol '{rol.nombre_rol}' ya cuenta con este permiso "
                    "sobre el recurso indicado. No se admiten registros duplicados."
                ),
            )

        try:
            permiso = self.permisos_repo.asignar(id_rol, dto.id_recurso, dto.id_accion, rol.nombre_rol)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_ASIGNACION_PERMISO,
                exitoso=True,
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
