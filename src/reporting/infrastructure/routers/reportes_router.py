# | Fecha      | Nombre   | Que se hizo                                                          |
# |------------|----------|----------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: catálogo, opciones de filtros, vista previa, generación, descarga y cancelación |
"""Router FastAPI de reportes (`/reportes`, RF-104).

  GET   /reportes/catalogo                        — Reportes que el rol puede generar, con sus filtros.
  GET   /reportes/opciones/{filtro}               — Valores de un filtro (fincas, animales, áreas…) del alcance.
  POST  /reportes/vista-previa                    — Primeras 20 filas o resumen, registros estimados.
  POST  /reportes                                 — Genera (≤1.000 registros, 201) o encola (>1.000, 202).
  GET   /reportes                                 — Mis reportes: estado y partes descargables.
  GET   /reportes/{id}/partes/{n}/descarga        — Archivo (solo el dueño, 48 h; 403 / 410).
  PATCH /reportes/{id}/cancelado                  — Cancela uno que se genera en segundo plano.

RBAC: cada tipo de reporte tiene su recurso ``reporte_<tipo>`` con la acción Ejecutar; los permitidos para el rol
se leen de ``modulo1.permisos`` en cada request y el caso de uso responde 403 si el tipo no está entre ellos.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.reporting.application.use_cases.reportes.cancelar_reporte_use_case import CancelarReporteUseCase
from src.reporting.application.use_cases.reportes.consultar_catalogo_reportes_use_case import (
    ConsultarCatalogoReportesUseCase,
)
from src.reporting.application.use_cases.reportes.descargar_reporte_use_case import DescargarReporteUseCase
from src.reporting.application.use_cases.reportes.generacion import Solicitante
from src.reporting.application.use_cases.reportes.listar_reportes_use_case import ListarReportesUseCase
from src.reporting.application.use_cases.reportes.previsualizar_reporte_use_case import PrevisualizarReporteUseCase
from src.reporting.application.use_cases.reportes.solicitar_reporte_use_case import (
    MENSAJE_SEGUNDO_PLANO,
    SolicitarReporteUseCase,
)
from src.reporting.domain.reportes.catalogo import CATALOGO
from src.reporting.domain.reportes.solicitud import EN_PROCESO, SolicitudReporte
from src.reporting.infrastructure.adapters.avisos_reportes_m01_adapter import AvisosReportesM01Adapter
from src.reporting.infrastructure.adapters.instantanea_reportes import abrir_instantanea
from src.reporting.infrastructure.adapters.renderizador_reportes import RenderizadorReportes
from src.reporting.infrastructure.adapters.solicitante_reportes import construir_solicitante
from src.reporting.infrastructure.dto.reporte_dto import SolicitarReporteDTO, VistaPreviaReporteDTO
from src.reporting.infrastructure.repositories.solicitud_reporte_repository import SqlAlchemySolicitudReporteRepository
from src.reporting.infrastructure.schema.reporte_schema import (
    ParteReporteResponse,
    ReporteCatalogoResponse,
    ReporteResponse,
    VistaPreviaResponse,
)
from src.reporting.infrastructure.repositories.fuente_reportes_repository import SqlAlchemyFuenteReportesRepository
from src.shared.database import get_db, sesion_sistema
from src.shared.errors import AuthorizationError
from src.shared.fechas import nombre_zona_usuario
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/reportes", tags=["Reportes (RF-104)"])

_ERRORES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse},
    404: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
}


def _solicitante(db: Session, usuario: UsuarioActual) -> Solicitante:
    return construir_solicitante(db, usuario.id_usuario, usuario.id_rol, nombre_zona_usuario())


def _respuesta(s: SolicitudReporte, partes: list | None = None, estado: str | None = None) -> ReporteResponse:
    estado = estado or s.estado
    return ReporteResponse(
        id_reporte=s.id_solicitud_reporte, tipo_reporte=s.tipo_reporte, titulo=CATALOGO[s.tipo_reporte].titulo,
        formato=s.formato, estado=estado, filtros_aplicados=s.filtros, numero_registros=s.numero_registros,
        tamano_archivo_kb=s.tamano_archivo_kb, checksum_sha256=s.checksum_sha256,
        mensaje=MENSAJE_SEGUNDO_PLANO if estado == EN_PROCESO else s.mensaje_error,
        fecha_solicitud=s.fecha_solicitud, fecha_generacion=s.fecha_generacion, fecha_expiracion=s.fecha_expiracion,
        partes=[ParteReporteResponse(numero_parte=p.numero_parte, nombre_archivo=p.nombre_archivo,
                                     tamano_bytes=p.tamano_bytes, checksum_sha256=p.checksum_sha256)
                for p in (partes or [])],
    )


@router.get("/catalogo", response_model=list[ReporteCatalogoResponse], responses=_ERRORES,
            summary="Reportes que el rol puede generar y sus filtros (RF-104)")
def catalogo(db: Session = Depends(get_db), usuario_actual: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** autenticado. Solo lista los tipos con permiso Ejecutar para el rol (vacío si no tiene ninguno)."""
    return ConsultarCatalogoReportesUseCase().execute(_solicitante(db, usuario_actual))


@router.get("/opciones/{filtro}", response_model=list[dict[str, Any]], responses=_ERRORES,
            summary="Valores elegibles de un filtro de reportes (RF-104)")
def opciones(filtro: Literal["finca", "especie", "activo", "lote", "infraestructura", "sensor", "periodo"],
             db: Session = Depends(get_db), usuario_actual: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** permiso para generar al menos un reporte (403 si no). Solo lo de las fincas del usuario."""
    solicitante = _solicitante(db, usuario_actual)
    if not solicitante.permitidos:
        raise AuthorizationError(code="REPORTE_NO_AUTORIZADO", field="filtro",
                                 message="Tu rol no tiene permiso para generar reportes.")
    return SqlAlchemyFuenteReportesRepository(db).opciones(filtro, solicitante.fincas)


@router.post("/vista-previa", response_model=VistaPreviaResponse, responses=_ERRORES,
             summary="Vista previa de un reporte: primeras 20 filas o resumen (RF-104)")
def vista_previa(dto: VistaPreviaReporteDTO, db: Session = Depends(get_db),
                 usuario_actual: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** permiso Ejecutar sobre el recurso del tipo (403 si no).

    Filtro faltante o fuera de su lista → 400. Animal, área o finca de otra finca → 403 (404 si no existe). Período
    no cerrado (en los reportes contables) → 422. Sin datos: 200 con `sin_datos = true` y el mensaje."""
    return PrevisualizarReporteUseCase(abrir_instantanea).execute(
        dto.tipo_reporte, dto.filtros, _solicitante(db, usuario_actual))


@router.post("", response_model=ReporteResponse, status_code=201,
             responses={**_ERRORES, 202: {"model": ReporteResponse, "description": "Se genera en segundo plano"}},
             summary="Generar un reporte en PDF o Excel (RF-104)")
def solicitar(dto: SolicitarReporteDTO, db: Session = Depends(get_db),
              usuario_actual: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** permiso Ejecutar sobre el recurso del tipo.

    Hasta 1.000 registros: 201 con el reporte GENERADO y sus partes para descargar. Más de 1.000: 202 EN_PROCESO;
    la bandeja avisa cuando esté listo. Mismas validaciones que la vista previa; sin datos → 422."""
    use_case = SolicitarReporteUseCase(db, SqlAlchemySolicitudReporteRepository(db), abrir_instantanea,
                                       RenderizadorReportes(), AvisosReportesM01Adapter(sesion_sistema))
    solicitud = use_case.execute(dto.tipo_reporte, dto.formato, dto.filtros, _solicitante(db, usuario_actual))
    partes = SqlAlchemySolicitudReporteRepository(db).listar_archivos(solicitud.id_solicitud_reporte)
    respuesta = _respuesta(solicitud, partes)
    if solicitud.estado == EN_PROCESO:
        return JSONResponse(status_code=202, content=respuesta.model_dump(mode="json"))
    return respuesta


@router.get("", response_model=list[ReporteResponse], responses=_ERRORES, summary="Mis reportes (RF-104)")
def listar(db: Session = Depends(get_db), usuario_actual: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** autenticado; solo los propios. Los vencidos (48 h) salen EXPIRADOS y sin partes."""
    return [_respuesta(r["solicitud"], r["partes"], r["estado"])
            for r in ListarReportesUseCase(SqlAlchemySolicitudReporteRepository(db)).execute(usuario_actual.id_usuario)]


@router.get("/{id_reporte}/partes/{numero_parte}/descarga",
            responses={**_ERRORES, 410: {"model": ErrorResponse}, 200: {"content": {"application/pdf": {}}}},
            summary="Descargar una parte de un reporte (RF-104)")
def descargar(id_reporte: UUID, numero_parte: int = Path(ge=1, le=999), db: Session = Depends(get_db),
              usuario_actual: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** solo quien pidió el reporte (403 para cualquier otro). Vencido → 410. Si el archivo no pasa la
    verificación de integridad, el reporte queda fallido y responde 422."""
    archivo = DescargarReporteUseCase(db, SqlAlchemySolicitudReporteRepository(db),
                                      AvisosReportesM01Adapter(sesion_sistema)).execute(
        id_reporte, numero_parte, usuario_actual.id_usuario)
    return Response(content=archivo.contenido, media_type=archivo.tipo_contenido, headers={
        "Content-Disposition": f'attachment; filename="{archivo.nombre_archivo}"',
        "X-Checksum-SHA256": archivo.checksum_sha256})


@router.patch("/{id_reporte}/cancelado", response_model=ReporteResponse, responses=_ERRORES,
              summary="Cancelar un reporte en segundo plano (RF-104)")
def cancelar(id_reporte: UUID, db: Session = Depends(get_db), usuario_actual: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** solo quien lo pidió (403). Solo si sigue EN_PROCESO; si no → 422."""
    return _respuesta(CancelarReporteUseCase(db, SqlAlchemySolicitudReporteRepository(db)).execute(
        id_reporte, usuario_actual.id_usuario))
