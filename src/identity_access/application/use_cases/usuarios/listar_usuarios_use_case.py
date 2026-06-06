from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado

TIPO_CONSULTA_LISTA_USUARIOS = 17


class ListarUsuariosUseCase:

    def __init__(
        self,
        usuarios_port: UsuariosPort,
        sesiones_port: SesionesPort,
        db: Session,
    ):
        self.usuarios_port = usuarios_port
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(
        self,
        usuario_actual: UsuarioActual,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
        pagina: int,
        tamano: int,
    ) -> dict:
        tamano = min(tamano, 50)
        offset = (pagina - 1) * tamano

        total = self.usuarios_port.contar(nombre, correo, id_estado, id_rol)
        items = self.usuarios_port.listar_paginado(nombre, correo, id_estado, id_rol, offset, tamano)

        try:
            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_CONSULTA_LISTA_USUARIOS,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "filtros": {
                        "nombre": nombre,
                        "correo": correo,
                        "id_estado": id_estado,
                        "id_rol": id_rol,
                    },
                    "total_resultados": total,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "total": total,
            "pagina": pagina,
            "tamano": tamano,
            "items": items,
        }
