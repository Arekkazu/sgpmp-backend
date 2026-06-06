from sqlalchemy.orm import Session

from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import NotFoundError

TIPO_CONSULTA_PERFIL_PROPIO = 19


class ConsultarPerfilUseCase:

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        sesiones_port: SesionesPort,
        db: Session,
    ):
        self.usuarios_port = usuarios_port
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(self, usuario_actual: UsuarioActual) -> dict:
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
        if len(numero) <= 4:
            return "*" * len(numero)
        return numero[:4] + "*" * (len(numero) - 4)
