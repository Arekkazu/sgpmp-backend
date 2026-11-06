# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-SSO02/RF-101: token de canal desde el registro de clientes y Bearer en usuarios |
"""Router FastAPI para la integración server-to-server con AgroFusion (canal de identidad, RF-SSO02).

Montado bajo un prefijo propio (`/integraciones/agrofusion`) porque es un contrato M2M distinto del
resto de la API. Desde RF-101 v2.0 las credenciales del cliente (`client_id`/`client_secret`) viajan
**solo** en el cuerpo de `POST /token`, se validan contra el registro de clientes externos de M07 y
el resultado es un token de canal (corto, sin sesión). Las operaciones de usuario exigen ese token
(`Authorization: Bearer`, canal `IDENTIDAD_M2M`); `GET /roles` no lleva autenticación porque
AgroFusion lo llama sin ella. `UPDATE_USER` y `GET_TYPE_DOCUMENT` siguen sin implementar.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.agrofusion.cambiar_estado_usuario_agrofusion_use_case import (
    CambiarEstadoUsuarioAgroFusionUseCase,
)
from src.identity_access.application.use_cases.agrofusion.crear_usuario_agrofusion_use_case import (
    CrearUsuarioAgroFusionUseCase,
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
from src.accounting_integration.application.use_cases.canal.verificar_acceso_canal_use_case import AccesoCanal
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.infrastructure.dependencias import requerir_canal
from src.accounting_integration.infrastructure.factoria import M07
from src.shared.database import como_sistema, get_db
from src.shared.rate_limit import registrar_llamada
from src.shared.schemas import ErrorResponse, MessageResponse

router = APIRouter(prefix="/integraciones/agrofusion", tags=["Integración AgroFusion"])

_RESPUESTAS_M2M = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 429: {"model": ErrorResponse}}
_acceso_identidad = requerir_canal("IDENTIDAD_M2M")


def _auditar_m2m(db: Session, tipo_evento: str, acceso: AccesoCanal, endpoint: str, metodo: str) -> None:
    M07(db).auditar_aparte(EventoIntegracion(
        tipo_evento=tipo_evento, tipo_actor="CLIENTE_EXTERNO", id_cliente_externo=acceso.cliente.id_cliente_externo,
        id_usuario=acceso.usuario.id_usuario, endpoint=endpoint, metodo_http=metodo, codigo_http=200, codigo_resultado="OK"))


@router.get(
    "/roles",
    summary="AgroFusion: listar roles (GET_ROLES)",
    response_model=list[AgroFusionRolResumen],
    responses=_RESPUESTAS_M2M,
)
def listar_roles(request: Request, db: Session = Depends(get_db)):
    """`GET_ROLES` — solo id y nombre de cada rol. AgroFusion lo llama sin autenticación, así que se
    limita por IP y se lee como Sistema (sin identidad, la RLS de `modulo1` no devolvería nada)."""
    registrar_llamada(f"m07:roles:{request.client.host if request.client else 'desconocida'}", 30, 60)
    with como_sistema(db):
        roles = SqlAlchemyRolRepository(db).listar()
    return [AgroFusionRolResumen(id_rol=r.id_rol, nombre_rol=r.nombre_rol) for r in roles]


@router.post(
    "/token",
    summary="AgroFusion: emitir token para un usuario (GET_AUTHORIZATION)",
    response_model=AgroFusionTokenResponse,
    responses={
        **_RESPUESTAS_M2M,
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        423: {"model": ErrorResponse},
    },
)
def emitir_token(dto: AgroFusionTokenDTO, request: Request, db: Session = Depends(get_db)):
    """`GET_AUTHORIZATION` — token de canal (RF-SSO02) para el usuario `email`. No crea sesión ni
    cierra la sesión web del usuario (RFC-019 D-19.4)."""
    ip = request.client.host if request.client else None
    token, expira_en = M07(db).emitir_token().execute(dto.client_id, dto.client_secret, dto.email, ip)
    return AgroFusionTokenResponse(access_token=token, expires_in=expira_en)


@router.post(
    "/usuarios",
    summary="AgroFusion: crear usuario activo (CREATE_USER)",
    status_code=201,
    response_model=UsuarioResponse,
    responses={
        **_RESPUESTAS_M2M,
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def crear_usuario(
    dto: AgroFusionCreateUserDTO,
    db: Session = Depends(get_db),
    acceso: AccesoCanal = Depends(_acceso_identidad),
):
    """`CREATE_USER` — alta completa de usuario, activo de inmediato."""

    use_case = CrearUsuarioAgroFusionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        roles_repo=SqlAlchemyRolRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    usuario = use_case.execute(dto)
    _auditar_m2m(db, "USUARIO_CREADO_M2M", acceso, "/integraciones/agrofusion/usuarios", "POST")
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
    summary="AgroFusion: consultar usuario por correo (GET_USER)",
    response_model=AgroFusionUsuarioEstadoResponse,
    responses=_RESPUESTAS_M2M,
)
def obtener_usuario(email: str, db: Session = Depends(get_db), _: AccesoCanal = Depends(_acceso_identidad)):
    """`GET_USER` — existencia + estado + rol actual. Lectura simple, sin use case dedicado."""

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
    summary="AgroFusion: cambiar estado de cuenta (CHANGE_USER_STATUS)",
    response_model=MessageResponse,
    responses={
        **_RESPUESTAS_M2M,
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def cambiar_estado_usuario(
    email: str,
    dto: AgroFusionEstadoDTO,
    db: Session = Depends(get_db),
    acceso: AccesoCanal = Depends(_acceso_identidad),
):
    """`CHANGE_USER_STATUS` — permite a un admin de AgroFusion desactivar remotamente una cuenta."""

    use_case = CambiarEstadoUsuarioAgroFusionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    use_case.execute(email, dto.id_estado_cuenta, dto.motivo)
    _auditar_m2m(db, "ESTADO_USUARIO_CAMBIADO_M2M", acceso, "/integraciones/agrofusion/usuarios/{email}/estado", "PATCH")
    return {"message": "Estado de cuenta actualizado exitosamente."}
