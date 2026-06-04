from typing import Optional

import bcrypt
from sqlalchemy.orm import Session

from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dto.usuario_dto import UsuarioCreateDTO
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.db_error_translator import raise_from_db_error

ROL_PRODUCTOR = 2


class UsuariosSQLRepository(UsuariosPort):

    def __init__(self, db: Session):
        self.db = db

    def buscar_por_correo(self, correo_electronico: str) -> Optional[Usuarios]:
        return (
            self.db.query(Usuarios)
            .filter(Usuarios.correo_electronico == correo_electronico)
            .first()
        )

    def create_usuario(self, dto: UsuarioCreateDTO) -> Usuarios:
        usuario = Usuarios(
            correo_electronico=dto.correo_electronico,
            telefono=dto.telefono,
            tipo_identificacion=dto.tipo_identificacion,
            numero_identificacion=dto.numero_identificacion,
            nombre=dto.nombre,
            apellidos=dto.apellidos,
            fecha_nacimiento=dto.fecha_nacimiento,
            genero=dto.genero,
            contrasena_cifrada=bcrypt.hashpw(dto.contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            direccion=dto.direccion,
            id_rol=ROL_PRODUCTOR,
        )
        try:
            self.db.add(usuario)
            self.db.flush()
            self.db.refresh(usuario)
            return usuario
        except Exception as e:
            raise_from_db_error(e, conflict_messages={
                "uq_usuario_correo_electronico": "El correo electrónico ya está registrado",
                "uq_usuario_numero_identificacion": "El número de identificación ya está registrado",
            })
