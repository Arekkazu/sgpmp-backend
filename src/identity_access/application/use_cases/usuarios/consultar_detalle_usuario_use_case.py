"""Caso de uso: consulta del detalle completo de un usuario por un administrador.

El número de identificación se muestra completo solo si el actor tiene el permiso
E (Ejecutar) sobre el recurso Usuarios; en caso contrario se enmascara.
"""
from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.permiso_repository import PermisoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError

TIPO_CONSULTA_DETALLE_USUARIO = 18
ID_RECURSO_USUARIOS = 1
ID_ACCION_EJECUTAR = 5


class ConsultarDetalleUsuarioUseCase:
    """Orquesta la consulta del detalle de un usuario con enmascarado condicional de ID."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        permisos_repo: PermisoRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario (proyección de lectura).
            permisos_repo: Repositorio de dominio de permisos (verificación del permiso E).
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.usuarios_repo = usuarios_repo
        self.permisos_repo = permisos_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(self, id_usuario: int, usuario_actual: UsuarioActual) -> dict:
        """Retorna el detalle del usuario con enmascarado según permisos del actor.

        Args:
            id_usuario: ID del usuario a consultar.
            usuario_actual: Administrador que realiza la consulta.

        Returns:
            Diccionario con los datos del usuario. El `numero_identificacion`
            aparece completo si el actor tiene el permiso Ejecutar sobre
            el recurso Usuarios; de lo contrario se enmascara.

        Raises:
            NotFoundError: Si el usuario no existe. HTTP 404.
        """
        detalle = self.usuarios_repo.obtener_detalle(id_usuario)
        if detalle is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message="Consulta fallida: El usuario solicitado no existe o ha sido retirado del sistema.",
            )

        tiene_id_completo = self.permisos_repo.buscar(
            id_rol=usuario_actual.id_rol,
            id_recurso=ID_RECURSO_USUARIOS,
            id_accion=ID_ACCION_EJECUTAR,
        ) is not None

        numero_identificacion = (
            detalle.numero_identificacion
            if tiene_id_completo
            else self._enmascarar(detalle.numero_identificacion)
        )

        try:
            self.eventos_repo.registrar(
                tipo_evento=TIPO_CONSULTA_DETALLE_USUARIO,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "id_usuario_consultado": id_usuario,
                    "tiene_id_completo": tiene_id_completo,
                },
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
