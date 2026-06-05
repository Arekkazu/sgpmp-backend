from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.cuentas.gestionar_cuenta_use_case import GestionarCuentaUseCase
from src.identity_access.application.use_cases.perfil.editar_perfil_use_case import EditarPerfilUseCase
from src.identity_access.application.use_cases.registro.activar_cuenta_use_case import ActivarCuentaUseCase
from src.identity_access.application.use_cases.registro.crear_usuario_use_case import CrearUsuarioUseCase
from src.identity_access.application.use_cases.registro.reenviar_token_use_case import ReenviarTokenUseCase
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.dto.gestion_cuenta_dto import GestionarCuentaDTO
from src.identity_access.infrastructure.dto.perfil_dto import EditarPerfilAdminDTO
from src.identity_access.infrastructure.dto.usuario_dto import ReenviarTokenDTO, UsuarioCreateDTO
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.identity_access.infrastructure.repositories.cuentas_repository import CuentasSQLRepository
from src.identity_access.infrastructure.repositories.sesiones_repository import SesionesSQLRepository
from src.identity_access.infrastructure.repositories.usuarios_repository import UsuariosSQLRepository
from src.identity_access.infrastructure.schema.gestion_schema import (
    UsuarioEnmascaradoResponse,
    UsuariosPaginadosResponse,
)
from src.identity_access.infrastructure.schema.user_schema import UsuarioResponse
from src.shared.database import get_db
from src.shared.schemas import ErrorResponse, MessageResponse

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("/", response_model=list[UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.scalars(select(Usuarios)).all()


@router.get(
    "/admin",
    response_model=UsuariosPaginadosResponse,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
def listar_usuarios_admin(
    nombre: Optional[str] = Query(None),
    correo: Optional[str] = Query(None),
    id_estado: Optional[int] = Query(None),
    id_rol: Optional[int] = Query(None),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    from src.shared.errors import AuthorizationError
    if usuario_actual.id_rol != 1:
        raise AuthorizationError(
            code="ACCESO_DENEGADO",
            message="Acceso denegado. Se requieren privilegios administrativos.",
        )
    repo = UsuariosSQLRepository(db)
    offset = (pagina - 1) * tamano
    total = repo.contar(nombre, correo, id_estado, id_rol)
    usuarios = repo.listar_paginado(nombre, correo, id_estado, id_rol, offset, tamano)
    items = [
        UsuarioEnmascaradoResponse(
            **{f: getattr(u, f) for f in [
                "id_usuario", "nombre", "apellidos", "correo_electronico",
                "tipo_identificacion", "numero_identificacion", "genero",
                "id_rol", "fecha_registro", "telefono", "direccion", "version",
            ]},
            id_estado_cuenta=u.cuentas_usuarios.id_estado_cuenta if u.cuentas_usuarios else None,
        )
        for u in usuarios
    ]
    return UsuariosPaginadosResponse(total=total, pagina=pagina, tamano=tamano, items=items)


@router.post(
    "/",
    response_model=MessageResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def crear_usuario(dto: UsuarioCreateDTO, db: Session = Depends(get_db)):
    use_case = CrearUsuarioUseCase(
        usuarios_port=UsuariosSQLRepository(db),
        cuentas_port=CuentasSQLRepository(db),
        db=db,
    )
    use_case.execute(dto)
    return {"message": "Registro exitoso. Revisa tu correo para activar tu cuenta."}


@router.post(
    "/activar/reenviar",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def reenviar_token(dto: ReenviarTokenDTO, db: Session = Depends(get_db)):
    use_case = ReenviarTokenUseCase(cuentas_port=CuentasSQLRepository(db))
    use_case.execute(dto)
    return {"message": "Token reenviado. Revisa tu correo para activar tu cuenta."}


@router.get(
    "/activar/{token}",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse},
        410: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def activar_cuenta(token: str, db: Session = Depends(get_db)):
    use_case = ActivarCuentaUseCase(cuentas_port=CuentasSQLRepository(db))
    use_case.execute(token)
    return {"message": "Cuenta activada exitosamente. Ya puedes iniciar sesión."}


@router.patch(
    "/{id_usuario}",
    response_model=UsuarioResponse,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def editar_perfil(
    id_usuario: int,
    dto: EditarPerfilAdminDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = EditarPerfilUseCase(
        usuarios_port=UsuariosSQLRepository(db),
        cuentas_port=CuentasSQLRepository(db),
        sesiones_port=SesionesSQLRepository(db),
        db=db,
    )
    usuario = use_case.execute(id_usuario, dto, usuario_actual)
    return usuario


@router.get(
    "/{id_usuario}/detalle",
    response_model=UsuarioEnmascaradoResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def detalle_usuario(
    id_usuario: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    from src.shared.errors import AuthorizationError, NotFoundError
    if usuario_actual.id_rol != 1:
        raise AuthorizationError(
            code="ACCESO_DENEGADO",
            message="Acceso denegado. Se requieren privilegios administrativos.",
        )
    repo = UsuariosSQLRepository(db)
    usuario = repo.buscar_por_id(id_usuario)
    if usuario is None:
        raise NotFoundError(
            code="USUARIO_NO_ENCONTRADO",
            message=f"El usuario con ID {id_usuario} no existe en los registros actuales del sistema.",
        )
    return UsuarioEnmascaradoResponse(
        **{f: getattr(usuario, f) for f in [
            "id_usuario", "nombre", "apellidos", "correo_electronico",
            "tipo_identificacion", "numero_identificacion", "genero",
            "id_rol", "fecha_registro", "telefono", "direccion", "version",
        ]},
        id_estado_cuenta=usuario.cuentas_usuarios.id_estado_cuenta if usuario.cuentas_usuarios else None,
    )


@router.post(
    "/{id_usuario}/gestionar",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def gestionar_cuenta(
    id_usuario: int,
    dto: GestionarCuentaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = GestionarCuentaUseCase(
        usuarios_port=UsuariosSQLRepository(db),
        cuentas_port=CuentasSQLRepository(db),
        sesiones_port=SesionesSQLRepository(db),
        db=db,
    )
    use_case.execute(id_usuario, dto, usuario_actual)
    return {"message": f"Estado de cuenta actualizado exitosamente. Acción '{dto.accion_cuenta.value}' aplicada."}