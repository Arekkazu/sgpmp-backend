"""Implementación SQLAlchemy del port de cuentas de usuario.

Gestiona el ciclo de vida del estado de cuenta, tokens de activación/recuperación
y el control de intentos fallidos con bloqueo temporal.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.cuentas_ports import CuentasPort
from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios
from src.identity_access.infrastructure.models.enums_models import EnumAccionCuenta
from src.identity_access.infrastructure.models.gestiones_cuenta_model import GestionesCuenta
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import FlowError, GoneError, ValidationError

ROL_ADMINISTRADOR = 1
ESTADO_ACTIVO = 2

ESTADO_PENDIENTE_ACTIVACION = 1
ESTADO_ACTIVO = 2
ESTADO_BLOQUEADO = 4
TOKEN_EXPIRACION_HORAS = 24
MAX_INTENTOS_FALLIDOS = 5
MINUTOS_BLOQUEO = 15


class CuentasSQLRepository(CuentasPort):
    """Repositorio SQLAlchemy para `CuentasUsuarios` y `GestionesCuenta`."""

    def __init__(self, db: Session):
        self.db = db

    def create_cuenta(self, id_usuario: int, token: str) -> CuentasUsuarios:
        cuenta = CuentasUsuarios(
            id_usuario=id_usuario,
            id_estado_cuenta=ESTADO_PENDIENTE_ACTIVACION,
            token_activacion_actual=token,
        )
        try:
            self.db.add(cuenta)
            self.db.flush()
            self.db.refresh(cuenta)
            return cuenta
        except Exception as e:
            raise_from_db_error(e, conflict_messages={
                "uq_usuario": "El usuario ya tiene una cuenta asociada",
            })

    def activar_cuenta(self, token: str) -> CuentasUsuarios:
        cuenta = (
            self.db.query(CuentasUsuarios)
            .filter(CuentasUsuarios.token_activacion_actual == token)
            .first()
        )

        if cuenta is None:
            raise ValidationError(
                code="TOKEN_INVALIDO",
                message="El token de activación es inválido o inexistente.",
            )

        ahora = datetime.now(timezone.utc)
        expiracion = cuenta.fecha_cambio_estado.replace(tzinfo=timezone.utc) + timedelta(hours=TOKEN_EXPIRACION_HORAS)
        if ahora > expiracion:
            raise GoneError(
                code="TOKEN_EXPIRADO",
                message=f"El token de activación expiró el {expiracion.strftime('%d/%m/%Y')} a las {expiracion.strftime('%H:%M:%S')}. Solicita uno nuevo.",
            )

        if cuenta.id_estado_cuenta == ESTADO_ACTIVO:
            raise FlowError(
                code="CUENTA_YA_ACTIVA",
                message="La cuenta ya fue activada anteriormente.",
            )

        try:
            cuenta.id_estado_cuenta = ESTADO_ACTIVO
            cuenta.tiene_correo_verificado = True
            cuenta.fecha_verificacion = ahora
            cuenta.token_activacion_actual = None
            cuenta.fecha_cambio_estado = ahora
            self.db.commit()
            self.db.refresh(cuenta)
            return cuenta
        except Exception as e:
            self.db.rollback()
            raise_from_db_error(e, conflict_messages={})

    def reenviar_token(self, correo_electronico: str, nuevo_token: str) -> str:
        usuario = (
            self.db.query(Usuarios)
            .filter(Usuarios.correo_electronico == correo_electronico)
            .first()
        )

        if usuario is None:
            raise ValidationError(
                code="CORREO_NO_REGISTRADO",
                message="No existe una cuenta asociada a ese correo electrónico.",
                field="correo_electronico",
            )

        cuenta = (
            self.db.query(CuentasUsuarios)
            .filter(CuentasUsuarios.id_usuario == usuario.id_usuario)
            .first()
        )

        if cuenta.id_estado_cuenta == ESTADO_ACTIVO:
            raise FlowError(
                code="CUENTA_YA_ACTIVA",
                message="La cuenta ya está activa. Puedes iniciar sesión directamente.",
            )

        if cuenta.id_estado_cuenta != ESTADO_PENDIENTE_ACTIVACION:
            raise FlowError(
                code="ESTADO_CUENTA_INVALIDO",
                message="La cuenta no puede recibir un nuevo token en su estado actual.",
            )

        cuenta.token_activacion_actual = nuevo_token
        cuenta.fecha_cambio_estado = datetime.now(timezone.utc)

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise_from_db_error(e, conflict_messages={})

        return usuario.nombre

    def buscar_cuenta_por_usuario(self, id_usuario: int) -> Optional[CuentasUsuarios]:
        return (
            self.db.query(CuentasUsuarios)
            .filter(CuentasUsuarios.id_usuario == id_usuario)
            .first()
        )

    def incrementar_intentos_fallidos(self, cuenta: CuentasUsuarios) -> None:
        cuenta.intentos_fallidos += 1
        cuenta.ultimo_intento_fallido = datetime.now(timezone.utc)
        self.db.flush()

    def bloquear_cuenta(self, cuenta: CuentasUsuarios) -> None:
        cuenta.id_estado_cuenta = ESTADO_BLOQUEADO
        cuenta.bloqueado_hasta = datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_BLOQUEO)
        self.db.flush()

    def resetear_intentos(self, cuenta: CuentasUsuarios) -> None:
        cuenta.intentos_fallidos = 0
        cuenta.ultimo_intento_fallido = None
        self.db.flush()

    def actualizar_ultimo_acceso(self, cuenta: CuentasUsuarios) -> None:
        cuenta.ultimo_acceso = datetime.now(timezone.utc)
        self.db.flush()

    def poner_cuenta_pendiente(self, cuenta: CuentasUsuarios, nuevo_token: str) -> None:
        cuenta.id_estado_cuenta = ESTADO_PENDIENTE_ACTIVACION
        cuenta.token_activacion_actual = nuevo_token
        cuenta.fecha_cambio_estado = datetime.now(timezone.utc)
        self.db.flush()

    def guardar_token_recuperacion(self, cuenta: CuentasUsuarios, token: str) -> None:
        # Reutiliza token_activacion_actual — la misma columna sirve para activación y recuperación.
        cuenta.token_activacion_actual = token
        cuenta.fecha_cambio_estado = datetime.now(timezone.utc)
        self.db.flush()

    def buscar_cuenta_por_token_recuperacion(self, token: str) -> Optional[CuentasUsuarios]:
        return (
            self.db.query(CuentasUsuarios)
            .filter(CuentasUsuarios.token_activacion_actual == token)
            .first()
        )

    def incrementar_intentos_cambio_contrasena(self, cuenta: CuentasUsuarios) -> None:
        cuenta.intentos_fallidos += 1
        cuenta.ultimo_intento_fallido = datetime.now(timezone.utc)
        self.db.flush()

    def bloquear_cambio_contrasena(self, cuenta: CuentasUsuarios) -> None:
        cuenta.bloqueado_hasta = datetime.now(timezone.utc) + timedelta(minutes=30)
        self.db.flush()

    def resetear_intentos_cambio_contrasena(self, cuenta: CuentasUsuarios) -> None:
        cuenta.intentos_fallidos = 0
        cuenta.ultimo_intento_fallido = None
        cuenta.bloqueado_hasta = None
        self.db.flush()

    def registrar_gestion(
        self,
        id_cuenta_usuario: int,
        accion: str,
        motivo: str,
        id_responsable: int,
    ) -> None:
        gestion = GestionesCuenta(
            id_cuenta_usuario=id_cuenta_usuario,
            accion_cuenta=EnumAccionCuenta(accion),
            motivo_accion=motivo,
            fecha_accion=datetime.now(timezone.utc),
            id_usuario_responsable=id_responsable,
        )
        self.db.add(gestion)
        self.db.flush()

    def contar_admins_activos(self) -> int:
        return (
            self.db.query(CuentasUsuarios)
            .join(Usuarios, Usuarios.id_usuario == CuentasUsuarios.id_usuario)
            .filter(
                Usuarios.id_rol == ROL_ADMINISTRADOR,
                CuentasUsuarios.id_estado_cuenta == ESTADO_ACTIVO,
            )
            .count()
        )
