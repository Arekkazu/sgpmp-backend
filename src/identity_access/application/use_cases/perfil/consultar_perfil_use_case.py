"""Caso de uso: consulta del perfil propio del usuario autenticado.

Retorna los datos del usuario con el número de identificación parcialmente
enmascarado (primeros 4 dígitos visibles) y registra el acceso en auditoría.
"""
from sqlalchemy.orm import Session

from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import NotFoundError

TIPO_CONSULTA_PERFIL_PROPIO = 19


class ConsultarPerfilUseCase:
    """Orquesta la consulta del perfil del usuario actualmente autenticado."""

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        sesiones_port: SesionesPort,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            usuarios_port: Recuperación de los datos del usuario.
            sesiones_port: Registro del evento de auditoría.
            db: Sesión SQLAlchemy activa del request.
        """
        self.usuarios_port = usuarios_port
        self.sesiones_port = sesiones_port
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
        usuario = self.usuarios_port.buscar_por_id(usuario_actual.id_usuario)
        if usuario is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message="Error de perfil: No se pudo recuperar la información asociada a su cuenta. El registro no existe o ha sido desactivado.",
            )

        numero_identificacion = self._enmascarar(usuario.numero_identificacion)
        nombre_rol = usuario.roles.nombre_rol
        estado_cuenta = (
            usuario.cuentas_usuarios.estados_cuentas.nombre
            if usuario.cuentas_usuarios
            else None
        )

        try:
            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_CONSULTA_PERFIL_PROPIO,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle={},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "nombre": usuario.nombre,
            "apellidos": usuario.apellidos,
            "correo_electronico": usuario.correo_electronico,
            "tipo_identificacion": usuario.tipo_identificacion,
            "numero_identificacion": numero_identificacion,
            "fecha_nacimiento": usuario.fecha_nacimiento,
            "fecha_registro": usuario.fecha_registro,
            "nombre_rol": nombre_rol,
            "estado_cuenta": estado_cuenta,
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
