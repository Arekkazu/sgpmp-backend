from typing import Optional

import bcrypt
from sqlalchemy import or_
from sqlalchemy.exc import InternalError
from sqlalchemy.orm import Session, joinedload

from src.identity_access.application.ports.usuarios_ports import UsuariosPort
from src.identity_access.infrastructure.dto.usuario_dto import UsuarioCreateDTO
from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios
from src.identity_access.infrastructure.models.roles_model import Roles
from src.identity_access.infrastructure.models.usuarios_model import Usuarios

from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import ConflictError, PreconditionFailedError

ROL_PRODUCTOR = 2


class UsuariosSQLRepository(UsuariosPort):

    def __init__(self, db: Session):
        self.db = db

    def buscar_por_id(self, id_usuario: int) -> Optional[Usuarios]:
        return (
            self.db.query(Usuarios)
            .filter(Usuarios.id_usuario == id_usuario)
            .first()
        )

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

    def actualizar_usuario(self, usuario: Usuarios, cambios: dict, version_cliente: int) -> Usuarios:
        if usuario.version != version_cliente:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message=(
                    "Conflicto de edición. Los datos del usuario han sido actualizados recientemente "
                    "por otro proceso. Por favor, recargue la página para obtener la información "
                    "más reciente antes de editar."
                ),
            )
        for campo, valor in cambios.items():
            setattr(usuario, campo, valor)
        try:
            self.db.flush()
            self.db.refresh(usuario)
            return usuario
        except Exception as e:
            raise_from_db_error(e, conflict_messages={
                "uq_usuario_correo_electronico": (
                    "Actualización denegada. La dirección ingresada ya se encuentra vinculada "
                    "a otra cuenta. El correo debe ser único."
                ),
            })

    def verificar_rol_existe(self, id_rol: int) -> bool:
        return self.db.query(Roles).filter(Roles.id_rol == id_rol).first() is not None

    def listar_paginado(
        self,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
        offset: int,
        limit: int,
    ) -> list[Usuarios]:
        query = self._query_con_filtros(nombre, correo, id_estado, id_rol)
        return query.offset(offset).limit(limit).all()

    def contar(
        self,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
    ) -> int:
        return self._query_con_filtros(nombre, correo, id_estado, id_rol).count()

    def _query_con_filtros(self, nombre, correo, id_estado, id_rol):
        query = (
            self.db.query(Usuarios)
            .join(CuentasUsuarios, CuentasUsuarios.id_usuario == Usuarios.id_usuario)
            .options(joinedload(Usuarios.cuentas_usuarios))
        )
        if nombre:
            query = query.filter(
                or_(
                    Usuarios.nombre.ilike(f"%{nombre}%"),
                    Usuarios.apellidos.ilike(f"%{nombre}%"),
                )
            )
        if correo:
            query = query.filter(Usuarios.correo_electronico.ilike(f"%{correo}%"))
        if id_estado is not None:
            query = query.filter(CuentasUsuarios.id_estado_cuenta == id_estado)
        if id_rol is not None:
            query = query.filter(Usuarios.id_rol == id_rol)
        return query

    def cambiar_contrasena(self, usuario: Usuarios, nuevo_hash: str) -> None:
        usuario.contrasena_cifrada = nuevo_hash
        try:
            self.db.flush()
        except InternalError as e:
            self.db.rollback()
            if "CONSTRAINT_VIOLATION" in str(e.orig):
                raise ConflictError(
                    code="CONTRASENA_REUTILIZADA",
                    message=(
                        "Seguridad de credenciales: No se permite reutilizar la contraseña actual. "
                        "Por favor, defina una clave completamente nueva."
                    ),
                )
            raise
        except Exception as e:
            raise_from_db_error(e, conflict_messages={})
