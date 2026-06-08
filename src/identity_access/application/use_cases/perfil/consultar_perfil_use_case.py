"""Caso de uso: consulta del perfil propio del usuario autenticado.

Retorna los datos del usuario con el número de identificación parcialmente
enmascarado (primeros 4 dígitos visibles) y registra el acceso en auditoría.
"""
from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError

TIPO_CONSULTA_PERFIL_PROPIO = 19


class ConsultarPerfilUseCase:
    """Orquesta la consulta del perfil del usuario actualmente autenticado."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario (proyección de lectura).
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.usuarios_repo = usuarios_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, usuario_actual: UsuarioActual) -> dict:
        """Recupera los datos del perfil del usuario autenticado.

        Args:
            usuario_actual: Usuario autenticado extraído del JWT.

        Returns:
            Diccionario con los campos del perfil. El número de identificación
            aparece parcialmente enmascarado.

        Raises:
            NotFoundError: Si el registro del usuario no existe en la DB. HTTP 404.
        """
        detalle = self.usuarios_repo.obtener_detalle(usuario_actual.id_usuario)
        if detalle is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message="Error de perfil: No se pudo recuperar la información asociada a su cuenta. El registro no existe o ha sido desactivado.",
            )

        numero_identificacion = self._enmascarar(detalle.numero_identificacion)

        try:
            self.eventos_repo.registrar(
                tipo_evento=TIPO_CONSULTA_PERFIL_PROPIO,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle={},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "nombre": detalle.nombre,
            "apellidos": detalle.apellidos,
            "correo_electronico": detalle.correo_electronico,
            "tipo_identificacion": detalle.tipo_identificacion,
            "numero_identificacion": numero_identificacion,
            "fecha_nacimiento": detalle.fecha_nacimiento,
            "fecha_registro": detalle.fecha_registro,
            "nombre_rol": detalle.nombre_rol,
            "estado_cuenta": detalle.estado_cuenta,
        }

    def _enmascarar(self, numero: str) -> str:
        """Enmascara el número de identificación dejando visibles los 4 primeros dígitos.

        Args:
            numero: Número de identificación completo.

        Returns:
            Número con los últimos caracteres reemplazados por asteriscos.
        """
        if len(numero) <= 4:
            return "*" * len(numero)
        return numero[:4] + "*" * (len(numero) - 4)
