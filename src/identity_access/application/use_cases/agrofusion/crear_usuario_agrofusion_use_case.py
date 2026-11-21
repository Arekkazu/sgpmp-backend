# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | RFC-019 D-19.6: la cuenta nace activa con un token de activación para AgroFusion |
# | 2026-11-06 | Arekkazu | RF-SSO02: roles como lista de ids y contraseña inicial como los envía AgroFusion |
"""Caso de uso: alta de usuario vía sincronización server-to-server (`CREATE_USER`).

Mecanismo B de AgroFusion — camino primario de auto-provisión (el 90% del
caso feliz según el análisis de referencia): a diferencia del autorregistro
normal, la cuenta nace **activa de inmediato**, sin flujo de activación por
correo, porque AgroFusion ya validó la identidad del usuario. Aun así recibe un
token de activación (RFC-019 D-19.6) que AgroFusion usa después en
``ACTIVATE_ACCOUNT``; la activación con ese token responde 200 idempotente.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.agrofusion.comun import rol_solicitado
from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.domain.value_objects.token_un_solo_uso import PREFIJO_TOKEN_M2M, calcular_hash_token
from src.identity_access.infrastructure.dto.agrofusion_dto import AgroFusionCreateUserDTO
from src.shared.errors import ValidationError

# modulo1.tipos_eventos — ver anotaciones/modulo_1/gaps_bd_sso_agrofusion.md
TIPO_PROVISION_AGROFUSION_SYNC = 22


class CrearUsuarioAgroFusionUseCase:
    """Orquesta el alta de usuario solicitada por el Hub de AgroFusion."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        roles_repo: RolRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.roles_repo = roles_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, dto: AgroFusionCreateUserDTO) -> tuple[Usuario, str]:
        """Crea un usuario y su cuenta, ya activa, resolviendo el rol destino.

        Args:
            dto: Datos completos del usuario a crear, incluyendo el
                ``rol_codigo`` que AgroFusion espera mapear a un rol de sgpmp.

        Returns:
            La entidad :class:`Usuario` creada y su ``activation_token`` (24 h, RFC-019 D-19.6).

        Raises:
            ConflictError: El correo o número de identificación ya existen. HTTP 409.
            ValidationError: Algún campo no cumple las reglas de dominio. HTTP 400.
        """
        # Rol: el primer id de ``roles`` (de GET_ROLES) o ``rol_codigo``; sin ninguno, el rol por defecto
        # de Usuario.registrar_nuevo. Uno que no existe es un 400, no un rol cambiado en silencio.
        id_rol = rol_solicitado(self.roles_repo, dto.roles, dto.rol_codigo)
        # Contraseña inicial de AgroFusion si cumple la política de SGPMP; si no, una aleatoria (la
        # persona entra desde AgroFusion o recupera la contraseña).
        try:
            contrasena = Contrasena.cifrar(dto.contrasena) if dto.contrasena else None
        except ValidationError:
            contrasena = None
        try:
            usuario = Usuario.registrar_nuevo(
                correo=Email(dto.correo_electronico),
                contrasena=contrasena or Contrasena.cifrar(secrets.token_urlsafe(32)),
                nombre=dto.nombre,
                apellidos=dto.apellidos,
                fecha_nacimiento=dto.fecha_nacimiento,
                genero=dto.genero.value,
                tipo_identificacion=dto.tipo_identificacion,
                numero_identificacion=dto.numero_identificacion,
                telefono=dto.telefono,
                direccion=dto.direccion,
                id_rol=id_rol,
            )
            usuario = self.usuarios_repo.guardar(usuario)

            token_activacion = PREFIJO_TOKEN_M2M + secrets.token_urlsafe(32)
            cuenta = self.cuentas_repo.crear(usuario.id_usuario, calcular_hash_token(token_activacion))
            cuenta.activar(datetime.now(timezone.utc))
            cuenta.conservar_token_m2m(calcular_hash_token(token_activacion))
            self.cuentas_repo.guardar(cuenta)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_PROVISION_AGROFUSION_SYNC,
                exitoso=True,
                id_usuario=usuario.id_usuario,
                detalle={"roles": dto.roles, "rol_codigo": dto.rol_codigo, "id_rol_resuelto": usuario.id_rol,
                         "contrasena_inicial": contrasena is not None},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return usuario, token_activacion
