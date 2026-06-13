"""Implementación SQLAlchemy del puerto de dominio :class:`RolRepository`.

Mapea entre la tabla ``roles`` y la entidad :class:`Rol`. Conserva el stored
procedure ``sp_crear_rol`` para el alta atómica de rol + permisos y la
traducción de los pgcodes P0004 (rol protegido) y P0005 (rol en uso) a errores
de dominio.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from src.identity_access.domain.entities.rol import Rol
from src.identity_access.domain.repositories.rol_repository import RolRepository
from src.identity_access.infrastructure.models.roles_model import Roles
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.errors import BusinessRuleError, ConflictError, ValidationError

_ERRCODE_PROTEGIDO = "P0004"
_ERRCODE_EN_USO = "P0005"

_MSG_PROTEGIDO = (
    "Acción denegada: El rol 'Administrador' es un objeto protegido por el sistema. "
    "No se permite su eliminación ni el cambio de su identificador base."
)


class SqlAlchemyRolRepository(RolRepository):
    """Adaptador SQLAlchemy para la tabla ``roles``."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _a_entidad(orm: Roles) -> Rol:
        """Convierte una fila ORM ``Roles`` en la entidad :class:`Rol`."""
        return Rol(
            id_rol=orm.id_rol,
            nombre_rol=orm.nombre_rol,
            es_protegido=orm.es_protegido,
            descripcion=orm.descripcion,
        )

    def listar(self) -> list[Rol]:
        filas = self.db.query(Roles).order_by(Roles.id_rol).all()
        return [self._a_entidad(r) for r in filas]

    def obtener_por_id(self, id_rol: int) -> Optional[Rol]:
        orm = self.db.query(Roles).filter(Roles.id_rol == id_rol).first()
        return self._a_entidad(orm) if orm else None

    def contar_usuarios(self, id_rol: int) -> int:
        return self.db.query(Usuarios).filter(Usuarios.id_rol == id_rol).count()

    def crear_con_sp(self, nombre_rol: str, descripcion: Optional[str], permisos: list[dict]) -> int:
        try:
            self.db.execute(
                text("CALL modulo1.sp_crear_rol(:nombre, :desc, CAST(:permisos AS jsonb))"),
                {"nombre": nombre_rol, "desc": descripcion, "permisos": json.dumps(permisos)},
            )
            self.db.flush()
        except ProgrammingError as e:
            self.db.rollback()
            msg = str(e.orig)
            if "Conflicto de identidad" in msg:
                raise ConflictError(
                    code="ROL_DUPLICADO",
                    message=(
                        f"Conflicto de identidad: El nombre de rol '{nombre_rol}' ya se encuentra "
                        "registrado. Por favor, utilice una denominación única y descriptiva."
                    ),
                    field="nombre_rol",
                )
            if "poseer al menos un permiso" in msg:
                raise ValidationError(
                    code="PERMISO_REQUERIDO",
                    message=(
                        "Operación rechazada: Todo rol debe poseer al menos un permiso asociado "
                        "para ser funcional. Seleccione al menos una capacidad del catálogo."
                    ),
                )
            if "no existe" in msg:
                raise ValidationError(
                    code="RECURSO_INVALIDO",
                    message=f"Datos inconsistentes: {msg}",
                )
            raise

        rol = self.db.query(Roles).filter(Roles.nombre_rol == nombre_rol).first()
        return rol.id_rol

    def guardar(self, rol: Rol) -> Rol:
        # UPDATE: se recupera la fila gestionada por el identity map y se copian
        # los campos editables de la entidad. El trigger de DB eleva P0004 si el
        # rol es protegido; uq_nombre eleva IntegrityError si el nombre se repite.
        orm = self.db.get(Roles, rol.id_rol)
        orm.nombre_rol = rol.nombre_rol
        orm.descripcion = rol.descripcion
        try:
            self.db.flush()
            self.db.refresh(orm)
        except ProgrammingError as e:
            self.db.rollback()
            if getattr(e.orig, "pgcode", "") == _ERRCODE_PROTEGIDO:
                raise BusinessRuleError(code="ROL_PROTEGIDO", message=_MSG_PROTEGIDO)
            raise
        except IntegrityError as e:
            self.db.rollback()
            if "uq_nombre" in str(e.orig):
                raise ConflictError(
                    code="ROL_DUPLICADO",
                    message=(
                        f"Conflicto de identidad: El nombre de rol '{rol.nombre_rol}' ya se encuentra "
                        "registrado. Por favor, utilice una denominación única y descriptiva."
                    ),
                    field="nombre_rol",
                )
            raise
        return self._a_entidad(orm)

    def eliminar(self, rol: Rol) -> None:
        orm = self.db.get(Roles, rol.id_rol)
        self.db.delete(orm)
        try:
            self.db.flush()
        except ProgrammingError as e:
            self.db.rollback()
            pgcode = getattr(e.orig, "pgcode", "")
            msg = str(e.orig)
            if pgcode == _ERRCODE_PROTEGIDO or "PROTECTED_ROLE" in msg:
                raise BusinessRuleError(code="ROL_PROTEGIDO", message=_MSG_PROTEGIDO)
            if pgcode == _ERRCODE_EN_USO or "ROLE_IN_USE" in msg:
                raise BusinessRuleError(
                    code="ROL_EN_USO",
                    message=(
                        "No se puede eliminar el rol: existen usuarios vinculados. "
                        "Para proceder, debe reasignar estos usuarios a un rol diferente."
                    ),
                )
            raise
