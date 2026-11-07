# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-95..102 / RF-AE01: consulta AAEF para AgroFusion y administración de la integración |
"""Routers de M07 (``/integracion``). Sin lógica: arman el caso de uso con la fábrica y lo ejecutan.

- ``GET /integracion/aaef/productores/{nit}``: la consulta de AgroFusion (RF-AE01). Su autenticación
  es el token de canal y la resuelve el Gateway (RF-95) para poder auditar también los rechazos.
- El resto es administración con la sesión web y RBAC por nombre de recurso (C=1, R=2, U=3, D=4, E=5).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from sqlalchemy.orm import Session

from src.accounting_integration.application.use_cases.clientes.registrar_cliente_externo_use_case import SolicitudCliente
from src.accounting_integration.application.use_cases.contratos.gestionar_contratos_use_case import SolicitudContrato
from src.accounting_integration.domain.entities.cliente_externo import ClienteExterno
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import FiltrosAuditoria
from src.accounting_integration.infrastructure import gateway_aaef
from src.accounting_integration.infrastructure.dto.m07_dto import (
    AprobarAnexoDTO,
    DeprecarContratoDTO,
    EditarClienteDTO,
    MotivoDTO,
    RegistrarAnexoDTO,
    RegistrarClienteDTO,
    RegistrarContratoDTO,
    RotarSecretoDTO,
)
from src.accounting_integration.infrastructure.factoria import M07
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.errors import AuthorizationError, MethodNotAllowedError, ValidationError
from src.shared.rbac import require_permission_sobre as permiso
from src.shared.rbac import tiene_permiso_sobre
from src.shared.schemas import ErrorResponse

C, R, U, D, E = 1, 2, 3, 4, 5
TipoEvento = Literal[
    "PAQUETE_AAEF_CONSULTADO", "SOLICITUD_RECHAZADA", "CREDENCIALES_EN_URL", "RATE_LIMIT_EXCEDIDO", "VISTA_AAEF_GENERADA",
    "PREPARACION_AAEF_FALLIDA", "TOKEN_CANAL_EMITIDO", "TOKEN_CANAL_RECHAZADO", "USUARIO_CREADO_M2M",
    "USUARIO_ACTUALIZADO_M2M", "ESTADO_USUARIO_CAMBIADO_M2M", "CLIENTE_REGISTRADO", "CLIENTE_EDITADO",
    "CLIENTE_SUSPENDIDO", "CLIENTE_REACTIVADO", "CLIENTE_REVOCADO", "SECRETO_ROTADO", "CONTRATO_REGISTRADO",
    "CONTRATO_ACTIVADO", "CONTRATO_DEPRECADO", "CONTRATO_INACTIVADO", "CONTRATO_ACTIVACION_BLOQUEADA",
    "ANEXO_REGISTRADO", "ANEXO_EN_REVISION", "ANEXO_APROBADO", "ANEXO_VALIDACION_FALLIDA",
    "INTENTO_MODIFICACION_AUDITORIA", "ACCESO_AUDITORIA_DENEGADO", "REGISTRO_AUDITORIA_CORRUPTO",
]
_ERRORES = {c: {"model": ErrorResponse} for c in (400, 401, 403, 404, 409, 410, 412, 422, 429, 500, 503)}
_NIT = Path(pattern=r"^[0-9]{6,15}$", description="NIT del titular (RF-19), solo dígitos y sin dígito de verificación.")

router = APIRouter(prefix="/integracion", responses=_ERRORES)


def _m07(db: Session = Depends(get_db)) -> M07:
    return M07(db)


# --- Consulta AAEF (RF-95, RF-AE01) -----------------------------------------------------------------

TAG_AAEF = "M07 · Consulta contable AAEF"


@router.get("/aaef/productores/{nit}", tags=[TAG_AAEF], summary="AgroFusion: documento contable AAEF del productor",
            responses={200: {"content": {"application/json": {}},
                             "description": "Envelope AAEF con X-Request-Id, X-Version-Contrato-AAEF y X-Content-SHA256"}})
def consultar_aaef(
    request: Request,
    nit: str,
    desde: Optional[str] = Query(None, description="Primer día de un período contable (AAAA-MM-DD)."),
    hasta: Optional[str] = Query(None, description="Último día de un período contable (AAAA-MM-DD)."),
    db: Session = Depends(get_db),
):
    """RF-AE01. ``Authorization: Bearer <token de canal>`` (de ``POST /integraciones/agrofusion/token``) y
    ``Accept-Version`` opcional. Solo períodos cerrados y con el rango alineado a ellos; no guarda nada."""
    return gateway_aaef.atender(request, db, nit, desde, hasta)


@router.get("/aaef/vista-previa/productores/{nit}", tags=[TAG_AAEF],
            dependencies=[Depends(permiso("exportacion_contable", R))],
            summary="Vista previa del documento AAEF con la sesión del Contador")
def vista_previa_aaef(request: Request, nit: str = _NIT, desde: date = Query(...), hasta: date = Query(...),
                      db: Session = Depends(get_db), m07: M07 = Depends(_m07),
                      usuario_actual: UsuarioActual = Depends(get_current_user)):
    """Lo mismo que recibirá AgroFusion, para revisarlo antes (RF-AE02 5.10). Exige todas las fincas del titular."""
    if desde > hasta:
        raise ValidationError(code="PARAMETROS_INVALIDOS", field="hasta",
                              message="La fecha «hasta» no puede ser anterior a la fecha «desde».")
    usuario = m07.usuarios.obtener(usuario_actual.id_usuario)
    return gateway_aaef.vista_previa(request, db, nit, desde, hasta, usuario_actual.id_usuario, usuario.correo)


# --- Clientes externos (RF-101) ----------------------------------------------------------------------

TAG_CLIENTES = "M07 · Clientes externos"


def _cliente(m07: M07, cliente: ClienteExterno) -> dict:
    credencial = m07.clientes.credencial_activa(cliente.id_cliente_externo)
    return {
        "id_cliente_externo": cliente.id_cliente_externo, "codigo": cliente.codigo, "nombre": cliente.nombre,
        "identificador_publico": cliente.identificador_publico, "estado": cliente.estado, "tipo": cliente.tipo,
        "ip_permitida": cliente.ip_permitida, "ttl_token_canal_minutos": cliente.ttl_token_canal_minutos,
        "canales": [{"canal": c, "limite_por_minuto": n} for c, n in sorted(cliente.canales.items())],
        "fecha_actualizacion": cliente.fecha_actualizacion,
        "credencial": ({"fecha_emision": credencial.fecha_emision, "fecha_expiracion": credencial.fecha_expiracion}
                       if credencial else None),
    }


@router.post("/clientes", status_code=201, tags=[TAG_CLIENTES], dependencies=[Depends(permiso("clientes_externos", C))],
             summary="Registrar un cliente externo (el secreto se muestra una sola vez)")
def registrar_cliente(dto: RegistrarClienteDTO, m07: M07 = Depends(_m07),
                      usuario_actual: UsuarioActual = Depends(get_current_user)):
    cliente, secreto = m07.registrar_cliente().execute(SolicitudCliente(
        dto.codigo, dto.nombre, dto.identificador_publico, dto.fecha_vencimiento, dto.canales_dict(), dto.ip_permitida,
        dto.ttl_token_canal_minutos, dto.client_secret), usuario_actual.id_usuario)
    return {**_cliente(m07, cliente), "client_id": cliente.identificador_publico, "client_secret": secreto,
            "aviso": "Guarde el secreto ahora: no se vuelve a mostrar."}


@router.get("/clientes", tags=[TAG_CLIENTES], dependencies=[Depends(permiso("clientes_externos", R))],
            summary="Listar los clientes externos")
def listar_clientes(m07: M07 = Depends(_m07)):
    return [_cliente(m07, c) for c in m07.clientes.listar()]


@router.patch("/clientes/{id_cliente_externo}", tags=[TAG_CLIENTES], dependencies=[Depends(permiso("clientes_externos", U))],
              summary="Editar canales, IP permitida y vigencia del token")
def editar_cliente(id_cliente_externo: int, dto: EditarClienteDTO, m07: M07 = Depends(_m07),
                   usuario_actual: UsuarioActual = Depends(get_current_user)):
    cliente = m07.gestionar_cliente().editar(id_cliente_externo, dto.canales_dict(), dto.ip_permitida,
                                             dto.ttl_token_canal_minutos, dto.fecha_actualizacion, usuario_actual.id_usuario)
    return _cliente(m07, cliente)


def _cambiar_estado(accion: str, id_cliente_externo: int, dto: MotivoDTO, m07: M07, usuario_actual: UsuarioActual) -> dict:
    return _cliente(m07, m07.gestionar_cliente().cambiar_estado(id_cliente_externo, accion, dto.motivo,
                                                                usuario_actual.id_usuario))


@router.post("/clientes/{id_cliente_externo}/suspender", tags=[TAG_CLIENTES],
             dependencies=[Depends(permiso("clientes_externos", U))], summary="Suspender un cliente (sus tokens dejan de servir)")
def suspender_cliente(id_cliente_externo: int, dto: MotivoDTO, m07: M07 = Depends(_m07),
                      usuario_actual: UsuarioActual = Depends(get_current_user)):
    return _cambiar_estado("suspender", id_cliente_externo, dto, m07, usuario_actual)


@router.post("/clientes/{id_cliente_externo}/reactivar", tags=[TAG_CLIENTES],
             dependencies=[Depends(permiso("clientes_externos", U))], summary="Reactivar un cliente suspendido")
def reactivar_cliente(id_cliente_externo: int, dto: MotivoDTO, m07: M07 = Depends(_m07),
                      usuario_actual: UsuarioActual = Depends(get_current_user)):
    return _cambiar_estado("reactivar", id_cliente_externo, dto, m07, usuario_actual)


@router.post("/clientes/{id_cliente_externo}/revocar", tags=[TAG_CLIENTES],
             dependencies=[Depends(permiso("clientes_externos", D))], summary="Revocar un cliente de forma definitiva")
def revocar_cliente(id_cliente_externo: int, dto: MotivoDTO, m07: M07 = Depends(_m07),
                    usuario_actual: UsuarioActual = Depends(get_current_user)):
    return _cambiar_estado("revocar", id_cliente_externo, dto, m07, usuario_actual)


@router.post("/clientes/{id_cliente_externo}/rotar", tags=[TAG_CLIENTES],
             dependencies=[Depends(permiso("clientes_externos", U))], summary="Rotar el secreto (el anterior deja de servir ya)")
def rotar_secreto(id_cliente_externo: int, dto: RotarSecretoDTO, m07: M07 = Depends(_m07),
                  usuario_actual: UsuarioActual = Depends(get_current_user)):
    secreto = m07.gestionar_cliente().rotar(id_cliente_externo, dto.motivo, dto.fecha_vencimiento, dto.client_secret,
                                            usuario_actual.id_usuario)
    return {"client_secret": secreto, "aviso": "Guarde el secreto ahora: no se vuelve a mostrar."}


# --- Anexo de mapeo y contratos (RF-AE02, RF-98) ---------------------------------------------------

TAG_CONTRATOS = "M07 · Contrato AAEF y anexo de mapeo"


@router.get("/anexos", tags=[TAG_CONTRATOS], dependencies=[Depends(permiso("contratos_aaef", R))],
            summary="Listar los anexos de mapeo")
def listar_anexos(m07: M07 = Depends(_m07)):
    return m07.contratos.listar_anexos()


@router.post("/anexos", status_code=201, tags=[TAG_CONTRATOS], dependencies=[Depends(permiso("contratos_aaef", C))],
             summary="Registrar un anexo de mapeo (queda en borrador)")
def registrar_anexo(dto: RegistrarAnexoDTO, m07: M07 = Depends(_m07),
                    usuario_actual: UsuarioActual = Depends(get_current_user)):
    return m07.gestionar_anexos().registrar(dto.codigo_anexo, dto.version_anexo, dto.ruta_documento,
                                            dto.sha256_documento, usuario_actual.id_usuario)


@router.post("/anexos/{id_mapeo_anexo_aaef}/revision", tags=[TAG_CONTRATOS],
             dependencies=[Depends(permiso("contratos_aaef", E))],
             summary="Aprobación interna del Contador: valida el mapeo y pasa el anexo a revisión")
def enviar_anexo_a_revision(id_mapeo_anexo_aaef: int, m07: M07 = Depends(_m07),
                            usuario_actual: UsuarioActual = Depends(get_current_user)):
    return m07.gestionar_anexos().enviar_a_revision(id_mapeo_anexo_aaef, usuario_actual.id_usuario)


@router.post("/anexos/{id_mapeo_anexo_aaef}/aprobar", tags=[TAG_CONTRATOS],
             dependencies=[Depends(permiso("contratos_aaef", U))],
             summary="Aprobar el anexo con la evidencia de la prueba de interoperabilidad")
def aprobar_anexo(id_mapeo_anexo_aaef: int, dto: AprobarAnexoDTO, m07: M07 = Depends(_m07),
                  usuario_actual: UsuarioActual = Depends(get_current_user)):
    return m07.gestionar_anexos().aprobar(id_mapeo_anexo_aaef, dto.model_dump(), usuario_actual.id_usuario)


@router.get("/contratos", tags=[TAG_CONTRATOS], dependencies=[Depends(permiso("contratos_aaef", R))],
            summary="Listar las versiones del contrato AAEF")
def listar_contratos(m07: M07 = Depends(_m07)):
    return m07.contratos.listar_contratos()


@router.post("/contratos", status_code=201, tags=[TAG_CONTRATOS], dependencies=[Depends(permiso("contratos_aaef", C))],
             summary="Registrar una versión del contrato (queda pendiente hasta su fecha de vigencia)")
def registrar_contrato(dto: RegistrarContratoDTO, m07: M07 = Depends(_m07),
                       usuario_actual: UsuarioActual = Depends(get_current_user)):
    return m07.gestionar_contratos().registrar(SolicitudContrato(
        dto.contrato_version, dto.tipo_cambio, dto.fecha_vigencia, dto.id_mapeo_anexo_aaef, list(dto.mapeadores),
        dto.periodo_gracia_dias, dto.descripcion), usuario_actual.id_usuario)


@router.post("/contratos/{id_version_contrato_aaef}/activar", tags=[TAG_CONTRATOS],
             dependencies=[Depends(permiso("contratos_aaef", U))], summary="Activar ya una versión pendiente")
def activar_contrato(id_version_contrato_aaef: int, m07: M07 = Depends(_m07),
                     usuario_actual: UsuarioActual = Depends(get_current_user)):
    return m07.gestionar_contratos().activar(id_version_contrato_aaef, usuario_actual.id_usuario)


@router.post("/contratos/{id_version_contrato_aaef}/deprecar", tags=[TAG_CONTRATOS],
             dependencies=[Depends(permiso("contratos_aaef", U))], summary="Deprecar una versión con período de gracia")
def deprecar_contrato(id_version_contrato_aaef: int, dto: DeprecarContratoDTO, m07: M07 = Depends(_m07),
                      usuario_actual: UsuarioActual = Depends(get_current_user)):
    return m07.gestionar_contratos().deprecar(id_version_contrato_aaef, dto.dias_gracia, usuario_actual.id_usuario)


# --- Auditoría de integración (RF-102) -------------------------------------------------------------

TAG_AUDITORIA = "M07 · Auditoría de integración"


def _filtros(tipo_evento: Optional[TipoEvento], id_cliente_externo: Optional[int], desde: Optional[date],
             hasta: Optional[date], endpoint: Optional[str], codigo_http: Optional[int]) -> FiltrosAuditoria:
    return FiltrosAuditoria((tipo_evento,) if tipo_evento else None, id_cliente_externo, desde, hasta, endpoint, codigo_http)


@router.get("/auditoria", tags=[TAG_AUDITORIA], summary="Historial de la integración (paginado, con integridad por registro)")
def consultar_auditoria(
    tipo_evento: Optional[TipoEvento] = None,
    id_cliente_externo: Optional[int] = Query(None, ge=1),
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    endpoint: Optional[str] = Query(None, max_length=255),
    codigo_http: Optional[int] = Query(None, ge=100, le=599),
    pagina: int = Query(1, ge=1),
    tamano: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    m07: M07 = Depends(_m07),
    usuario_actual: UsuarioActual = Depends(get_current_user),
):
    """Con ``auditoria_integracion`` se ve todo; con ``auditoria_integracion_cierres`` (auditor externo) solo las
    consultas contables exitosas y las activaciones del contrato, sin IP ni detalle."""
    if tiene_permiso_sobre(db, usuario_actual.id_rol, "auditoria_integracion", R):
        restringida = False
    elif tiene_permiso_sobre(db, usuario_actual.id_rol, "auditoria_integracion_cierres", R):
        restringida = True
    else:
        m07.auditar_aparte(EventoIntegracion(tipo_evento="ACCESO_AUDITORIA_DENEGADO", severidad="WARNING",
                                             tipo_actor="USUARIO", id_usuario=usuario_actual.id_usuario,
                                             codigo_resultado="ACCESO_DENEGADO"))
        raise AuthorizationError(code="ACCESO_DENEGADO", message="No tiene permiso para consultar la auditoría de la integración.")
    return m07.consultar_auditoria().execute(_filtros(tipo_evento, id_cliente_externo, desde, hasta, endpoint, codigo_http),
                                             pagina, tamano, restringida)


@router.get("/auditoria/exportar", tags=[TAG_AUDITORIA], dependencies=[Depends(permiso("auditoria_integracion", E))],
            summary="Exportar la auditoría filtrada en CSV o JSON")
def exportar_auditoria(
    formato: Literal["csv", "json"] = "csv",
    tipo_evento: Optional[TipoEvento] = None,
    id_cliente_externo: Optional[int] = Query(None, ge=1),
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    endpoint: Optional[str] = Query(None, max_length=255),
    codigo_http: Optional[int] = Query(None, ge=100, le=599),
    m07: M07 = Depends(_m07),
):
    contenido = m07.consultar_auditoria().exportar(
        _filtros(tipo_evento, id_cliente_externo, desde, hasta, endpoint, codigo_http), formato)
    tipo = "application/json" if formato == "json" else "text/csv; charset=utf-8"
    nombre = f"auditoria_integracion_{datetime.now():%Y%m%d_%H%M%S}.{formato}"
    return Response(content=contenido, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.api_route("/auditoria", methods=["PUT", "PATCH", "DELETE"], tags=[TAG_AUDITORIA], include_in_schema=False)
def bloquear_modificacion_auditoria(request: Request, m07: M07 = Depends(_m07)):
    """RF-102 FA-2: la auditoría es inmutable también por API."""
    m07.auditar_aparte(EventoIntegracion(
        tipo_evento="INTENTO_MODIFICACION_AUDITORIA", severidad="CRITICAL", tipo_actor="USUARIO",
        endpoint="/integracion/auditoria", metodo_http=request.method, codigo_http=405,
        codigo_resultado="METODO_NO_PERMITIDO", ip_origen=request.client.host if request.client else None))
    raise MethodNotAllowedError(code="METODO_NO_PERMITIDO", message="La auditoría de la integración no se puede modificar.")
