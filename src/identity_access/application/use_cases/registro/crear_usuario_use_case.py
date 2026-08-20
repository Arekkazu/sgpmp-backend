"""Caso de uso: creación de un nuevo usuario en el sistema.

Construye la entidad de dominio :class:`Usuario` a partir del DTO de entrada,
valida la edad mínima usando la propia entidad, la persiste mediante el
repositorio de dominio y envía el correo de activación.

Este caso de uso es la *implementación de referencia* del patrón DDD del
proyecto: trabaja con la entidad y los value objects del dominio y no conoce
SQLAlchemy ni los modelos ORM. La única dependencia técnica que conserva es el
control transaccional (``commit``/``rollback``), que por decisión del proyecto
(ver ``CLAUDE.md``) vive en el caso de uso y no en un *Unit of Work*.
"""
import secrets

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.usuario import Usuario
from src.identity_access.domain.repositories.cuenta_repository import CuentaRepository
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.contrasena import Contrasena
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.infrastructure.dto.usuario_dto import UsuarioCreateDTO
from src.identity_access.infrastructure.email_templates import activation_email
from src.shared.email import send_email
from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token
from src.shared.errors import AuthorizationError

TIPO_REGISTRO_USUARIO = 1

class CrearUsuarioUseCase:
    """Orquesta el registro de un nuevo usuario con envío de correo de activación."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        cuentas_repo: CuentaRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario.
            eventos_repo: Repositorio utilizado para registrar eventos de auditoría.
            cuentas_repo: Repositorio de dominio del agregado Cuenta (alta en estado PENDIENTE).
            db: Sesión SQLAlchemy activa del request, usada solo para delimitar
                la transacción (``commit``/``rollback``).
        """
        self.usuarios_repo = usuarios_repo
        self.cuentas_repo = cuentas_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(
        self,
        dto: UsuarioCreateDTO,
        ip: str,
        user_agent: str,
    ) -> Usuario:
        """Registra el usuario, crea su cuenta y envía el correo de activación.

        Args:
            dto: Datos del nuevo usuario (nombre, correo, contraseña, etc.).
            ip: Dirección IP asociada a la solicitud.
            user_agent: Cliente o navegador desde el cual se realiza la solicitud.
        Returns:
            La entidad :class:`Usuario` creada, con su identidad asignada.

        Raises:
            ValidationError: Si el correo o la contraseña no son válidos. HTTP 400.
            AuthorizationError: Si la edad es menor de 18 años. HTTP 403.
            ConflictError: Si el correo o la identificación ya están registrados.
                HTTP 409.
        """
        # 1. Value objects: validan formato y política al construirse.
        correo = Email(dto.correo_electronico)
        contrasena = Contrasena.desde_texto_plano(dto.contrasena)

        # 2. Entidad de dominio mediante su factory (fija rol e invariantes de alta).
        usuario = Usuario.registrar_nuevo(
            correo=correo,
            contrasena=contrasena,
            nombre=dto.nombre,
            apellidos=dto.apellidos,
            fecha_nacimiento=dto.fecha_nacimiento,
            genero=dto.genero.value,
            tipo_identificacion=dto.tipo_identificacion,
            numero_identificacion=dto.numero_identificacion,
            telefono=dto.telefono,
            direccion=dto.direccion,
        )

        # 3. Regla de negocio que vive en la entidad, no en el caso de uso.
        if not usuario.es_mayor_de_edad():
            raise AuthorizationError(
                code="EDAD_MINIMA_REQUERIDA",
                message="Registro denegado: debe ser mayor de 18 años para registrarse como responsable de una unidad productiva en el sistema.",
                field="fecha_nacimiento",
            )

        # 4. Persistencia vía repositorio de dominio + cuenta asociada.
        try:
            usuario = self.usuarios_repo.guardar(usuario)
            token = secrets.token_urlsafe(32)
            self.cuentas_repo.crear(usuario.id_usuario, calcular_hash_token(token))
            self.eventos_repo.registrar(
                tipo_evento=TIPO_REGISTRO_USUARIO,
                exitoso=True,
                id_usuario=usuario.id_usuario,
                detalle={
                    "accion": "registro_usuario",
                    "id_usuario_creado": usuario.id_usuario,
                    "id_rol_asignado": usuario.id_rol,
                    "estado_cuenta": "PENDIENTE",
                    "ip": ip,
                    "user_agent": user_agent[:255],
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # 5. Notificación fuera de la transacción (CLAUDE.md: tras el commit).
        send_email(
            to=str(usuario.correo),
            subject="Activa tu cuenta en SGPMP",
            html_body=activation_email(usuario.nombre, token),
        )

        return usuario
