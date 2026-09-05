"""Caso de uso: alta de usuario vía sincronización server-to-server (`CREATE_USER`).

Mecanismo B de AgroFusion — camino primario de auto-provisión (el 90% del
caso feliz según el análisis de referencia): a diferencia del autorregistro
normal, la cuenta nace **activa de inmediato**, sin flujo de activación por
correo, porque AgroFusion ya validó la identidad del usuario.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.infrastructure.dto.agrofusion_dto import AgroFusionCreateUserDTO

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

    def execute(self, dto: AgroFusionCreateUserDTO) -> Usuario:
        """Crea un usuario y su cuenta, ya activa, resolviendo el rol destino.

        Args:
            dto: Datos completos del usuario a crear, incluyendo el
                ``rol_codigo`` que AgroFusion espera mapear a un rol de sgpmp.

        Returns:
            La entidad :class:`Usuario` creada.

        Raises:
            ConflictError: El correo o número de identificación ya existen. HTTP 409.
            ValidationError: Algún campo no cumple las reglas de dominio. HTTP 400.
        """
        # rol_codigo debe matchear exactamente (case-insensitive) contra
        # modulo1.roles.nombre_rol; si no viene o no matchea, Usuario.registrar_nuevo
        # cae al rol por defecto (ROL_PRODUCTOR) — mismo fallback que describe
        # el diseño en anotaciones/modulo_1/plan_sso_agrofusion.md.
        id_rol = None
        if dto.rol_codigo:
            rol = self.roles_repo.obtener_por_nombre(dto.rol_codigo)
            if rol is not None:
                id_rol = rol.id_rol

        try:
            usuario = Usuario.registrar_nuevo(
                correo=Email(dto.correo_electronico),
                contrasena=Contrasena.cifrar(secrets.token_urlsafe(32)),
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

            cuenta = self.cuentas_repo.crear(usuario.id_usuario, secrets.token_urlsafe(32))
            cuenta.activar(datetime.now(timezone.utc))
            self.cuentas_repo.guardar(cuenta)

            self.eventos_repo.registrar(
                tipo_evento=TIPO_PROVISION_AGROFUSION_SYNC,
                exitoso=True,
                id_usuario=usuario.id_usuario,
                detalle={"rol_codigo": dto.rol_codigo, "id_rol_resuelto": usuario.id_rol},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return usuario
