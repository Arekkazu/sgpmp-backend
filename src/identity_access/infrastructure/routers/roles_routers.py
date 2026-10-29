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
from src.identity_access.infrastructure.repositories.permiso_repository import SqlAlchemyPermisoRepository
from src.identity_access.infrastructure.repositories.rol_repository import SqlAlchemyRolRepository
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
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
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Catálogo de recursos RBAC (RF-04)",
    response_model=list[RecursoResponse],
    dependencies=[Depends(require_permission(3, 2))],
)
def listar_recursos(db: Session = Depends(get_db)):
    """Lista los recursos de `modulo1.recursos` sobre los que se pueden asignar permisos.

    **Acceso:** permiso `permisos` · Leer (3·R).
    """
    return db.scalars(select(Recursos).order_by(Recursos.id_recurso)).all()


@router.get(
    "/catalogo/acciones",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Catálogo de acciones RBAC (RF-04)",
    response_model=list[AccionResponse],
    dependencies=[Depends(require_permission(3, 2))],
)
def listar_acciones(db: Session = Depends(get_db)):
    """Lista las acciones de `modulo1.acciones` (C, R, U, D, E).

    **Acceso:** permiso `permisos` · Leer (3·R).
    """
    return db.scalars(select(Acciones).order_by(Acciones.id_accion)).all()


# ── Roles CRUD ─────────────────────────────────────────────────────────────────

@router.get(
    "/",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Listar roles con sus permisos (RF-03)",
    response_model=list[RolConPermisosResponse],
    dependencies=[Depends(require_permission(2, 2))],
)
def listar_roles(db: Session = Depends(get_db)):
    """Devuelve todos los roles del sistema con los permisos asignados a cada uno.

    **Acceso:** permiso `roles` · Leer (2·R).
    """
    use_case = ListarRolesUseCase(
        roles_repo=SqlAlchemyRolRepository(db),
        permisos_repo=SqlAlchemyPermisoRepository(db),
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
    summary="Crear un rol con permisos iniciales (RF-03)",
    response_model=RolResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(2, 1))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def crear_rol(
    dto: CrearRolDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """Crea un rol y sus permisos iniciales en una sola transacción.

    **Acceso:** permiso `roles` · Crear (2·C).

    Errores: nombre duplicado (409), sin permisos o recurso/acción inexistente (400).
    """
    use_case = CrearRolUseCase(
        roles_repo=SqlAlchemyRolRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    id_rol = use_case.execute(dto, usuario_actual)
    rol = SqlAlchemyRolRepository(db).obtener_por_id(id_rol)
    return RolResponse.model_validate(rol)


@router.get(
    "/{id_rol}",
    summary="Consultar un rol (RF-03)",
    response_model=RolConPermisosResponse,
    dependencies=[Depends(require_permission(2, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def detalle_rol(id_rol: int, db: Session = Depends(get_db)):
    """Devuelve un rol con sus permisos.

    **Acceso:** permiso `roles` · Leer (2·R).
    """
    roles_repo = SqlAlchemyRolRepository(db)
    rol = roles_repo.obtener_por_id(id_rol)
    if rol is None:
        raise NotFoundError(
            code="ROL_NO_ENCONTRADO",
            message=f"Error: El rol solicitado con ID {id_rol} no existe.",
        )
    permisos = SqlAlchemyPermisoRepository(db).listar_por_rol(id_rol)
    return RolConPermisosResponse(
        id_rol=rol.id_rol,
        nombre_rol=rol.nombre_rol,
        descripcion=rol.descripcion,
        es_protegido=rol.es_protegido,
        permisos=[PermisoResponse.model_validate(p) for p in permisos],
    )


@router.put(
    "/{id_rol}",
    summary="Editar nombre o descripción de un rol (RF-03)",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission(2, 3))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
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
    """Actualiza el nombre y/o la descripción de un rol.

    **Acceso:** permiso `roles` · Actualizar (2·U).

    Sin cambios respecto al valor actual responde 400. El rol protegido
    (Administrador) no puede cambiar de nombre (403), pero sí de descripción.
    """
    use_case = EditarRolUseCase(
        roles_repo=SqlAlchemyRolRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    use_case.execute(id_rol, dto, usuario_actual)
    return {"message": f"Rol {id_rol} actualizado exitosamente."}


@router.delete(
    "/{id_rol}",
    summary="Eliminar un rol (RF-03)",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission(2, 4))],
    responses={
        401: {"model": ErrorResponse},
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
    """Elimina un rol del sistema.

    **Acceso:** permiso `roles` · Eliminar (2·D).

    El rol protegido no se puede eliminar (403), ni un rol con usuarios asignados (422).
    """
    use_case = EliminarRolUseCase(
        roles_repo=SqlAlchemyRolRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    use_case.execute(id_rol, usuario_actual)
    return {"message": f"Rol {id_rol} eliminado exitosamente."}


# ── Permisos de un rol ─────────────────────────────────────────────────────────

@router.get(
    "/{id_rol}/permisos",
    summary="Listar permisos de un rol (RF-04)",
    response_model=list[PermisoResponse],
    dependencies=[Depends(require_permission(3, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def listar_permisos_rol(id_rol: int, db: Session = Depends(get_db)):
    """Devuelve los permisos (recurso + acción) asignados a un rol.

    **Acceso:** permiso `permisos` · Leer (3·R).
    """
    roles_repo = SqlAlchemyRolRepository(db)
    if roles_repo.obtener_por_id(id_rol) is None:
        raise NotFoundError(
            code="ROL_NO_ENCONTRADO",
            message=f"Error: El rol solicitado con ID {id_rol} no existe.",
        )
    permisos = SqlAlchemyPermisoRepository(db).listar_por_rol(id_rol)
    return [PermisoResponse.model_validate(p) for p in permisos]


@router.post(
    "/{id_rol}/permisos",
    summary="Asignar un permiso a un rol (RF-04)",
    response_model=PermisoResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(3, 1))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
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
    """Asigna un par recurso + acción a un rol.

    **Acceso:** permiso `permisos` · Crear (3·C).

    Errores: recurso o acción inexistentes, o acción que no aplica al recurso
    (400); permiso repetido (409); permiso reservado al Administrador (422).
    """
    use_case = AsignarPermisoUseCase(
        roles_repo=SqlAlchemyRolRepository(db),
        permisos_repo=SqlAlchemyPermisoRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    permiso = use_case.execute(id_rol, dto, usuario_actual)
    return PermisoResponse.model_validate(permiso)


@router.delete(
    "/{id_rol}/permisos/{id_permiso}",
    summary="Retirar un permiso de un rol (RF-04)",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission(3, 4))],
    responses={
        401: {"model": ErrorResponse},
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
    """Retira un permiso del rol indicado.

    **Acceso:** permiso `permisos` · Eliminar (3·D).

    El permiso debe existir (404) y pertenecer a ese rol (403). La BD impide dejar
    un rol sin permisos o quitar permisos al Administrador (422).
    """
    use_case = RetirarPermisoUseCase(
        permisos_repo=SqlAlchemyPermisoRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    use_case.execute(id_rol, id_permiso, usuario_actual)
    return {"message": f"Permiso {id_permiso} retirado exitosamente del rol {id_rol}."}
