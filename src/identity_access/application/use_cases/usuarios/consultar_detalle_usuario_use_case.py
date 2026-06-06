from sqlalchemy.orm import Session

from src.identity_access.application.ports.permisos_ports import PermisosPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import NotFoundError

TIPO_CONSULTA_DETALLE_USUARIO = 18
ID_RECURSO_USUARIOS = 1
ID_ACCION_EJECUTAR = 5


class ConsultarDetalleUsuarioUseCase:

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        permisos_port: PermisosPort,
        sesiones_port: SesionesPort,
        db: Session,
    ):
        self.usuarios_port = usuarios_port
        self.permisos_port = permisos_port
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(self, id_usuario: int, usuario_actual: UsuarioActual) -> dict:
        usuario = self.usuarios_port.buscar_por_id(id_usuario)
        if usuario is None:
            raise NotFoundError(
                code="USUARIO_NO_ENCONTRADO",
                message="Consulta fallida: El usuario solicitado no existe o ha sido retirado del sistema.",
            )

        tiene_id_completo = self.permisos_port.buscar(
            id_rol=usuario_actual.id_rol,
            id_recurso=ID_RECURSO_USUARIOS,
            id_accion=ID_ACCION_EJECUTAR,
        ) is not None

        numero_identificacion = (
            usuario.numero_identificacion
            if tiene_id_completo
            else self._enmascarar(usuario.numero_identificacion)
        )

        nombre_rol = usuario.roles.nombre_rol
        estado_cuenta = (
            usuario.cuentas_usuarios.estados_cuentas.nombre
            if usuario.cuentas_usuarios
            else None
        )

        try:
            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_CONSULTA_DETALLE_USUARIO,
                resultado=EnumEventoResultado.EXITOSO,
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
