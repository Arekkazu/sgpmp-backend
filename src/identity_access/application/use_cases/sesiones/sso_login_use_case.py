"""Caso de uso: inicio de sesión vía SSO de AgroFusion (Mecanismo A).

Verifica un token de handoff RS256 emitido por AgroFusion y, según si el
correo ya existe en sgpmp, reutiliza la cuenta existente o provisiona una
cuenta mínima (ver :meth:`Usuario.crear_minimo_sso`). El resto del flujo
—invalidar sesión previa, emitir JWT, registrar sesión— es idéntico al login
por contraseña y se reutiliza vía ``sesion_comun``.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.sesiones.sesion_comun import (
    emitir_sesion,
    verificar_estado_cuenta,
)
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.domain.repositories.sso_provider_port import SsoProviderPort
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.infrastructure.dto.usuario_dto import SsoLoginDTO

# modulo1.tipos_eventos — ver anotaciones/modulo_1/gaps_bd_sso_agrofusion.md
TIPO_LOGIN_SSO_EXITOSO = 20
TIPO_PROVISION_SSO_MINIMA = 21

# modulo1.roles — rol de mínimo privilegio (cero permisos) para cuentas SSO
# provistas sin sincronización previa de AgroFusion. Ver mismo gaps doc.
ROL_EXTERNO_AGROFUSION = 9


class SsoLoginUseCase:
    """Orquesta el login vía handoff SSO de AgroFusion."""

    def __init__(
        self,
        sso_provider: SsoProviderPort,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        sesiones_repo: SesionRepository,
        eventos_repo: EventoRepository,
        db: Session,
        notificacion_service=None,
    ):
        """Inicializa el use case con sus dependencias.

        Args:
            sso_provider: Puerto de verificación del token SSO externo.
            usuarios_repo: Repositorio de dominio del agregado Usuario.
            cuentas_repo: Repositorio de dominio del agregado Cuenta.
            sesiones_repo: Repositorio de dominio de sesiones y tokens.
            eventos_repo: Repositorio de dominio de eventos (auditoría).
            db: Sesión SQLAlchemy activa del request.
            notificacion_service: Servicio de notificaciones opcional.
        """
        self.sso_provider = sso_provider
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.sesiones_repo = sesiones_repo
        self.eventos_repo = eventos_repo
        self.db = db
        self.notificacion_service = notificacion_service

    def execute(self, dto: SsoLoginDTO, ip: str, user_agent: str) -> tuple[str, datetime, bool, int, bool]:
        """Autentica vía SSO y crea una nueva sesión activa.

        Args:
            dto: Token de handoff SSO recibido del frontend.
            ip: Dirección IP del cliente.
            user_agent: Cadena User-Agent del cliente.

        Returns:
            Tupla ``(jwt_str, fecha_expiracion, sesion_previa_cerrada, id_usuario,
            perfil_incompleto)``. ``perfil_incompleto`` es ``True`` si la cuenta
            quedó (o seguía) en estado ``PENDIENTE_DATOS``.

        Raises:
            AuthenticationError: Token SSO inválido/expirado. HTTP 401.
            LockedError: Cuenta existente bloqueada temporalmente. HTTP 423.
            AuthorizationError: Cuenta existente inactiva o eliminada. HTTP 403.
        """
        # 1. Verificar identidad federada (sin tocar DB todavía)
        identidad = self.sso_provider.verificar(dto.sso_token)
        ahora = datetime.now(timezone.utc)

        # 2. Buscar usuario existente por correo
        usuario = self.usuarios_repo.obtener_por_correo(identidad.email)

        if usuario is None:
            usuario, cuenta = self._provisionar_minimo(identidad, ip, ahora)
        else:
            cuenta = self.cuentas_repo.obtener_por_usuario(usuario.id_usuario)
            if cuenta.esta_pendiente():
                # AgroFusion ya verificó la identidad: activar directo, no tiene
                # sentido pedir que confirme un correo ya confirmado en la
                # plataforma central.
                try:
                    cuenta.activar(ahora)
                    cuenta = self.cuentas_repo.guardar(cuenta)
                    self.db.commit()
                except Exception:
                    self.db.rollback()
                    raise
            else:
                verificar_estado_cuenta(cuenta, usuario, self.cuentas_repo, self.db, ahora)

        # 3. Emitir sesión — idéntico al login normal, sin validar contraseña
        jwt_str, fecha_expiracion, sesion_previa_cerrada = emitir_sesion(
            usuario=usuario,
            cuenta=cuenta,
            ip=ip,
            user_agent=user_agent,
            tipo_evento_exitoso=TIPO_LOGIN_SSO_EXITOSO,
            sesiones_repo=self.sesiones_repo,
            cuentas_repo=self.cuentas_repo,
            eventos_repo=self.eventos_repo,
            db=self.db,
            ahora=ahora,
            detalle_extra={"mecanismo": "sso_agrofusion", "emisor": identidad.emisor},
        )

        if self.notificacion_service:
            self.notificacion_service.notificar(
                tipo_evento=TIPO_LOGIN_SSO_EXITOSO,
                id_usuario=usuario.id_usuario,
                correo_destino=str(usuario.correo),
            )

        return jwt_str, fecha_expiracion, sesion_previa_cerrada, usuario.id_usuario, cuenta.esta_pendiente_datos()

    def _provisionar_minimo(self, identidad, ip: str, ahora: datetime) -> tuple[Usuario, Cuenta]:
        """Crea una cuenta mínima cuando el correo no existía todavía en sgpmp.

        Camino de respaldo del Mecanismo A: no hay sincronización previa
        (Mecanismo B `CREATE_USER`) que ya haya traído los datos completos.
        """
        try:
            contrasena_inutilizable = Contrasena.cifrar(secrets.token_urlsafe(32))
            usuario = Usuario.crear_minimo_sso(
                correo=identidad.email,
                contrasena=contrasena_inutilizable,
                id_rol=ROL_EXTERNO_AGROFUSION,
            )
            usuario = self.usuarios_repo.guardar(usuario)

            # Se crea directo en PENDIENTE_DATOS (sin token de activación: no
            # aplica un flujo de verificación por correo aquí) para no pasar
            # por una transición Pendiente→PendienteDatos que el trigger de
            # validación de transiciones de modulo1.cuentas_usuarios no permite.
            cuenta = self.cuentas_repo.crear(usuario.id_usuario, None, Cuenta.ESTADO_PENDIENTE_DATOS)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_PROVISION_SSO_MINIMA,
                exitoso=True,
                id_usuario=usuario.id_usuario,
                detalle={"ip": ip, "emisor": identidad.emisor, "sub_externo": identidad.sub_externo},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return usuario, cuenta
