"""Caso de uso: edición de perfil de usuario (propio o por administrador).

La autorización se resuelve en dos endpoints del router: edición propia y
edición administrativa con RBAC. Este caso de uso modifica datos de perfil y,
cuando corresponde, el rol; los estados de cuenta se gestionan solo por RF-06.
Si el correo cambia, la cuenta pasa a PENDIENTE y se envía verificación.
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
from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilDTO
from src.identity_access.infrastructure.email_templates import activation_email
from src.shared.email import send_email
from src.shared.errors import BusinessRuleError, NotFoundError, ValidationError


TIPO_EVENTO_ACTUALIZACION_PERFIL = 9


def _valor_columna(usuario: Usuario, campo: str):
    """Lee el valor de un campo de la entidad por su nombre de columna ORM.

    El detalle de auditoría conserva las claves de columna
    (``correo_electronico``), mientras que la entidad expone el correo
    mediante el value object ``correo``.
    """
    if campo == "correo_electronico":
        return str(usuario.correo)

    return getattr(usuario, campo, None)


class EditarPerfilUseCase:
    """Orquesta la edición de perfil y las reglas de negocio asociadas."""

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
        """Inicializa el caso de uso.

        Args:
            usuarios_repo: Repositorio de usuarios.
            cuentas_repo: Repositorio de cuentas.
            sesiones_repo: Repositorio utilizado para invalidar sesiones.
            eventos_repo: Repositorio de eventos de auditoría.
            roles_repo: Repositorio de roles.
            db: Sesión SQLAlchemy activa.
            notificacion_service: Servicio de notificaciones opcional.
        """
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.sesiones_repo = sesiones_repo
        self.eventos_repo = eventos_repo
        self.roles_repo = roles_repo
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(
        self,
        id_usuario: int,
        dto: EditarPerfilDTO,
        usuario_actual: UsuarioActual,
    ) -> Usuario:
        """Aplica cambios de perfil previamente autorizados por el router.

        Args:
            id_usuario: ID del usuario cuyo perfil se va a editar.
            dto: Campos permitidos para actualizar.
            usuario_actual: Usuario autenticado que realiza la operación.

        Returns:
            Entidad Usuario actualizada.

        Raises:
            NotFoundError: Si el usuario objetivo no existe.
            ValidationError: Si se intenta cambiar el propio rol o el nuevo
                rol no existe.
            BusinessRuleError: Si el cambio de correo no es permitido o se
                intenta reasignar al último usuario activo de un rol protegido.
        """

        # 1. Buscar usuario objetivo.
        usuario = self.usuarios_repo.obtener_por_id(id_usuario)

        if usuario is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message=(
                    "Usuario no encontrado. El registro que intenta modificar "
                    "no existe en el sistema."
                ),
            )

        # 2. La autorización propio/administrativo se realiza en el router.
        # EditarPerfilAdminDTO incorpora id_rol, mientras que EditarPerfilDTO
        # utilizado para /usuarios/me no lo expone.
        es_edicion_administrativa = hasattr(dto, "id_rol")
        id_rol_nuevo = getattr(dto, "id_rol", None)

        rol_modificado = (
            id_rol_nuevo is not None
            and id_rol_nuevo != usuario.id_rol
        )

        if rol_modificado:
            # Un usuario administrativo no puede cambiar su propio rol.
            if id_usuario == usuario_actual.id_usuario:
                raise ValidationError(
                    code="RESTRICCION_AUTOEDICION_ADMIN",
                    message=(
                        "Operación no permitida. Por seguridad, no puede "
                        "cambiar el rol de su propia cuenta."
                    ),
                    field="id_rol",
                )

            # El nuevo rol debe existir.
            if self.roles_repo.obtener_por_id(id_rol_nuevo) is None:
                raise ValidationError(
                    code="ROL_NO_EXISTE",
                    message="El rol asignado no existe en el sistema.",
                    field="id_rol",
                )

        # 3. Construir los cambios.
        correo_modificado = (
            dto.correo_electronico is not None
            and str(dto.correo_electronico) != str(usuario.correo)
        )

        nuevo_correo = (
            str(dto.correo_electronico)
            if correo_modificado
            else None
        )

        cambios = {
            "nombre": dto.nombre,
            "apellidos": dto.apellidos,
        }

        if dto.correo_electronico is not None:
            cambios["correo_electronico"] = str(dto.correo_electronico)

        if dto.telefono is not None:
            cambios["telefono"] = dto.telefono

        if dto.direccion is not None:
            cambios["direccion"] = dto.direccion

        if rol_modificado:
            cambios["id_rol"] = id_rol_nuevo

        valores_anteriores = {
            campo: _valor_columna(usuario, campo)
            for campo in cambios
        }

        # 4. Obtener la cuenta asociada.
        cuenta_objetivo = self.cuentas_repo.obtener_por_usuario(
            usuario.id_usuario
        )

        # El correo únicamente puede cambiarse si la cuenta está activa.
        if (
            correo_modificado
            and cuenta_objetivo is not None
            and cuenta_objetivo.id_estado_cuenta != Cuenta.ESTADO_ACTIVO
        ):
            raise BusinessRuleError(
                code="CUENTA_NO_ACTIVA",
                message=(
                    "No se puede cambiar el correo electrónico porque "
                    "la cuenta no está activa."
                ),
                field="correo_electronico",
            )

        # 5. Proteger el último usuario activo de cualquier rol protegido.
        if (
            rol_modificado
            and cuenta_objetivo is not None
            and cuenta_objetivo.esta_activa()
        ):
            rol_actual = self.roles_repo.obtener_por_id(usuario.id_rol)

            if (
                rol_actual is not None
                and rol_actual.es_protegido
                and self.cuentas_repo.contar_usuarios_activos_por_rol(
                    usuario.id_rol
                ) <= 1
            ):
                raise BusinessRuleError(
                    code="ULTIMO_ADMIN_PROTEGIDO",
                    message=(
                        "Operación denegada por seguridad. No se puede "
                        "reasignar al último usuario activo de un rol protegido."
                    ),
                    field="id_rol",
                )

        # El rol forma parte del JWT. Cuando cambia el rol se invalidan las
        # sesiones para que los nuevos permisos se apliquen en el siguiente login.
        if (
            correo_modificado or rol_modificado
        ) and cuenta_objetivo is not None:
            self.sesiones_repo.invalidar_todas_sesiones(
                cuenta_objetivo.id_cuenta_usuario
            )

        token_verificacion = None

        try:
            # 6. Aplicar cambios al usuario.
            usuario.nombre = cambios["nombre"]
            usuario.apellidos = cambios["apellidos"]

            if "correo_electronico" in cambios:
                usuario.correo = Email(
                    cambios["correo_electronico"]
                )

            if "telefono" in cambios:
                usuario.telefono = cambios["telefono"]

            if "direccion" in cambios:
                usuario.direccion = cambios["direccion"]

            if "id_rol" in cambios:
                usuario.id_rol = cambios["id_rol"]

            usuario = self.usuarios_repo.actualizar(
                usuario,
                dto.version,
            )

            # 7. Si cambia el correo, la cuenta vuelve a estado pendiente.
            if correo_modificado and cuenta_objetivo is not None:
                token_verificacion = secrets.token_urlsafe(32)

                cuenta_objetivo.poner_pendiente(
                    token_verificacion,
                    datetime.now(timezone.utc),
                )

                self.cuentas_repo.guardar(cuenta_objetivo)

            # 8. Registrar auditoría.
            tipo_actor = (
                "Administrador"
                if es_edicion_administrativa
                else "Usuario"
            )

            self.eventos_repo.registrar(
                tipo_evento=TIPO_EVENTO_ACTUALIZACION_PERFIL,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "id_usuario_modificado": id_usuario,
                    "tipo_actor": tipo_actor,
                    "campos_modificados": list(cambios.keys()),
                    "valores_anteriores": valores_anteriores,
                    "valores_nuevos": {
                        campo: _valor_columna(usuario, campo)
                        for campo in cambios
                    },
                },
            )

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

        # 9. Enviar verificación si cambió el correo.
        if correo_modificado and token_verificacion is not None:
            send_email(
                to=nuevo_correo,
                subject="Verifica tu nuevo correo en SGPMP",
                html_body=activation_email(
                    usuario.nombre,
                    token_verificacion,
                ),
            )

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_EVENTO_ACTUALIZACION_PERFIL,
                id_usuario=id_usuario,
                correo_destino=str(usuario.correo),
            )

        return usuario