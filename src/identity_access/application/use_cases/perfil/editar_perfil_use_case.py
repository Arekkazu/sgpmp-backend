import secrets
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilAdminDTO
from src.identity_access.infrastructure.email_templates import activation_email
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.email import send_email
from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError, ValidationError

ROL_ADMINISTRADOR = 1
ESTADO_ACTIVO = 2
ESTADOS_QUE_INVALIDAN_SESION = {3, 4, 5}  # Inactivo, Bloqueado, Eliminado
TIPO_EVENTO_ACTUALIZACION_PERFIL = 9

TRANSICIONES_VALIDAS = {
    1: {2, 5},          # Pendiente → Activo, Eliminado
    2: {1, 3, 4, 5},    # Activo → Pendiente, Inactivo, Bloqueado, Eliminado
    3: {2, 5},          # Inactivo → Activo, Eliminado
    4: {2, 3, 5},       # Bloqueado → Activo, Inactivo, Eliminado
    # Eliminado (5) no tiene transiciones salientes
}


class EditarPerfilUseCase:

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        cuentas_port: CuentasPort,
        sesiones_port: SesionesPort,
        db: Session,
        notificacion_service=None,
    ):
        self.usuarios_port = usuarios_port
        self.cuentas_port = cuentas_port
        self.sesiones_port = sesiones_port
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, id_usuario: int, dto: EditarPerfilAdminDTO, usuario_actual: UsuarioActual) -> Usuarios:
        es_admin = usuario_actual.id_rol == ROL_ADMINISTRADOR

        # 1. Buscar usuario objetivo
        usuario = self.usuarios_port.buscar_por_id(id_usuario)
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
            if dto.id_rol is not None and not self.usuarios_port.verificar_rol_existe(dto.id_rol):
                raise ValidationError(
                    code="ROL_NO_EXISTE",
                    message="El rol asignado no existe en el sistema.",
                    field="id_rol",
                )

        # 3. Construir dict de cambios y capturar valores anteriores
        correo_modificado = (
            dto.correo_electronico is not None
            and str(dto.correo_electronico) != usuario.correo_electronico
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

        valores_anteriores = {campo: getattr(usuario, campo, None) for campo in cambios}

        nuevo_estado = dto.id_estado_cuenta if (es_admin and dto.id_estado_cuenta is not None) else None
        estado_invalida_sesion = nuevo_estado in ESTADOS_QUE_INVALIDAN_SESION if nuevo_estado else False

        # 4. Revocar sesión activa ANTES del flush de estado (el trigger la desactiva después)
        cuenta_objetivo = self.cuentas_port.buscar_cuenta_por_usuario(usuario.id_usuario)

        if (estado_invalida_sesion or correo_modificado) and cuenta_objetivo is not None:
            sesion_activa = self.sesiones_port.buscar_sesion_activa(cuenta_objetivo.id_cuenta_usuario)
            if sesion_activa is not None:
                self.sesiones_port.invalidar_sesion(sesion_activa)

        if correo_modificado and cuenta_objetivo is not None and cuenta_objetivo.id_estado_cuenta != ESTADO_ACTIVO:
            raise BusinessRuleError(
                code="CUENTA_NO_ACTIVA",
                message="No se puede cambiar el correo electrónico porque la cuenta no está activa.",
                field="correo_electronico",
            )

        token_verificacion = None
        try:
            # 5. Actualizar datos en tabla usuarios (con control de concurrencia)
            usuario = self.usuarios_port.actualizar_usuario(usuario, cambios, dto.version)

            if cuenta_objetivo is not None:
                self.db.refresh(cuenta_objetivo)

            # 6. Actualizar estado en cuentas_usuarios si admin lo modificó
            if nuevo_estado is not None and cuenta_objetivo is not None and nuevo_estado != cuenta_objetivo.id_estado_cuenta:
                estado_actual = cuenta_objetivo.id_estado_cuenta
                if nuevo_estado not in TRANSICIONES_VALIDAS.get(estado_actual, set()):
                    raise BusinessRuleError(
                        code="TRANSICION_INVALIDA",
                        message=f"No se puede cambiar el estado de la cuenta de {estado_actual} a {nuevo_estado} porque la transición no está permitida.",
                    )
                cuenta_objetivo.id_estado_cuenta = nuevo_estado
                self.db.flush()

            # 7. Poner cuenta en PENDIENTE si correo fue modificado
            if correo_modificado and cuenta_objetivo is not None:
                token_verificacion = secrets.token_urlsafe(32)
                self.cuentas_port.poner_cuenta_pendiente(cuenta_objetivo, token_verificacion)

            # 8. Registrar evento de auditoría
            tipo_actor = "Administrador" if es_admin else "Usuario"
            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_EVENTO_ACTUALIZACION_PERFIL,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "id_usuario_modificado": id_usuario,
                    "tipo_actor": tipo_actor,
                    "campos_modificados": list(cambios.keys()),
                    "valores_anteriores": valores_anteriores,
                    "valores_nuevos": {campo: getattr(usuario, campo, None) for campo in cambios},
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
                correo_destino=usuario.correo_electronico,
            )

        return usuario
