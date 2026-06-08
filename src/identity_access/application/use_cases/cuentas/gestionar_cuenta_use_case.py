"""Caso de uso: gestión administrativa del estado de una cuenta de usuario.

Permite a un administrador activar, inactivar, bloquear o eliminar la cuenta
de otro usuario. Protege al último administrador activo y valida las
transiciones de estado permitidas.
"""
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.dto.gestion_cuenta_dto import GestionarCuentaDTO
from src.identity_access.infrastructure.models.enums_models import EnumAccionCuenta, EnumEventoResultado
from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError, ValidationError

ROL_ADMINISTRADOR = 1

ACCION_A_ESTADO = {
    EnumAccionCuenta.ACTIVAR:   2,
    EnumAccionCuenta.INACTIVAR: 3,
    EnumAccionCuenta.BLOQUEAR:  4,
    EnumAccionCuenta.ELIMINAR:  5,
}

TRANSICIONES_VALIDAS = {
    1: {2, 5},
    2: {1, 3, 4, 5},
    3: {2, 5},
    4: {2, 3, 5},
}

ESTADOS_QUE_INVALIDAN_SESION = {3, 4, 5}
ACCIONES_CRITICAS = {EnumAccionCuenta.INACTIVAR, EnumAccionCuenta.ELIMINAR}
ACCIONES_QUE_REDUCEN_ADMINS = {EnumAccionCuenta.INACTIVAR, EnumAccionCuenta.BLOQUEAR, EnumAccionCuenta.ELIMINAR}
TIPO_CAMBIO_ESTADO = 10

_MOTIVO_DEFAULT = "Acción administrativa"


class GestionarCuentaUseCase:
    """Orquesta el cambio de estado de la cuenta de un usuario por un administrador."""

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        cuentas_port: CuentasPort,
        sesiones_port: SesionesPort,
        db: Session,
        notificacion_service=None,
    ):
        """Inicializa el use case.

        Args:
            usuarios_port: Acceso a datos de usuarios.
            cuentas_port: Acceso a datos de cuentas y gestiones.
            sesiones_port: Invalidación de sesiones y auditoría.
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones opcional.
        """
        self.usuarios_port = usuarios_port
        self.cuentas_port = cuentas_port
        self.sesiones_port = sesiones_port
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, id_usuario: int, dto: GestionarCuentaDTO, usuario_actual: UsuarioActual) -> None:
        """Aplica la acción de gestión sobre la cuenta del usuario indicado.

        Args:
            id_usuario: ID del usuario cuya cuenta se va a gestionar.
            dto: Datos de la acción (acción a ejecutar y motivo opcional).
            usuario_actual: Usuario administrador que ejecuta la acción.

        Raises:
            AuthorizationError: Si el actor no es administrador o intenta
                gestionar su propia cuenta. HTTP 403.
            NotFoundError: Si el usuario o su cuenta no existen. HTTP 404.
            ValidationError: Si la acción crítica no tiene motivo, o la cuenta
                ya está en el estado solicitado. HTTP 400.
            BusinessRuleError: Si la transición de estado no es válida o se
                intenta desactivar al único administrador activo. HTTP 422.
        """
        # 1. Solo administradores
        if usuario_actual.id_rol != ROL_ADMINISTRADOR:
            raise AuthorizationError(
                code="ACCESO_DENEGADO",
                message=(
                    "Acceso denegado. Se requieren privilegios administrativos para gestionar "
                    "estados de cuenta. Este intento de acceso ha sido registrado en el log de auditoría."
                ),
            )

        # 2. Admin no puede gestionar su propia cuenta
        if id_usuario == usuario_actual.id_usuario:
            raise AuthorizationError(
                code="AUTOEDICION_ESTADO_PROHIBIDA",
                message=(
                    "Operación no permitida. Un administrador no puede gestionar el estado "
                    "de su propia cuenta."
                ),
            )

        # 3. Buscar usuario y cuenta
        usuario = self.usuarios_port.buscar_por_id(id_usuario)
        if usuario is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message=f"Error de referencia. El usuario con ID {id_usuario} no existe en los registros actuales del sistema.",
            )

        cuenta = self.cuentas_port.buscar_cuenta_por_usuario(id_usuario)
        if cuenta is None:
            raise NotFoundError(
                code="CUENTA_NO_ENCONTRADA",
                message=f"El usuario con ID {id_usuario} no tiene una cuenta asociada.",
            )

        # 4. Motivo obligatorio para acciones críticas
        motivo = dto.motivo_accion
        if dto.accion_cuenta in ACCIONES_CRITICAS and not motivo:
            raise ValidationError(
                code="MOTIVO_REQUERIDO",
                message=(
                    "Campo obligatorio faltante. Para las acciones de Desactivación o Eliminación, "
                    "es obligatorio registrar una justificación en el campo 'motivo_accion' para fines de auditoría."
                ),
                field="motivo_accion",
            )
        motivo = motivo or _MOTIVO_DEFAULT

        # 5. Determinar estado destino y validar transición
        nuevo_estado = ACCION_A_ESTADO[dto.accion_cuenta]
        estado_actual = cuenta.id_estado_cuenta

        if nuevo_estado == estado_actual:
            raise ValidationError(
                code="ESTADO_SIN_CAMBIO",
                message=f"Inconsistencia de estado. La cuenta ya se encuentra en el estado solicitado.",
            )

        if estado_actual == 5:
            raise BusinessRuleError(
                code="TRANSICION_INVALIDA",
                message=(
                    "Transición de estado inválida. Una cuenta en estado 'ELIMINADO' tiene carácter "
                    f"irreversible para preservar la integridad histórica. No se permite el cambio a estado {nuevo_estado}."
                ),
            )

        if nuevo_estado not in TRANSICIONES_VALIDAS.get(estado_actual, set()):
            raise BusinessRuleError(
                code="TRANSICION_INVALIDA",
                message=f"Transición de estado inválida ({estado_actual} → {nuevo_estado}).",
            )

        # 6. Protección del último administrador activo
        if usuario.id_rol == ROL_ADMINISTRADOR and dto.accion_cuenta in ACCIONES_QUE_REDUCEN_ADMINS:
            if self.cuentas_port.contar_admins_activos() <= 1:
                raise BusinessRuleError(
                    code="ULTIMO_ADMIN_PROTEGIDO",
                    message=(
                        f"Operación denegada por seguridad. El usuario {id_usuario} es el único "
                        "administrador activo del sistema. Debe designar y activar un nuevo "
                        "administrador antes de proceder con la desactivación o eliminación."
                    ),
                )

        # 7. Revocar sesiones ANTES del flush del estado (trigger las desactiva después)
        if nuevo_estado in ESTADOS_QUE_INVALIDAN_SESION:
            self.sesiones_port.invalidar_todas_sesiones(cuenta.id_cuenta_usuario)

        try:
            # 8. Actualizar estado
            cuenta.id_estado_cuenta = nuevo_estado
            cuenta.motivo_ultimo_cambio = motivo
            self.db.flush()

            # 9. Registrar en gestiones_cuenta
            self.cuentas_port.registrar_gestion(
                id_cuenta_usuario=cuenta.id_cuenta_usuario,
                accion=dto.accion_cuenta.value,
                motivo=motivo,
                id_responsable=usuario_actual.id_usuario,
            )

            # 10. Registrar evento de auditoría
            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_CAMBIO_ESTADO,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "id_usuario_afectado": id_usuario,
                    "accion": dto.accion_cuenta.value,
                    "estado_anterior": estado_actual,
                    "estado_nuevo": nuevo_estado,
                    "motivo": motivo,
                },
            )

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_CAMBIO_ESTADO,
                id_usuario=id_usuario,
                correo_destino=usuario.correo_electronico,
            )
