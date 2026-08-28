"""Router FastAPI para el módulo de usuarios (`/usuarios`).

Expone endpoints de registro, activación, perfil, edición, listado administrativo,
gestión de estado de cuenta y registro de tokens FCM.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session
from src.identity_access.infrastructure.dto.fcm_token_dto import FcmTokenDTO

from src.identity_access.application.use_cases.cuentas.gestionar_cuenta_use_case import GestionarCuentaUseCase
from src.identity_access.application.use_cases.perfil.consultar_perfil_use_case import ConsultarPerfilUseCase
from src.identity_access.application.use_cases.perfil.editar_perfil_use_case import EditarPerfilUseCase
from src.identity_access.application.use_cases.registro.activar_cuenta_use_case import ActivarCuentaUseCase
from src.identity_access.application.use_cases.registro.crear_usuario_use_case import CrearUsuarioUseCase
from src.identity_access.application.use_cases.registro.reenviar_token_use_case import ReenviarTokenUseCase
from src.identity_access.application.use_cases.usuarios.consultar_detalle_usuario_use_case import ConsultarDetalleUsuarioUseCase
from src.identity_access.application.use_cases.usuarios.listar_usuarios_use_case import ListarUsuariosUseCase
from src.identity_access.infrastructure.adapters.correo_activacion_background_adapter import (
    CorreoActivacionBackgroundAdapter,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.dto.gestion_cuenta_dto import GestionarCuentaDTO
from src.shared.rbac import require_permission
from src.identity_access.infrastructure.dto.perfil_dto import (EditarPerfilAdminDTO, EditarPerfilDTO)
from src.identity_access.infrastructure.dto.usuario_dto import ReenviarTokenDTO, UsuarioCreateDTO
from src.identity_access.infrastructure.repositories.cuenta_repository import SqlAlchemyCuentaRepository
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.identity_access.infrastructure.repositories.permiso_repository import SqlAlchemyPermisoRepository
from src.identity_access.infrastructure.repositories.rol_repository import SqlAlchemyRolRepository
from src.identity_access.infrastructure.repositories.sesion_repository import SqlAlchemySesionRepository
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.shared.notificacion_service import NotificacionService
from src.identity_access.infrastructure.schema.gestion_schema import (
    UsuarioDetalleResponse,
    UsuarioListadoPaginadoResponse,
    UsuarioListadoResponse,
)
from src.identity_access.infrastructure.schema.user_schema import UsuarioResponse
from src.shared.database import get_db
from src.shared.schemas import ErrorResponse, MessageResponse

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])

def _crear_editar_perfil_use_case(db: Session) -> EditarPerfilUseCase:
    return EditarPerfilUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        sesiones_repo=SqlAlchemySesionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        roles_repo=SqlAlchemyRolRepository(db),
        db=db,
        notificacion_service=NotificacionService(
            port=SqlAlchemyNotificacionRepository(db),
            db=db,
        ),
    )


def _contexto_auditoria(request: Request) -> tuple[str, str]:
    """Obtiene IP y user-agent normalizados por el middleware del request."""
    ip = getattr(request.state, "ip", None)
    if not ip:
        ip = request.client.host if request.client else "unknown"

    user_agent = getattr(request.state, "user_agent", None)
    if not user_agent:
        user_agent = request.headers.get("user-agent", "unknown")

    return ip, user_agent


def _a_usuario_response(usuario) -> UsuarioResponse:
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
    "/admin",
    response_model=UsuarioListadoPaginadoResponse,
    dependencies=[Depends(require_permission(1, 2))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
def listar_usuarios_admin(
    nombre: Optional[str] = Query(None),
    correo: Optional[str] = Query(None),
    id_estado: Optional[int] = Query(None),
    id_rol: Optional[int] = Query(None),
    estado_cuenta: Optional[str] = Query(
        None, description="Nombre del estado de cuenta (ej: Activo, Bloqueado), case-insensitive."
    ),
    actualizado_desde: Optional[datetime] = Query(
        None, description="Solo usuarios modificados (datos o estado de cuenta) desde este instante."
    ),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = ListarUsuariosUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    resultado = use_case.execute(
        usuario_actual=usuario_actual,
        nombre=nombre,
        correo=correo,
        id_estado=id_estado,
        id_rol=id_rol,
        pagina=pagina,
        tamano=tamano,
        estado_cuenta=estado_cuenta,
        actualizado_desde=actualizado_desde,
    )
    items = [
        UsuarioListadoResponse(
            nombre_usuario=f"{u.nombre} {u.apellidos}",
            correo_electronico=u.correo_electronico,
            nombre_rol=u.nombre_rol,
            estado_cuenta=u.estado_cuenta or "",
            ultima_modificacion=u.ultima_modificacion,
        )
        for u in resultado["items"]
    ]
    return UsuarioListadoPaginadoResponse(
        total=resultado["total"],
        pagina=resultado["pagina"],
        tamano=resultado["tamano"],
        mensaje=resultado.get("mensaje"),
        items=items,
    )


@router.post(
    "/",
    response_model=MessageResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def crear_usuario(
    dto: UsuarioCreateDTO,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    ip, user_agent = _contexto_auditoria(request)

    use_case = CrearUsuarioUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        correo_activacion_port=CorreoActivacionBackgroundAdapter(background_tasks),
        db=db,
    )

    use_case.execute(dto, ip, user_agent)

    return {"message": "Registro exitoso, envío de correo en proceso."}


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
    use_case = ReenviarTokenUseCase(
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        db=db,
    )
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

def activar_cuenta(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    ip, user_agent = _contexto_auditoria(request)

    use_case = ActivarCuentaUseCase(
        cuentas_repo=SqlAlchemyCuentaRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
        notificacion_service=NotificacionService(
            port=SqlAlchemyNotificacionRepository(db),
            db=db,
        ),
    )

    use_case.execute(token, ip, user_agent)

    return {
        "message": "Cuenta activada exitosamente. Ya puedes iniciar sesión."
    }


@router.post(
    "/me/fcm-token",
    response_model=MessageResponse,
    status_code=200,
    responses={401: {"model": ErrorResponse}},
)
def registrar_fcm_token(
    dto: FcmTokenDTO,
    request: Request,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    user_agent = request.headers.get("user-agent")
    repo = SqlAlchemyNotificacionRepository(db)
    repo.guardar_fcm_token(usuario_actual.id_usuario, dto.token, user_agent)
    db.commit()
    return {"message": "Token FCM registrado exitosamente."}


@router.get(
    "/me",
    response_model=UsuarioDetalleResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def consultar_perfil(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    use_case = ConsultarPerfilUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    resultado = use_case.execute(usuario_actual)
    return UsuarioDetalleResponse(**resultado)

@router.patch(
    "/me",
    response_model=UsuarioResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def editar_perfil_propio(
    dto: EditarPerfilDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    usuario = _crear_editar_perfil_use_case(db).execute(
        usuario_actual.id_usuario,
        dto,
        usuario_actual,
    )

    return _a_usuario_response(usuario)

@router.patch(
    "/{id_usuario}",
    response_model=UsuarioResponse,
    dependencies=[Depends(require_permission(1, 3))],
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
def editar_perfil_admin(
    id_usuario: int,
    dto: EditarPerfilAdminDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    usuario = _crear_editar_perfil_use_case(db).execute(
        id_usuario,
        dto,
        usuario_actual,
    )

    return _a_usuario_response(usuario)

@router.get(
    "/{id_usuario}/detalle",
    response_model=UsuarioDetalleResponse,
    dependencies=[Depends(require_permission(1, 2))],
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
    use_case = ConsultarDetalleUsuarioUseCase(
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        permisos_repo=SqlAlchemyPermisoRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
        db=db,
    )
    resultado = use_case.execute(id_usuario, usuario_actual)
    return UsuarioDetalleResponse(**resultado)


@router.post(
    "/{id_usuario}/gestionar",
    response_model=MessageResponse,
    dependencies=[Depends(require_permission(4, 3))],
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
    usuarios_repo=SqlAlchemyUsuarioRepository(db),
    cuentas_repo=SqlAlchemyCuentaRepository(db),
    eventos_repo=SqlAlchemyEventoRepository(db),
    sesiones_repo=SqlAlchemySesionRepository(db),
    roles_repo=SqlAlchemyRolRepository(db),
    db=db,
    notificacion_service=NotificacionService(
        port=SqlAlchemyNotificacionRepository(db),
        db=db,
    ),
)
    use_case.execute(id_usuario, dto, usuario_actual)
    return {"message": f"Estado de cuenta actualizado exitosamente. Acción '{dto.accion_cuenta.value}' aplicada."}
