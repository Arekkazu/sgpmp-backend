"""Caso de uso: renovar el access token a partir de un refresh token vigente.

Sin credenciales: la confianza la da el valor opaco de alta entropía que solo
el navegador conoce (transportado por cookie ``HttpOnly``, nunca leído por JS).
Aplica rotación (cada uso invalida el refresh token usado y emite uno nuevo) y
detección de reuso (presentar un refresh token ya rotado es señal de robo →
se revoca la sesión completa). Ver diseño completo en
``anotaciones/modulo_1/gaps_bd_refresh_tokens.md``.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.sesion_repository import SesionRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.shared.errors import AuthenticationError, GoneError
from src.shared.jwt import create_token, refresh_token_expiration, token_expiration

TIPO_REFRESH_TOKEN_ROTADO = 23
TIPO_REUSO_TOKEN_REFRESCO_DETECTADO = 24

INACTIVIDAD_MINUTOS = 30


class RefreshTokenUseCase:
    """Rota el par access/refresh token de una sesión vigente."""

    def __init__(
        self,
        sesiones_repo: SesionRepository,
        cuentas_repo: CuentaRepository,
        usuarios_repo: UsuarioRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        """Inicializa el use case con sus dependencias.

        Args:
            sesiones_repo: Repositorio de dominio de sesiones y tokens.
            cuentas_repo: Repositorio de dominio del agregado Cuenta.
            usuarios_repo: Repositorio de dominio del agregado Usuario.
            eventos_repo: Repositorio de dominio de eventos (auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.sesiones_repo = sesiones_repo
        self.cuentas_repo = cuentas_repo
        self.usuarios_repo = usuarios_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, refresh_token_raw: str, ip: str, user_agent: str) -> tuple[str, datetime, str, datetime]:
        """Canjea un refresh token vigente por un access token nuevo, rotando ambos.

        Args:
            refresh_token_raw: Valor en claro del refresh token, leído de la
                cookie ``HttpOnly`` por el router.
            ip: Dirección IP del cliente, para auditoría.
            user_agent: Cadena User-Agent del cliente, para auditoría.

        Returns:
            Tupla ``(jwt_str, fecha_expiracion, refresh_raw_nuevo, fecha_expiracion_refresco)``.

        Raises:
            AuthenticationError: Refresh token inexistente, reutilizado tras
                rotación (posible robo — revoca la sesión completa), sesión
                inválida, o sesión expirada por inactividad. HTTP 401.
            GoneError: Refresh token expirado. HTTP 410.
        """
        ahora = datetime.now(timezone.utc)
        hash_valor = hashlib.sha256(refresh_token_raw.encode()).hexdigest()
        token = self.sesiones_repo.buscar_token_por_hash(hash_valor)
        if token is None:
            raise AuthenticationError(
                code="REFRESH_TOKEN_INVALIDO",
                message="El refresh token no es válido.",
            )

        sesion = self.sesiones_repo.buscar_sesion_por_id(token.id_sesion) if token.id_sesion is not None else None
        cuenta = self.cuentas_repo.obtener_por_id(sesion.id_cuenta_usuario) if sesion is not None else None

        if token.esta_usado():
            # Reuso de un refresh token ya rotado: señal de robo. Se revoca el
            # par de tokens *vigente* de la sesión — nunca se vuelve a tocar
            # este token viejo, el trigger trg_token_un_solo_uso lo bloquearía.
            if sesion is not None and sesion.es_activa:
                self.sesiones_repo.invalidar_sesion(sesion)
                if cuenta is not None:
                    self.eventos_repo.registrar(
                        tipo_evento=TIPO_REUSO_TOKEN_REFRESCO_DETECTADO,
                        exitoso=False,
                        id_usuario=cuenta.id_usuario,
                        detalle={"ip": ip, "user_agent": user_agent[:255]},
                        id_sesion=sesion.id_sesion,
                    )
                self.db.commit()
            raise AuthenticationError(
                code="REFRESH_TOKEN_REUTILIZADO",
                message="Se detectó actividad sospechosa. La sesión fue cerrada por seguridad.",
            )

        if token.fecha_expiracion is not None and token.fecha_expiracion < ahora:
            if sesion is not None and sesion.es_activa:
                self.sesiones_repo.invalidar_sesion(sesion)
                self.db.commit()
            raise GoneError(
                code="REFRESH_TOKEN_EXPIRADO",
                message="La sesión expiró. Inicia sesión nuevamente.",
            )

        if sesion is None or not sesion.es_activa or cuenta is None:
            raise AuthenticationError(
                code="SESION_INVALIDA",
                message="La sesión ya no es válida. Inicia sesión nuevamente.",
            )

        # Inactividad (30 min) — mismo control que get_current_user aplica al
        # access token; un refresh NO cuenta como actividad real, así que no
        # actualiza cuenta.ultimo_acceso.
        if cuenta.ultimo_acceso is not None:
            ultimo_acceso = cuenta.ultimo_acceso
            if ultimo_acceso.tzinfo is None:
                ultimo_acceso = ultimo_acceso.replace(tzinfo=timezone.utc)
            if ahora - ultimo_acceso > timedelta(minutes=INACTIVIDAD_MINUTOS):
                self.sesiones_repo.invalidar_sesion(sesion)
                self.db.commit()
                raise AuthenticationError(
                    code="SESION_EXPIRADA_INACTIVIDAD",
                    message="Su sesión ha expirado por inactividad. Por favor, inicie sesión nuevamente.",
                )

        usuario = self.usuarios_repo.obtener_por_id(cuenta.id_usuario)

        try:
            nueva_fecha_expiracion = token_expiration()
            nuevo_token_acceso = self.sesiones_repo.crear_token_acceso(nueva_fecha_expiracion)
            jwt_str, _ = create_token(nuevo_token_acceso.id_token, usuario.id_usuario, usuario.id_rol)

            nuevo_refresh_raw = secrets.token_urlsafe(32)
            nuevo_hash = hashlib.sha256(nuevo_refresh_raw.encode()).hexdigest()
            nueva_fecha_expiracion_refresco = refresh_token_expiration()
            nuevo_token_refresco = self.sesiones_repo.crear_token_refresco(nueva_fecha_expiracion_refresco, nuevo_hash)

            sesion_actualizada = self.sesiones_repo.rotar_tokens(
                sesion=sesion,
                nuevo_id_token_acceso=nuevo_token_acceso.id_token,
                nuevo_id_token_refresco=nuevo_token_refresco.id_token,
                nueva_fecha_expiracion=nueva_fecha_expiracion,
            )
            self.sesiones_repo.vincular_token_a_sesion(nuevo_token_refresco.id_token, sesion_actualizada.id_sesion)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_REFRESH_TOKEN_ROTADO,
                exitoso=True,
                id_usuario=usuario.id_usuario,
                detalle={"ip": ip, "user_agent": user_agent[:255]},
                id_sesion=sesion_actualizada.id_sesion,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return jwt_str, nueva_fecha_expiracion, nuevo_refresh_raw, nueva_fecha_expiracion_refresco
