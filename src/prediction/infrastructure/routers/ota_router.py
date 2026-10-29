# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-204-G43/207-G46 RF-70: DISTRIBUCION_POSPUESTA al crear fuera de ventana |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-04/CU06 H-02 RF-70/73: consultar la OTA no deja evento; nombre de versión |
"""Router FastAPI para distribución OTA de modelos Edge (`/prediccion`).

RF-70 CU-06: Consulta del estado OTA y listado de despliegues por dispositivo.
  GET /prediccion/modelos/{id_version}/ota-status
  GET /prediccion/despliegues

DEV-15 (D6 de AIOT-DEV-03): orquestador OTA por componente.
  POST /prediccion/ota/distribuciones         — Distribuir una versión (RBAC 44, E)
  GET  /prediccion/ota/distribuciones/{id}    — Estado del rollout (RBAC 44, R)
  POST /prediccion/ota/reportes               — Interno: reportes del nodo (token de servicio del broker)
  GET  /prediccion/ota/artefactos/{id}        — Descarga con URL firmada y temporal (Range)

Autorización RBAC:
  recurso ota_status = id_recurso 44
  R=2 (Administrador, Ingeniero); E=5 (Administrador, DB-04)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.ota.consultar_distribucion_ota_use_case import ConsultarDistribucionOtaUseCase
from src.prediction.application.use_cases.ota.consultar_ota_status_use_case import ConsultarOtaStatusUseCase
from src.prediction.application.use_cases.ota.crear_distribucion_ota_use_case import CrearDistribucionOtaUseCase
from src.prediction.application.use_cases.ota.listar_despliegues_use_case import ListarDesplieguesUseCase
from src.prediction.application.use_cases.ota.obtener_artefacto_ota_use_case import ObtenerArtefactoOtaUseCase
from src.prediction.application.use_cases.ota.registrar_reporte_ota_use_case import RegistrarReporteOtaUseCase
from src.prediction.infrastructure.adapters.ota_edge_adapters import (
    AvisoOtaBrokerAdapter,
    NodoOtaM09Adapter,
    UrlDescargaHmacAdapter,
)
from src.prediction.infrastructure.adapters.version_modelo_adapter import VersionModeloAdapter
from src.prediction.infrastructure.dto.ota_dto import CrearDistribucionOtaDTO, ReporteOtaDTO
from src.prediction.infrastructure.models.version_modelo_model import VersionModeloModel
from src.prediction.infrastructure.repositories.despliegue_ota_repository import SqlAlchemyDespliegueOtaRepository
from src.prediction.infrastructure.repositories.distribucion_ota_repository import SqlAlchemyDistribucionOtaRepository
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.repositories.version_modelo_repository import SqlAlchemyVersionModeloRepository
from src.prediction.infrastructure.schema.despliegue_ota_schema import (
    DespliegueOtaListResponse,
    DespliegueOtaResponse,
    DistribucionOtaResponse,
    OtaStatusResponse,
    ReporteOtaResponse,
)
from src.shared.broker_auth import require_token_servicio_broker
from src.shared.database import get_db, get_db_sistema
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion", tags=["Predicción M04 - OTA"])

_RECURSO = 44


def _con_nombre_version(db: Session, despliegues: list[DespliegueOtaResponse]) -> list[DespliegueOtaResponse]:
    """CU06 H-02: nombre de la versión desplegada y de la anterior, una consulta por página."""
    ids = {d.id_version_modelo for d in despliegues} | {
        d.id_version_modelo_anterior for d in despliegues if d.id_version_modelo_anterior is not None
    }
    if ids:
        nombres = dict(db.execute(
            select(VersionModeloModel.id_version_modelo, VersionModeloModel.nombre_version)
            .where(VersionModeloModel.id_version_modelo.in_(ids))
        ).all())
        for d in despliegues:
            d.nombre_version = nombres.get(d.id_version_modelo)
            d.nombre_version_anterior = nombres.get(d.id_version_modelo_anterior)
    return despliegues


@router.get(
    "/modelos/{id_version}/ota-status",
    response_model=OtaStatusResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Consultar estado OTA de una versión de modelo (RF-70)",
)
def consultar_ota_status(
    id_version: int,
    id_dispositivo: Optional[int] = Query(None, description="Filtrar por ID de dispositivo IoT."),
    estado: Optional[str] = Query(None, description="Filtrar por estado: EXITOSO, FALLIDO, PENDIENTE, SIN_CAMBIOS, EN_PROCESO."),
    db: Session = Depends(get_db),
) -> OtaStatusResponse:
    use_case = ConsultarOtaStatusUseCase(
        repo=SqlAlchemyDespliegueOtaRepository(db),
        version_port=VersionModeloAdapter(db),
    )
    id_version_resultado, despliegues = use_case.execute(
        id_version=id_version,
        id_dispositivo=id_dispositivo,
        estado=estado,
    )
    return OtaStatusResponse(
        id_version_modelo=id_version_resultado,
        despliegues=_con_nombre_version(db, [DespliegueOtaResponse.from_entity(d) for d in despliegues]),
        total=len(despliegues),
    )


@router.get(
    "/despliegues",
    response_model=DespliegueOtaListResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Listar despliegues OTA con filtros opcionales (RF-70)",
)
def listar_despliegues(
    id_version: Optional[int] = Query(None, description="Filtrar por ID de versión de modelo."),
    id_dispositivo: Optional[int] = Query(None, description="Filtrar por ID de dispositivo IoT."),
    estado: Optional[str] = Query(None, description="Filtrar por estado: EXITOSO, FALLIDO, PENDIENTE, SIN_CAMBIOS, EN_PROCESO."),
    limit: int = Query(20, ge=1, le=100, description="Registros por página (máx. 100)."),
    offset: int = Query(0, ge=0, description="Desplazamiento de la página."),
    db: Session = Depends(get_db),
) -> DespliegueOtaListResponse:
    use_case = ListarDesplieguesUseCase(
        repo=SqlAlchemyDespliegueOtaRepository(db),
        version_port=VersionModeloAdapter(db),
    )
    items, total = use_case.execute(
        id_version=id_version,
        id_dispositivo=id_dispositivo,
        estado=estado,
        limit=limit,
        offset=offset,
    )
    return DespliegueOtaListResponse(
        total=total,
        items=_con_nombre_version(db, [DespliegueOtaResponse.from_entity(d) for d in items]),
    )


# ── DEV-15: orquestador OTA por componente (RF-70/RF-73, D6 de AIOT-DEV-03) ──


def _ota_edge(db: Session) -> dict:
    return {
        "nodo_port": NodoOtaM09Adapter(db),
        "aviso_port": AvisoOtaBrokerAdapter(),
        "url_port": UrlDescargaHmacAdapter(),
    }


@router.post(
    "/ota/distribuciones",
    response_model=DistribucionOtaResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Distribuir por OTA una versión de un componente a varios nodos (RF-70, D6)",
)
def crear_distribucion_ota(
    dto: CrearDistribucionOtaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DistribucionOtaResponse:
    """Crea un despliegue PENDIENTE por nodo y avisa `ota/notify` a la fase canary.

    El orden de `lista_dispositivos_objetivo` decide el rollout: el primero es el
    canary; luego `porcentaje_parcial` % (20–30) y por último el resto. Cada fase
    se avisa cuando todos los nodos de la anterior reportan `activated`.
    """
    resultado = CrearDistribucionOtaUseCase(
        db=db,
        version_repo=SqlAlchemyVersionModeloRepository(db),
        distribucion_repo=SqlAlchemyDistribucionOtaRepository(db),
        despliegue_repo=SqlAlchemyDespliegueOtaRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        **_ota_edge(db),
    ).execute(dto, usuario_actual.id_usuario)
    return DistribucionOtaResponse.from_resultado(resultado)


@router.get(
    "/ota/distribuciones/{id_distribucion_ota}",
    response_model=DistribucionOtaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Estado de una distribución OTA y de cada nodo (RF-70)",
)
def consultar_distribucion_ota(
    id_distribucion_ota: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DistribucionOtaResponse:
    resultado = ConsultarDistribucionOtaUseCase(
        distribucion_repo=SqlAlchemyDistribucionOtaRepository(db),
        despliegue_repo=SqlAlchemyDespliegueOtaRepository(db),
    ).execute(id_distribucion_ota)
    return DistribucionOtaResponse.from_resultado(resultado)


@router.post(
    "/ota/reportes",
    response_model=ReporteOtaResponse,
    status_code=200,
    dependencies=[Depends(require_token_servicio_broker)],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Reporte de un nodo durante la OTA, reenviado por el broker (RF-70/RF-73, BRK-08)",
)
def registrar_reporte_ota(
    dto: ReporteOtaDTO,
    db: Session = Depends(get_db_sistema),
) -> ReporteOtaResponse:
    """Interno: lo llama el broker con su token de servicio (`BROKER_SERVICE_TOKEN`)."""
    resultado = RegistrarReporteOtaUseCase(
        db=db,
        despliegue_repo=SqlAlchemyDespliegueOtaRepository(db),
        distribucion_repo=SqlAlchemyDistribucionOtaRepository(db),
        version_repo=SqlAlchemyVersionModeloRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        **_ota_edge(db),
    ).execute(dto)
    return ReporteOtaResponse(
        id_despliegue_ota=resultado.despliegue.id_despliegue_ota,
        estado_despliegue=resultado.despliegue.estado_despliegue,
        evento_rf73=resultado.evento_rf73,
        sin_cambios=resultado.sin_cambios,
        fase_avanzada_a=resultado.fase_avanzada_a,
    )


@router.get(
    "/ota/artefactos/{id_despliegue_ota}",
    response_class=FileResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 410: {"model": ErrorResponse}},
    summary="Descargar el artefacto de un despliegue OTA con URL firmada (admite Range)",
)
def descargar_artefacto_ota(
    id_despliegue_ota: int,
    expira: int = Query(...),
    firma: str = Query(..., min_length=64, max_length=64),
    db: Session = Depends(get_db_sistema),
) -> FileResponse:
    """Sin JWT: la URL firmada y temporal que recibió el nodo en `ota/notify` es la credencial.
    Responde `206 Partial Content` cuando el nodo pide un rango (`Range: bytes=...`)."""
    archivo = ObtenerArtefactoOtaUseCase(
        despliegue_repo=SqlAlchemyDespliegueOtaRepository(db),
        version_repo=SqlAlchemyVersionModeloRepository(db),
        url_port=UrlDescargaHmacAdapter(),
    ).execute(id_despliegue_ota, expira, firma)
    return FileResponse(archivo, media_type="application/octet-stream", filename=archivo.name)
