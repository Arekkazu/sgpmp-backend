"""Caso de uso: edición de perfil de usuario (propio o por administrador).

Un usuario solo puede modificar su propia información; un administrador puede
editar cualquier perfil, incluyendo rol y estado de cuenta. Si el correo cambia,
la cuenta pasa a PENDIENTE y se envía un correo de verificación al nuevo correo.
"""
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilAdminDTO
from src.identity_access.infrastructure.email_templates import activation_email
from src.shared.email import send_email
from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError, ValidationError

ROL_ADMINISTRADOR = 1
ESTADOS_QUE_INVALIDAN_SESION = {3, 4, 5}  # Inactivo, Bloqueado, Eliminado
TIPO_EVENTO_ACTUALIZACION_PERFIL = 9

TRANSICIONES_VALIDAS = {
    1: {2, 5},          # Pendiente → Activo, Eliminado
    2: {1, 3, 4, 5},    # Activo → Pendiente, Inactivo, Bloqueado, Eliminado
    3: {2, 5},          # Inactivo → Activo, Eliminado
    4: {2, 3, 5},       # Bloqueado → Activo, Inactivo, Eliminado
    # Eliminado (5) no tiene transiciones salientes
}


def _valor_columna(usuario: Usuario, campo: str):
    """Lee el valor de un campo de la entidad por su nombre de columna ORM.

    El audit detail conserva las claves de columna (``correo_electronico``);
    la entidad expone el correo como value object ``correo``.
    """
    if campo == "correo_electronico":
        return str(usuario.correo)
    return getattr(usuario, campo, None)


class EditarPerfilUseCase:
    """Orquesta la edición de perfil con soporte de control de concurrencia y cambio de correo."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        sesiones_repo: SesionRepository,
        eventos_repo: EventoRepository,
        roles_repo: RolRepository,
        db: Session,
        notificacion_service=None,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario (lectura y actualización).
            cuentas_repo: Repositorio de dominio del agregado Cuenta (estado y token).
            sesiones_repo: Repositorio de dominio de sesiones (invalidación).
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            roles_repo: Repositorio de dominio de roles (verificación de existencia).
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones opcional.
        """
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.sesiones_repo = sesiones_repo
        self.eventos_repo = eventos_repo
        self.roles_repo = roles_repo
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, id_usuario: int, dto: EditarPerfilAdminDTO, usuario_actual: UsuarioActual) -> Usuario:
        """Aplica los cambios de perfil respetando los permisos del actor.

        Args:
            id_usuario: ID del usuario cuyo perfil se va a editar.
            dto: Campos a actualizar (campos `None` se ignoran) y versión para control
                 de concurrencia optimista.
            usuario_actual: Usuario autenticado que realiza la operación.

        Returns:
            Entidad :class:`Usuario` actualizada.

        Raises:
            NotFoundError: Si el usuario objetivo no existe. HTTP 404.
            AuthorizationError: Si un no-administrador intenta editar otro perfil
                o modificar campos de rol/estado. HTTP 403.
            ValidationError: Si un administrador intenta cambiar su propio rol/estado,
                o el rol indicado no existe. HTTP 400.
            BusinessRuleError: Si la transición de estado no es válida o se intenta
                cambiar el correo de una cuenta no activa. HTTP 422.
            PreconditionFailedError: Si la versión del registro no coincide (edición concurrente). HTTP 412.
        """
        es_admin = usuario_actual.id_rol == ROL_ADMINISTRADOR

        # 1. Buscar usuario objetivo
        usuario = self.usuarios_repo.obtener_por_id(id_usuario)
        if usuario is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message="Usuario no encontrado. El registro que intenta modificar no existe en el sistema.",
            )

        # 2. Verificar permisos del actor
        if not es_admin:
            if id_usuario != usuario_actual.id_usuario:
                raise AuthorizationError(
                    code="EDICION_NO_AUTORIZADA",
                    message="Acceso restringido. Solo puede modificar su propia información.",
                )
            if dto.id_estado_cuenta is not None or dto.id_rol is not None:
                raise AuthorizationError(
                    code="SIN_PERMISO_CAMPOS_CRITICOS",
                    message=(
                        "Acceso restringido. No tiene permisos para modificar campos críticos "
                        "(Rol/Estado). Esta acción ha sido reportada al sistema de auditoría."
                    ),
                )
        else:
            if id_usuario == usuario_actual.id_usuario:
                if dto.id_estado_cuenta is not None or dto.id_rol is not None:
                    raise ValidationError(
                        code="RESTRICCION_AUTOEDICION_ADMIN",
                        message=(
                            "Operación no permitida. Por seguridad, un administrador no puede "
                            "desactivar su propia cuenta ni remover sus privilegios administrativos."
                        ),
                    )
            if dto.id_rol is not None and self.roles_repo.obtener_por_id(dto.id_rol) is None:
                raise ValidationError(
                    code="ROL_NO_EXISTE",
                    message="El rol asignado no existe en el sistema.",
                    field="id_rol",
                )

        # 3. Construir dict de cambios y capturar valores anteriores
        correo_modificado = (
            dto.correo_electronico is not None
            and str(dto.correo_electronico) != str(usuario.correo)
        )
        nuevo_correo = str(dto.correo_electronico) if correo_modificado else None

        cambios = {"nombre": dto.nombre, "apellidos": dto.apellidos}
        if dto.correo_electronico is not None:
            cambios["correo_electronico"] = str(dto.correo_electronico)
        if dto.telefono is not None:
            cambios["telefono"] = dto.telefono
        if dto.direccion is not None:
            cambios["direccion"] = dto.direccion
        if es_admin and dto.id_rol is not None:
            cambios["id_rol"] = dto.id_rol

        valores_anteriores = {campo: _valor_columna(usuario, campo) for campo in cambios}

        nuevo_estado = dto.id_estado_cuenta if (es_admin and dto.id_estado_cuenta is not None) else None
        estado_invalida_sesion = nuevo_estado in ESTADOS_QUE_INVALIDAN_SESION if nuevo_estado else False

        # 4. Revocar sesión activa ANTES del flush de estado (el trigger la desactiva después)
        cuenta_objetivo = self.cuentas_repo.obtener_por_usuario(usuario.id_usuario)

        if (estado_invalida_sesion or correo_modificado) and cuenta_objetivo is not None:
            sesion_activa = self.sesiones_repo.buscar_sesion_activa(cuenta_objetivo.id_cuenta_usuario)
            if sesion_activa is not None:
                self.sesiones_repo.invalidar_sesion(sesion_activa)

        if correo_modificado and cuenta_objetivo is not None and cuenta_objetivo.id_estado_cuenta != Cuenta.ESTADO_ACTIVO:
            raise BusinessRuleError(
                code="CUENTA_NO_ACTIVA",
                message="No se puede cambiar el correo electrónico porque la cuenta no está activa.",
                field="correo_electronico",
            )

        token_verificacion = None
        try:
            # 5. Aplicar los cambios a la entidad y persistir (con control de concurrencia)
            usuario.nombre = cambios["nombre"]
            usuario.apellidos = cambios["apellidos"]
            if "correo_electronico" in cambios:
                usuario.correo = Email(cambios["correo_electronico"])
            if "telefono" in cambios:
                usuario.telefono = cambios["telefono"]
            if "direccion" in cambios:
                usuario.direccion = cambios["direccion"]
            if "id_rol" in cambios:
                usuario.id_rol = cambios["id_rol"]

            usuario = self.usuarios_repo.actualizar(usuario, dto.version)

            # 6. Actualizar estado en cuentas_usuarios si admin lo modificó
            if nuevo_estado is not None and cuenta_objetivo is not None and nuevo_estado != cuenta_objetivo.id_estado_cuenta:
                estado_actual = cuenta_objetivo.id_estado_cuenta
                if nuevo_estado not in TRANSICIONES_VALIDAS.get(estado_actual, set()):
                    raise BusinessRuleError(
                        code="TRANSICION_INVALIDA",
                        message=f"No se puede cambiar el estado de la cuenta de {estado_actual} a {nuevo_estado} porque la transición no está permitida.",
                    )
                cuenta_objetivo.cambiar_estado(nuevo_estado)
                self.cuentas_repo.guardar(cuenta_objetivo)

            # 7. Poner cuenta en PENDIENTE si correo fue modificado
            if correo_modificado and cuenta_objetivo is not None:
                token_verificacion = secrets.token_urlsafe(32)
                cuenta_objetivo.poner_pendiente(token_verificacion, datetime.now(timezone.utc))
                self.cuentas_repo.guardar(cuenta_objetivo)

            # 8. Registrar evento de auditoría
            tipo_actor = "Administrador" if es_admin else "Usuario"
            self.eventos_repo.registrar(
                tipo_evento=TIPO_EVENTO_ACTUALIZACION_PERFIL,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "id_usuario_modificado": id_usuario,
                    "tipo_actor": tipo_actor,
                    "campos_modificados": list(cambios.keys()),
                    "valores_anteriores": valores_anteriores,
                    "valores_nuevos": {campo: _valor_columna(usuario, campo) for campo in cambios},
                },
            )

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # 9. Enviar email de verificación si el correo fue modificado (después del commit)
        if correo_modificado and token_verificacion is not None:
            send_email(
                to=nuevo_correo,
                subject="Verifica tu nuevo correo en SGPMP",
                html_body=activation_email(usuario.nombre, token_verificacion),
            )

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_EVENTO_ACTUALIZACION_PERFIL,
                id_usuario=id_usuario,
                correo_destino=str(usuario.correo),
            )

        return usuario
