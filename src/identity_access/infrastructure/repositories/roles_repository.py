"""Implementación SQLAlchemy del port de roles.

La creación de roles usa un stored procedure (`sp_crear_rol`) para garantizar
atomicidad entre la inserción del rol y sus permisos iniciales. Los errores
del SP se identifican por pgcode o por mensaje para traducirlos a errores de dominio.
"""
import json
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from src.identity_access.application.ports.roles_ports import RolesPort
from src.identity_access.infrastructure.models.roles_model import Roles
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.errors import BusinessRuleError, ConflictError, ValidationError

_ERRCODE_PROTEGIDO = "P0004"
_ERRCODE_EN_USO = "P0005"


class RolesSQLRepository(RolesPort):
    """Repositorio SQLAlchemy para la tabla `roles` y sus permisos asociados."""

    def __init__(self, db: Session):
        self.db = db

    def listar(self) -> list[Roles]:
        return self.db.query(Roles).order_by(Roles.id_rol).all()

    def buscar_por_id(self, id_rol: int) -> Optional[Roles]:
        return self.db.query(Roles).filter(Roles.id_rol == id_rol).first()

    def contar_usuarios_por_rol(self, id_rol: int) -> int:
        return self.db.query(Usuarios).filter(Usuarios.id_rol == id_rol).count()

    def crear_con_sp(
        self,
        nombre_rol: str,
        descripcion: Optional[str],
        permisos_json: list[dict],
    ) -> int:
        try:
            self.db.execute(
                text("CALL modulo1.sp_crear_rol(:nombre, :desc, CAST(:permisos AS jsonb))"),
                {
                    "nombre": nombre_rol,
                    "desc": descripcion,
                    "permisos": json.dumps(permisos_json),
                },
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

    def editar(
        self,
        rol: Roles,
        nombre_rol: Optional[str],
        descripcion: Optional[str],
    ) -> None:
        if nombre_rol is not None:
            rol.nombre_rol = nombre_rol
        if descripcion is not None:
            rol.descripcion = descripcion
        try:
            self.db.flush()
        except ProgrammingError as e:
            self.db.rollback()
            if getattr(e.orig, "pgcode", "") == _ERRCODE_PROTEGIDO:
                raise BusinessRuleError(
                    code="ROL_PROTEGIDO",
                    message=(
                        "Acción denegada: El rol 'Administrador' es un objeto protegido por el sistema. "
                        "No se permite su eliminación ni el cambio de su identificador base."
                    ),
                )
            raise
        except IntegrityError as e:
            self.db.rollback()
            if "uq_nombre" in str(e.orig):
                raise ConflictError(
                    code="ROL_DUPLICADO",
                    message=(
                        f"Conflicto de identidad: El nombre de rol '{nombre_rol}' ya se encuentra "
                        "registrado. Por favor, utilice una denominación única y descriptiva."
                    ),
                    field="nombre_rol",
                )
            raise

    def eliminar(self, rol: Roles) -> None:
        self.db.delete(rol)
        try:
            self.db.flush()
        except ProgrammingError as e:
            self.db.rollback()
            pgcode = getattr(e.orig, "pgcode", "")
            msg = str(e.orig)
            if pgcode == _ERRCODE_PROTEGIDO or "PROTECTED_ROLE" in msg:
                raise BusinessRuleError(
                    code="ROL_PROTEGIDO",
                    message=(
                        "Acción denegada: El rol 'Administrador' es un objeto protegido por el sistema. "
                        "No se permite su eliminación ni el cambio de su identificador base."
                    ),
                )
            if pgcode == _ERRCODE_EN_USO or "ROLE_IN_USE" in msg:
                raise BusinessRuleError(
                    code="ROL_EN_USO",
                    message=(
                        "No se puede eliminar el rol: existen usuarios vinculados. "
                        "Para proceder, debe reasignar estos usuarios a un rol diferente."
                    ),
                )
            raise
