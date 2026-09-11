"""Router FastAPI para la integración server-to-server con AgroFusion (Mecanismo B).

Montado bajo un prefijo propio (`/integraciones/agrofusion`) para dejar claro
que es un contrato M2M distinto del resto de la API: ningún endpoint aquí usa
`require_permission` (quien llama no es un `Usuario` de sgpmp con `id_rol`,
sino el Hub de AgroFusion autenticado con `client_id`/`client_secret` — ver
`verify_agrofusion_client`). Implementa 5 de las 7 operaciones que AgroFusion
puede invocar contra un proyecto externo (`GET_ROLES`, `GET_AUTHORIZATION`,
`CREATE_USER`, `GET_USER`, `CHANGE_USER_STATUS`); `ACTIVATE_ACCOUNT`,
`UPDATE_USER` y `GET_TYPE_DOCUMENT` quedan fuera de esta primera iteración
(ver anotaciones/modulo_1/plan_sso_agrofusion.md).
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.agrofusion.cambiar_estado_usuario_agrofusion_use_case import (
    CambiarEstadoUsuarioAgroFusionUseCase,
)
from src.identity_access.application.use_cases.agrofusion.crear_usuario_agrofusion_use_case import (
    CrearUsuarioAgroFusionUseCase,
)
from src.identity_access.application.use_cases.agrofusion.emitir_token_agrofusion_use_case import (
    EmitirTokenAgroFusionUseCase,
)
from src.identity_access.domain.value_objects.email import Email
from src.identity_access.infrastructure.dto.agrofusion_dto import (
    AgroFusionCreateUserDTO,
    AgroFusionEstadoDTO,
    AgroFusionTokenDTO,
)
from src.identity_access.infrastructure.repositories.cuenta_repository import SqlAlchemyCuentaRepository
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.rol_repository import SqlAlchemyRolRepository
from src.identity_access.infrastructure.repositories.sesion_repository import SqlAlchemySesionRepository
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.identity_access.infrastructure.schema.agrofusion_schema import (
    AgroFusionRolResumen,
    AgroFusionTokenResponse,
    AgroFusionUsuarioEstadoResponse,
)
from src.identity_access.infrastructure.schema.user_schema import UsuarioResponse
from src.shared.agrofusion_auth import verify_agrofusion_client
from src.shared.database import get_db
from src.shared.schemas import ErrorResponse, MessageResponse

router = APIRouter(prefix="/integraciones/agrofusion", tags=["Integración AgroFusion"])

_RESPUESTAS_M2M = {401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}


@router.get(
    "/roles",
    response_model=list[AgroFusionRolResumen],
    responses=_RESPUESTAS_M2M,
)
def listar_roles(
    client_id: str = Query(...),
    client_secret: str = Query(...),
    db: Session = Depends(get_db),
):
    """`GET_ROLES` — lectura simple de `modulo1.roles`, sin use case dedicado."""
    verify_agrofusion_client(client_id, client_secret)
    roles = SqlAlchemyRolRepository(db).listar()
    return [AgroFusionRolResumen(id_rol=r.id_rol, nombre_rol=r.nombre_rol) for r in roles]


@router.post(
    "/token",
    response_model=AgroFusionTokenResponse,
    responses={
        **_RESPUESTAS_M2M,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        423: {"model": ErrorResponse},
    },
)
def emitir_token(dto: AgroFusionTokenDTO, request: Request, db: Session = Depends(get_db)):
    """`GET_AUTHORIZATION` — emite un JWT sgpmp normal, sin contraseña."""
    verify_agrofusion_client(dto.client_id, dto.client_secret)

    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "AgroFusion-Hub")

    use_case = EmitirTokenAgroFusionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    jwt_str, expira_en = use_case.execute(dto.email, ip, user_agent)
    return AgroFusionTokenResponse(access_token=jwt_str, expires_in=expira_en)


@router.post(
    "/usuarios",
    status_code=201,
    response_model=UsuarioResponse,
    responses={
        **_RESPUESTAS_M2M,
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def crear_usuario(dto: AgroFusionCreateUserDTO, db: Session = Depends(get_db)):
    """`CREATE_USER` — alta completa de usuario, activo de inmediato."""
    verify_agrofusion_client(dto.client_id, dto.client_secret)

    use_case = CrearUsuarioAgroFusionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        roles_repo=SqlAlchemyRolRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    usuario = use_case.execute(dto)
    return UsuarioResponse(
        id_usuario=usuario.id_usuario,
        nombre=usuario.nombre,
        apellidos=usuario.apellidos,
        correo_electronico=str(usuario.correo),
        tipo_identificacion=usuario.tipo_identificacion,
        numero_identificacion=usuario.numero_identificacion,
        genero=usuario.genero,
        id_rol=usuario.id_rol,
        fecha_registro=usuario.fecha_registro,
        telefono=usuario.telefono,
        direccion=usuario.direccion,
        version=usuario.version,
    )


@router.get(
    "/usuarios/{email}",
    response_model=AgroFusionUsuarioEstadoResponse,
    responses=_RESPUESTAS_M2M,
)
def obtener_usuario(
    email: str,
    client_id: str = Query(...),
    client_secret: str = Query(...),
    db: Session = Depends(get_db),
):
    """`GET_USER` — existencia + estado + rol actual. Lectura simple, sin use case dedicado."""
    verify_agrofusion_client(client_id, client_secret)

    usuarios_repo = SqlAlchemyUsuarioRepository(db)
    usuario = usuarios_repo.obtener_por_correo(Email(email))
    if usuario is None:
        return AgroFusionUsuarioEstadoResponse(existe=False)

    cuenta = SqlAlchemyCuentaRepository(db).obtener_por_usuario(usuario.id_usuario)
    return AgroFusionUsuarioEstadoResponse(
        existe=True,
        id_usuario=usuario.id_usuario,
        id_estado_cuenta=cuenta.id_estado_cuenta if cuenta else None,
        id_rol=usuario.id_rol,
    )


@router.patch(
    "/usuarios/{email}/estado",
    response_model=MessageResponse,
    responses={
        **_RESPUESTAS_M2M,
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def cambiar_estado_usuario(email: str, dto: AgroFusionEstadoDTO, db: Session = Depends(get_db)):
    """`CHANGE_USER_STATUS` — permite a un admin de AgroFusion desactivar remotamente una cuenta."""
    verify_agrofusion_client(dto.client_id, dto.client_secret)

    use_case = CambiarEstadoUsuarioAgroFusionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    use_case.execute(email, dto.id_estado_cuenta, dto.motivo)
    return {"message": "Estado de cuenta actualizado exitosamente."}
