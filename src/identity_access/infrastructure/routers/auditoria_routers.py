"""Router FastAPI para el módulo de auditoría (`/auditoria`).

Expone la consulta paginada del log de eventos con filtros por usuario,
tipo, categoría y rango de fechas. Solo accesible por administradores.

`GET /auditoria/archivado/` consulta el archivo histórico de RF-10 (eventos con
más de 12 meses copiados a `modulo1.eventos_archivados`) con los mismos filtros,
la misma paginación y el mismo permiso que el log activo.

Los métodos de escritura están declarados a propósito para responder 405 con el
mensaje de inmutabilidad que exige el RF, en vez del cuerpo genérico de FastAPI.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.auditoria.consultar_auditoria_use_case import (
    TIPO_CONSULTA_AUDITORIA,
    ConsultarAuditoriaUseCase,
)
from src.identity_access.application.use_cases.auditoria.exportar_auditoria_use_case import (
    ExportarAuditoriaUseCase,
)
from src.identity_access.domain.value_objects.evento_categoria import EventoCategoria
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.models.permisos_model import Permisos
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.identity_access.infrastructure.schema.gestion_schema import AuditoriaItemResponse, AuditoriaPaginadaResponse
from src.shared.database import get_db
from src.shared.errors import AuthorizationError, MethodNotAllowedError
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/auditoria", tags=["Auditoría"])

ID_RECURSO_AUDITORIA = 6
ID_ACCION_LEER = 2

MENSAJE_INMUTABLE = (
    "Operación no permitida: Los registros de auditoría son inmutables por "
    "diseño y no pueden ser modificados ni eliminados bajo ninguna circunstancia."
)


def verificar_acceso_auditoria(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> UsuarioActual:
    """Autoriza la consulta de auditoría y audita el intento cuando la deniega.

    Equivale a `require_permission(6, 2)` —la decisión sigue viviendo en
    `modulo1.permisos`, no en un `id_rol` quemado— pero el flujo alterno del RF
    exige además que el acceso denegado quede registrado en la propia auditoría,
    y una dependencia genérica de RBAC no puede hacerlo.
    """
    permiso = (
        db.query(Permisos)
        .filter(
            Permisos.id_rol == usuario_actual.id_rol,
            Permisos.id_recurso == ID_RECURSO_AUDITORIA,
            Permisos.id_accion == ID_ACCION_LEER,
            Permisos.es_activo.is_(True),
        )
        .first()
    )
    if permiso is not None:
        return usuario_actual

    try:
        SqlAlchemyEventoRepository(db).registrar(
            tipo_evento=TIPO_CONSULTA_AUDITORIA,
            exitoso=False,
            id_usuario=usuario_actual.id_usuario,
            detalle={"razon": "ACCESO_DENEGADO", "id_rol": usuario_actual.id_rol},
        )
        db.commit()
    except Exception:
        # El incidente ya se está bloqueando; no poder auditarlo no debe
        # convertir un 403 en un 500 que oculte la denegación.
        db.rollback()

    raise AuthorizationError(
        code="ACCESO_DENEGADO",
        message=(
            "Acceso denegado: No posee privilegios de administrador para consultar "
            "el historial de auditoría. Este incidente ha sido registrado."
        ),
    )


def _consultar(
    response: Response,
    db: Session,
    usuario_actual: UsuarioActual,
    id_usuario: Optional[int],
    tipo_evento: Optional[int],
    categoria: Optional[EventoCategoria],
    fecha_desde: Optional[datetime],
    fecha_hasta: Optional[datetime],
    pagina: int,
    tamano: int,
    archivados: bool,
) -> AuditoriaPaginadaResponse:
    """Ejecuta la consulta y arma el response, común al log activo y al histórico."""
    use_case = ConsultarAuditoriaUseCase(
        eventos_repo=SqlAlchemyEventoRepository(db),
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        db=db,
    )
    resultado = use_case.execute(
        usuario_actual=usuario_actual,
        id_usuario=id_usuario,
        tipo_evento=tipo_evento,
        categoria=categoria,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        tamano=tamano,
        archivados=archivados,
    )

    items = [
        AuditoriaItemResponse(
            id_evento=evento.id_evento,
            tipo_evento=evento.tipo_evento,
            fecha_evento=evento.fecha_evento,
            modulo=evento.modulo,
            resultado=evento.resultado.value if hasattr(evento.resultado, "value") else evento.resultado,
            detalle=evento.detalle,
            id_usuario=evento.id_usuario,
            categoria=evento.categoria,
            estado=evento.estado,
            id_sesion=evento.id_sesion,
            nombre_usuario=evento.nombre_usuario,
            direccion_ip=evento.direccion_ip,
            user_agent=evento.user_agent,
            descripcion=evento.descripcion,
            integridad_ok=integridad == "INTEGRO",
            integridad=integridad,
        )
        for evento, integridad in resultado["items"]
    ]

    if resultado["saturada"]:
        response.status_code = 206

    return AuditoriaPaginadaResponse(
        total=resultado["total"],
        pagina=resultado["pagina"],
        tamano=resultado["tamano"],
        items=items,
        mensaje=resultado["mensaje"],
    )


@router.get(
    "/",
    response_model=AuditoriaPaginadaResponse,
    responses={
        206: {"model": AuditoriaPaginadaResponse, "description": "Consulta extensa: respuesta parcial."},
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse, "description": "Violación de integridad detectada."},
    },
)
def consultar_auditoria(
    response: Response,
    id_usuario: Optional[int] = Query(None),
    tipo_evento: Optional[int] = Query(None),
    categoria: Optional[EventoCategoria] = Query(None),
    fecha_desde: Optional[datetime] = Query(None),
    fecha_hasta: Optional[datetime] = Query(None),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(verificar_acceso_auditoria),
):
    return _consultar(
        response=response,
        db=db,
        usuario_actual=usuario_actual,
        id_usuario=id_usuario,
        tipo_evento=tipo_evento,
        categoria=categoria,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        tamano=tamano,
        archivados=False,
    )


@router.get(
    "/archivado/",
    response_model=AuditoriaPaginadaResponse,
    responses={
        206: {"model": AuditoriaPaginadaResponse, "description": "Consulta extensa: respuesta parcial."},
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse, "description": "Violación de integridad detectada."},
    },
    summary="Consultar el archivo histórico de auditoría (RF-10)",
)
def consultar_auditoria_archivada(
    response: Response,
    id_usuario: Optional[int] = Query(None),
    tipo_evento: Optional[int] = Query(None),
    categoria: Optional[EventoCategoria] = Query(None),
    fecha_desde: Optional[datetime] = Query(None),
    fecha_hasta: Optional[datetime] = Query(None),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(verificar_acceso_auditoria),
):
    return _consultar(
        response=response,
        db=db,
        usuario_actual=usuario_actual,
        id_usuario=id_usuario,
        tipo_evento=tipo_evento,
        categoria=categoria,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        tamano=tamano,
        archivados=True,
    )


@router.get(
    "/exportar",
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        500: {"model": ErrorResponse, "description": "Violación de integridad detectada."},
    },
    summary="Exportar el historial de auditoría completo en CSV (RF-10)",
)
def exportar_auditoria(
    id_usuario: Optional[int] = Query(None),
    tipo_evento: Optional[int] = Query(None),
    categoria: Optional[EventoCategoria] = Query(None),
    fecha_desde: Optional[datetime] = Query(None),
    fecha_hasta: Optional[datetime] = Query(None),
    archivados: bool = Query(False, description="Exportar el archivo histórico en vez del log activo."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(verificar_acceso_auditoria),
) -> StreamingResponse:
    """Entrega en un solo request lo que antes costaba una petición por página.

    El conteo, la verificación de integridad y el evento de auditoría ocurren una
    única vez; el archivo se transmite en streaming.
    """
    use_case = ExportarAuditoriaUseCase(
        eventos_repo=SqlAlchemyEventoRepository(db),
        usuarios_repo=SqlAlchemyUsuarioRepository(db),
        db=db,
    )
    lineas, total_disponible, total_exportado = use_case.execute(
        usuario_actual=usuario_actual,
        id_usuario=id_usuario,
        tipo_evento=tipo_evento,
        categoria=categoria,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        archivados=archivados,
    )

    nombre = f"auditoria-{datetime.now().date().isoformat()}.csv"
    return StreamingResponse(
        lineas,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            # El cliente deriva "truncado" comparando ambos; requieren estar en
            # `expose_headers` del CORS o el navegador se los oculta.
            "X-Total-Registros": str(total_disponible),
            "X-Registros-Exportados": str(total_exportado),
        },
    )


@router.api_route(
    "/{ruta:path}",
    methods=["PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
@router.api_route(
    "/",
    methods=["PUT", "PATCH", "DELETE"],
    responses={405: {"model": ErrorResponse}},
    summary="Bloqueado: los registros de auditoría son inmutables",
)
def rechazar_modificacion_auditoria() -> None:
    """FA de inmutabilidad: PUT/PATCH/DELETE quedan bloqueados en la API.

    La base de datos ya los bloquea con triggers; esta ruta existe para que el
    cliente reciba el mensaje del RF y el formato de error del proyecto en vez
    del `{"detail": "Method Not Allowed"}` por defecto de FastAPI.
    """
    raise MethodNotAllowedError(code="AUDITORIA_INMUTABLE", message=MENSAJE_INMUTABLE)
