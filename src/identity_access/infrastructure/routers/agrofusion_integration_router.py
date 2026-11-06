# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-SSO02/RF-101: token de canal desde el registro de clientes y Bearer en usuarios |
# | 2026-11-06 | Arekkazu | RF-SSO02: contrato real de AgroFusion (404 en GET_USER, tipos de documento, {user_id}) |
"""Router FastAPI para la integración server-to-server con AgroFusion (canal de identidad, RF-SSO02).

Montado bajo un prefijo propio (`/integraciones/agrofusion`) porque es un contrato M2M distinto del
resto de la API. Desde RF-101 v2.0 las credenciales del cliente (`client_id`/`client_secret`) viajan
**solo** en el cuerpo de `POST /token`, se validan contra el registro de clientes externos de M07 y
el resultado es un token de canal (corto, sin sesión). Las operaciones de usuario exigen ese token
(`Authorization: Bearer`, canal `IDENTIDAD_M2M`); `GET /roles` no lleva autenticación porque
AgroFusion lo llama sin ella, igual que `GET_TYPE_DOCUMENT`.

Contrato verificado en `agrofusion-backendauth` (`users_service`, `orchestrator_service`):
- `GET_USER` responde 404 si el usuario no existe: AgroFusion decide crear según que la llamada falle.
- `UPDATE_USER` y `CHANGE_USER_STATUS` llegan con el id de SGPMP en `{user_id}` (lo toma de `GET_USER`).
- `ACTIVATE_ACCOUNT` reemplaza `{activation_token}` con el token que devolvió `CREATE_USER`.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.agrofusion.comun import usuario_por_identificador
from src.identity_access.application.use_cases.agrofusion.actualizar_usuario_agrofusion_use_case import (
    ActualizarUsuarioAgroFusionUseCase,
)
from src.identity_access.application.use_cases.agrofusion.cambiar_estado_usuario_agrofusion_use_case import (
    CambiarEstadoUsuarioAgroFusionUseCase,
)
from src.identity_access.application.use_cases.agrofusion.crear_usuario_agrofusion_use_case import (
    CrearUsuarioAgroFusionUseCase,
)
from src.identity_access.infrastructure.dto.agrofusion_dto import (
    AgroFusionCreateUserDTO,
    AgroFusionEstadoDTO,
    AgroFusionTokenDTO,
    AgroFusionUpdateUserDTO,
    GENERO_A_AGROFUSION,
    TIPOS_DOCUMENTO,
)
from src.identity_access.infrastructure.repositories.cuenta_repository import SqlAlchemyCuentaRepository
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.rol_repository import SqlAlchemyRolRepository
from src.identity_access.infrastructure.repositories.sesion_repository import SqlAlchemySesionRepository
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.identity_access.infrastructure.schema.agrofusion_schema import (
    AgroFusionRolResumen,
    AgroFusionTokenResponse,
    AgroFusionTipoDocumento,
    AgroFusionUsuarioCreadoResponse,
    AgroFusionUsuarioResponse,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.routers.usuarios_routers import _a_usuario_response, _crear_editar_perfil_use_case
from src.identity_access.infrastructure.schema.user_schema import UsuarioResponse
from src.accounting_integration.application.use_cases.canal.verificar_acceso_canal_use_case import AccesoCanal
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.infrastructure.dependencias import requerir_canal
from src.accounting_integration.infrastructure.factoria import M07
from src.shared.database import como_sistema, get_db
from src.shared.errors import AuthorizationError
from src.shared.rate_limit import registrar_llamada
from src.shared.rbac import tiene_permiso
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
    response_model=AgroFusionUsuarioCreadoResponse,
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
    """`CREATE_USER` — alta completa de usuario, activo de inmediato. Devuelve el ``activation_token``
    que AgroFusion usa en `ACTIVATE_ACCOUNT` (respuesta 200 idempotente, RFC-019 D-19.6)."""

    use_case = CrearUsuarioAgroFusionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        roles_repo=SqlAlchemyRolRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    usuario, activation_token = use_case.execute(dto)
    _auditar_m2m(db, "USUARIO_CREADO_M2M", acceso, "/integraciones/agrofusion/usuarios", "POST")
    return AgroFusionUsuarioCreadoResponse(
        activation_token=activation_token,
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
    "/tipos-documento",
    summary="AgroFusion: tipos de documento (GET_TYPE_DOCUMENT)",
    response_model=list[AgroFusionTipoDocumento],
    responses=_RESPUESTAS_M2M,
)
def listar_tipos_documento(request: Request):
    """`GET_TYPE_DOCUMENT` — catálogo fijo de SGPMP; el `id` es el que debe volver en `CREATE_USER`."""
    registrar_llamada(f"m07:tipos-documento:{request.client.host if request.client else 'desconocida'}", 30, 60)
    return [AgroFusionTipoDocumento(id=k, nombre=v) for k, v in TIPOS_DOCUMENTO.items()]


@router.get(
    "/usuarios/{email}",
    summary="AgroFusion: consultar usuario por correo (GET_USER)",
    response_model=AgroFusionUsuarioResponse,
    responses={**_RESPUESTAS_M2M, 404: {"model": ErrorResponse}},
)
def obtener_usuario(email: str, db: Session = Depends(get_db), _: AccesoCanal = Depends(_acceso_identidad)):
    """`GET_USER` — 404 si no existe (AgroFusion lo crea entonces); si existe, sus datos y el id que
    AgroFusion usará en `{user_id}`."""
    usuario = usuario_por_identificador(SqlAlchemyUsuarioRepository(db), email)
    cuenta = SqlAlchemyCuentaRepository(db).obtener_por_usuario(usuario.id_usuario)
    genero = getattr(usuario.genero, "value", usuario.genero)
    return AgroFusionUsuarioResponse(
        id_usuario=usuario.id_usuario, nombre=usuario.nombre, apellidos=usuario.apellidos,
        correo_electronico=str(usuario.correo), roles=[usuario.id_rol], tipo_identificacion=usuario.tipo_identificacion,
        numero_identificacion=usuario.numero_identificacion, fecha_nacimiento=usuario.fecha_nacimiento,
        genero=genero, genero_id=GENERO_A_AGROFUSION.get(genero),
        id_estado_cuenta=cuenta.id_estado_cuenta if cuenta else None,
    )


@router.patch(
    "/usuarios/{usuario}/estado",
    summary="AgroFusion: cambiar estado de cuenta (CHANGE_USER_STATUS)",
    response_model=MessageResponse,
    responses={
        **_RESPUESTAS_M2M,
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def cambiar_estado_usuario(
    usuario: str,
    dto: AgroFusionEstadoDTO,
    db: Session = Depends(get_db),
    acceso: AccesoCanal = Depends(_acceso_identidad),
):
    """`CHANGE_USER_STATUS` — `usuario` es el id de SGPMP (`{user_id}` en AgroFusion) o el correo;
    `nuevo_estado` usa los códigos de AgroFusion (1 activo, 2 inactivo, 3 eliminado). Reenviar el
    mismo estado no es un error."""

    use_case = CambiarEstadoUsuarioAgroFusionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    use_case.execute(usuario, dto.nuevo_estado, dto.motivo)
    _auditar_m2m(db, "ESTADO_USUARIO_CAMBIADO_M2M", acceso, "/integraciones/agrofusion/usuarios/{usuario}/estado", "PATCH")
    return {"message": "Estado de cuenta actualizado exitosamente."}


@router.put(
    "/usuarios/{usuario}",
    summary="AgroFusion: actualizar usuario (UPDATE_USER)",
    response_model=UsuarioResponse,
    responses={**_RESPUESTAS_M2M, 400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def actualizar_usuario(
    usuario: str,
    dto: AgroFusionUpdateUserDTO,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    acceso: AccesoCanal = Depends(_acceso_identidad),
):
    """`UPDATE_USER` — nombre, apellidos, teléfono, dirección y rol. Exige al usuario del token el mismo
    permiso que la edición administrativa web (`usuarios` · Actualizar); el correo no cambia por aquí.
    `usuario` es el id de SGPMP (`{user_id}` en AgroFusion) o el correo."""
    if not tiene_permiso(db, acceso.usuario.id_rol, 1, 3):
        raise AuthorizationError(code="ACCESO_DENEGADO",
                                 message="El usuario del SGPMP con el que actúa AgroFusion no puede editar usuarios.")
    usuario_actual = UsuarioActual(id_usuario=acceso.usuario.id_usuario, id_token=0, id_rol=acceso.usuario.id_rol,
                                   id_estado_cuenta=2)
    use_case = ActualizarUsuarioAgroFusionUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        roles_repo=SqlAlchemyRolRepository(db),
        editar_perfil=_crear_editar_perfil_use_case(db, background_tasks),
    )
    actualizado = use_case.execute(usuario, dto, usuario_actual)
    _auditar_m2m(db, "USUARIO_ACTUALIZADO_M2M", acceso, "/integraciones/agrofusion/usuarios/{usuario}", "PUT")
    return _a_usuario_response(actualizado)
