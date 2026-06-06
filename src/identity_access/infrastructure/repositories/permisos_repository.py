from typing import Optional

from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from src.identity_access.application.ports.permisos_ports import PermisosPort
from src.identity_access.infrastructure.models.acciones_model import Acciones
from src.identity_access.infrastructure.models.permisos_model import Permisos
from src.identity_access.infrastructure.models.recursos_model import Recursos
from src.shared.errors import BusinessRuleError, ConflictError

_ERRCODE_MIN_PERMISO = "P0006"
_ERRCODE_ADMIN_NO_DELETE = "P0204"
_ERRCODE_ADMIN_MISMATCH = "P0202"


class PermisosSQLRepository(PermisosPort):

    def __init__(self, db: Session):
        self.db = db

    def listar_por_rol(self, id_rol: int) -> list[Permisos]:
        return (
            self.db.query(Permisos)
            .filter(Permisos.id_rol == id_rol)
            .order_by(Permisos.id_recurso, Permisos.id_accion)
            .all()
        )

    def buscar(self, id_rol: int, id_recurso: int, id_accion: int) -> Optional[Permisos]:
        return (
            self.db.query(Permisos)
            .filter(
                Permisos.id_rol == id_rol,
                Permisos.id_recurso == id_recurso,
                Permisos.id_accion == id_accion,
            )
            .first()
        )

    def asignar(self, id_rol: int, id_recurso: int, id_accion: int, nombre_rol: str) -> Permisos:
        nombre = f"{nombre_rol}_permiso_{id_recurso}_{id_accion}"
        permiso = Permisos(
            nombre=nombre,
            id_rol=id_rol,
            id_recurso=id_recurso,
            id_accion=id_accion,
            es_activo=True,
        )
        self.db.add(permiso)
        try:
            self.db.flush()
            self.db.refresh(permiso)
            return permiso
        except ProgrammingError as e:
            self.db.rollback()
            pgcode = getattr(e.orig, "pgcode", "")
            msg = str(e.orig)
            if pgcode == _ERRCODE_ADMIN_MISMATCH or "ADMIN_PERM_ROLE_MISMATCH" in msg:
                raise BusinessRuleError(
                    code="PERMISO_SOLO_ADMIN",
                    message=(
                        "HTTP 403: Acción denegada: El rol 'Administrador' es un objeto protegido "
                        "por el sistema. No se permite asignar permisos administrativos a otros roles."
                    ),
                )
            raise
        except IntegrityError as e:
            self.db.rollback()
            if "uq_permiso_unico" in str(e.orig):
                raise ConflictError(
                    code="PERMISO_DUPLICADO",
                    message=(
                        "Conflicto de redundancia: El rol ya cuenta con este permiso sobre el recurso indicado. "
                        "No se admiten registros duplicados."
                    ),
                )
            raise

    def buscar_por_id(self, id_permiso: int) -> Permisos | None:
        return self.db.query(Permisos).filter(Permisos.id_permiso == id_permiso).first()

    def existe_recurso(self, id_recurso: int) -> bool:
        return self.db.query(Recursos).filter(Recursos.id_recurso == id_recurso).first() is not None

    def existe_accion(self, id_accion: int) -> bool:
        return self.db.query(Acciones).filter(Acciones.id_accion == id_accion).first() is not None

    def retirar(self, permiso: Permisos) -> None:
        self.db.delete(permiso)
        try:
            self.db.flush()
        except ProgrammingError as e:
            self.db.rollback()
            pgcode = getattr(e.orig, "pgcode", "")
            msg = str(e.orig)
            if pgcode == _ERRCODE_MIN_PERMISO or "MIN_PERMISSION" in msg:
                raise BusinessRuleError(
                    code="PERMISO_MINIMO",
                    message=(
                        "Error de integridad: No se puede retirar el permiso. "
                        "Todo rol debe mantener al menos una capacidad activa. "
                        "El rol no puede quedar sin permisos asociados."
                    ),
                )
            if pgcode == _ERRCODE_ADMIN_NO_DELETE or "ADMIN_PERM_NO_DELETE" in msg:
                raise BusinessRuleError(
                    code="PERMISO_ADMIN_INMUTABLE",
                    message=(
                        "Acción denegada: El rol 'Administrador' es un objeto protegido por el sistema. "
                        "No se permite la eliminación de sus permisos administrativos."
                    ),
                )
            raise
