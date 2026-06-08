"""Router FastAPI para el módulo de roles y permisos (`/roles`).

Expone CRUD de roles, catálogos de recursos y acciones, y endpoints de
asignación/retiro de permisos sobre un rol específico.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, status

from src.identity_access.application.use_cases.permisos.asignar_permiso_use_case import AsignarPermisoUseCase
from src.identity_access.application.use_cases.permisos.retirar_permiso_use_case import RetirarPermisoUseCase
from src.identity_access.application.use_cases.roles.crear_rol_use_case import CrearRolUseCase
from src.identity_access.application.use_cases.roles.editar_rol_use_case import EditarRolUseCase
from src.identity_access.application.use_cases.roles.eliminar_rol_use_case import EliminarRolUseCase
from src.identity_access.application.use_cases.roles.listar_roles_use_case import ListarRolesUseCase
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.dto.roles_dto import AsignarPermisoDTO, CrearRolDTO, EditarRolDTO
from src.identity_access.infrastructure.models.acciones_model import Acciones
from src.identity_access.infrastructure.models.recursos_model import Recursos
from src.identity_access.infrastructure.repositories.permisos_repository import PermisosSQLRepository
from src.identity_access.infrastructure.repositories.rol_repository import SqlAlchemyRolRepository
from src.identity_access.infrastructure.repositories.roles_repository import RolesSQLRepository
from src.identity_access.infrastructure.repositories.sesiones_repository import SesionesSQLRepository
from src.identity_access.infrastructure.schema.roles_schema import (
    AccionResponse,
    PermisoResponse,
    RecursoResponse,
    RolConPermisosResponse,
    RolResponse,
)
from src.shared.database import get_db
from src.shared.errors import NotFoundError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse, MessageResponse

router = APIRouter(prefix="/roles", tags=["Roles y Permisos"])


# ── Catálogos (antes de /{id_rol} para evitar conflictos de ruta) ──────────────

@router.get(
    "/catalogo/recursos",
    response_model=list[RecursoResponse],
    dependencies=[Depends(require_permission(3, 2))],
)
def listar_recursos(db: Session = Depends(get_db)):
    return db.scalars(select(Recursos).order_by(Recursos.id_recurso)).all()


@router.get(
    "/catalogo/acciones",
    response_model=list[AccionResponse],
    dependencies=[Depends(require_permission(3, 2))],
)
def listar_acciones(db: Session = Depends(get_db)):
    return db.scalars(select(Acciones).order_by(Acciones.id_accion)).all()


# ── Roles CRUD ─────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=list[RolConPermisosResponse],
    dependencies=[Depends(require_permission(2, 2))],
)
def listar_roles(db: Session = Depends(get_db)):
    use_case = ListarRolesUseCase(
        roles_repo=SqlAlchemyRolRepository(db),
        permisos_port=PermisosSQLRepository(db),
    )
    resultado = use_case.execute()
    return [
        RolConPermisosResponse(
            id_rol=item["rol"].id_rol,
            nombre_rol=item["rol"].nombre_rol,
            descripcion=item["rol"].descripcion,
            es_protegido=item["rol"].es_protegido,
            permisos=[PermisoResponse.model_validate(p) for p in item["permisos"]],
        )
        for item in resultado
    ]


@router.post(
    "/",
    response_model=RolResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(2, 1))],
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def crear_rol(
    dto: CrearRolDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = CrearRolUseCase(
        roles_repo=SqlAlchemyRolRepository(db),
        sesiones_port=SesionesSQLRepository(db),
        db=db,
    )
    id_rol = use_case.execute(dto, usuario_actual)
    rol = SqlAlchemyRolRepository(db).obtener_por_id(id_rol)
    return RolResponse.model_validate(rol)


@router.get(
    "/{id_rol}",
    response_model=RolConPermisosResponse,
    dependencies=[Depends(require_permission(2, 2))],
    responses={404: {"model": ErrorResponse}},
)
def detalle_rol(id_rol: int, db: Session = Depends(get_db)):
    roles_repo = SqlAlchemyRolRepository(db)
    rol = roles_repo.obtener_por_id(id_rol)
    if rol is None:
        raise NotFoundError(
            code="ROL_NO_ENCONTRADO",
            message=f"Error: El rol solicitado con ID {id_rol} no existe.",
        )
    permisos = PermisosSQLRepository(db).listar_por_rol(id_rol)
    return RolConPermisosResponse(
        id_rol=rol.id_rol,
        nombre_rol=rol.nombre_rol,
        descripcion=rol.descripcion,
        es_protegido=rol.es_protegido,
        permisos=[PermisoResponse.model_validate(p) for p in permisos],
    )


@router.put(
    "/{id_rol}",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission(2, 3))],
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def editar_rol(
    id_rol: int,
    dto: EditarRolDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = EditarRolUseCase(
        roles_repo=SqlAlchemyRolRepository(db),
        sesiones_port=SesionesSQLRepository(db),
        db=db,
    )
    use_case.execute(id_rol, dto, usuario_actual)
    return {"message": f"Rol {id_rol} actualizado exitosamente."}


@router.delete(
    "/{id_rol}",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission(2, 4))],
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def eliminar_rol(
    id_rol: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = EliminarRolUseCase(
        roles_repo=SqlAlchemyRolRepository(db),
        sesiones_port=SesionesSQLRepository(db),
        db=db,
    )
    use_case.execute(id_rol, usuario_actual)
    return {"message": f"Rol {id_rol} eliminado exitosamente."}


# ── Permisos de un rol ─────────────────────────────────────────────────────────

@router.get(
    "/{id_rol}/permisos",
    response_model=list[PermisoResponse],
    dependencies=[Depends(require_permission(3, 2))],
    responses={404: {"model": ErrorResponse}},
)
def listar_permisos_rol(id_rol: int, db: Session = Depends(get_db)):
    roles_repo = SqlAlchemyRolRepository(db)
    if roles_repo.obtener_por_id(id_rol) is None:
        raise NotFoundError(
            code="ROL_NO_ENCONTRADO",
            message=f"Error: El rol solicitado con ID {id_rol} no existe.",
        )
    permisos = PermisosSQLRepository(db).listar_por_rol(id_rol)
    return [PermisoResponse.model_validate(p) for p in permisos]


@router.post(
    "/{id_rol}/permisos",
    response_model=PermisoResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(3, 1))],
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def asignar_permiso(
    id_rol: int,
    dto: AsignarPermisoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = AsignarPermisoUseCase(
        roles_port=RolesSQLRepository(db),
        permisos_port=PermisosSQLRepository(db),
        sesiones_port=SesionesSQLRepository(db),
        db=db,
    )
    permiso = use_case.execute(id_rol, dto, usuario_actual)
    return PermisoResponse.model_validate(permiso)


@router.delete(
    "/{id_rol}/permisos/{id_permiso}",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission(3, 4))],
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def retirar_permiso(
    id_rol: int,
    id_permiso: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = RetirarPermisoUseCase(
        permisos_port=PermisosSQLRepository(db),
        sesiones_port=SesionesSQLRepository(db),
        db=db,
    )
    use_case.execute(id_rol, id_permiso, usuario_actual)
    return {"message": f"Permiso {id_permiso} retirado exitosamente del rol {id_rol}."}
