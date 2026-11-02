# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66/RF-69: rutas para que el motor IA arme su catálogo solo    |
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: solicitud por animal y procesos de reentrenamiento |
"""Rutas internas del motor IA (``motor-ia``): con ellas arma su catálogo sin ``catalogo.json``.

Token ``IOT_INFERENCIA_M04_TOKEN``, sin usuario ni RBAC (como ``POST /prediccion/inferencias``).

  GET  /prediccion/motor/catalogo                      — animales individuales que atiende y su versión.
  POST /prediccion/motor/activos/{id}/version          — copia en SOMBRA para un animal sin versión (RFC-010).
  GET  /prediccion/motor/versiones/{id}/artefacto      — el ``.onnx`` de una versión ACTIVO o SOMBRA.
  GET  /prediccion/motor/activos/{id}/lecturas?horas=  — lecturas para calibrar su línea base (ET-02).
  GET  /prediccion/motor/activos/{id}/retroalimentaciones — diagnósticos vigentes del animal (AJF-14, RF-72).
  POST /prediccion/motor/reentrenamientos/tomar        — toma el proceso PENDIENTE más antiguo (204 si no hay).
  PATCH /prediccion/motor/reentrenamientos/{id}        — latido (fase, progreso, recursos) o cierre.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import uuid

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.prediction.application.use_cases.motor.asignar_version_animal_use_case import AsignarVersionAnimalUseCase
from src.prediction.application.use_cases.motor.obtener_artefacto_version_use_case import (
    ObtenerArtefactoVersionUseCase,
)
from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.infrastructure.adapters.catalogo_motor_m02_adapter import CatalogoMotorM02Adapter
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from src.prediction.infrastructure.repositories.version_modelo_repository import SqlAlchemyVersionModeloRepository
from src.prediction.application.use_cases.reentrenamiento.procesar_reentrenamiento_use_case import (
    ActualizacionProceso, ProcesarReentrenamientoUseCase,
)
from src.prediction.infrastructure.repositories.proceso_reentrenamiento_repository import (
    SqlAlchemyProcesoReentrenamientoRepository,
)
from src.prediction.infrastructure.schema.proceso_reentrenamiento_schema import (
    ActualizarProcesoDTO, ProcesoReentrenamientoResponse, RetroalimentacionesMotorResponse,
)
from src.shared.broker_auth import require_token_servicio_motor_ia
from src.shared.database import get_db_sistema
from src.shared.schemas import ErrorResponse

router = APIRouter(
    prefix="/prediccion/motor",
    tags=["Predicción M04 - Motor IA (interno)"],
    dependencies=[Depends(require_token_servicio_motor_ia)],
    responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)

#: ET-02 calibra con 7–14 días (Tabla 6.1).
MAX_HORAS_LECTURAS = 24 * 14


class VersionMotorResponse(BaseModel):
    id_version_modelo: int
    nombre_version: str
    hash_artefacto_sha256: str
    fuente_datos: str


class AnimalMotorResponse(BaseModel):
    id_activo_biologico: int
    tipo_modelo: str
    #: None: el animal todavía no tiene versión; el motor pide la copia con el POST.
    version: Optional[VersionMotorResponse] = None


class CatalogoMotorResponse(BaseModel):
    animales: list[AnimalMotorResponse]


class LecturasMotorResponse(BaseModel):
    #: Formato largo del contrato IA-1: ``{"timestamp", "variable", "valor", "apto_para_ia"}``.
    lecturas: list[dict[str, Any]]


def _version(v: VersionModelo) -> VersionMotorResponse:
    return VersionMotorResponse(
        id_version_modelo=v.id_version_modelo, nombre_version=v.nombre_version,
        hash_artefacto_sha256=v.hash_artefacto_sha256, fuente_datos=v.fuente_datos,
    )


@router.get("/catalogo", response_model=CatalogoMotorResponse, summary="Animales que atiende el motor IA")
def catalogo(db: Session = Depends(get_db_sistema)) -> CatalogoMotorResponse:
    return CatalogoMotorResponse(animales=[
        AnimalMotorResponse(
            id_activo_biologico=a.id_activo_biologico, tipo_modelo=a.tipo_modelo,
            version=VersionMotorResponse(
                id_version_modelo=a.id_version_modelo, nombre_version=a.nombre_version,
                hash_artefacto_sha256=a.hash_artefacto_sha256, fuente_datos=a.fuente_datos,
            ) if a.id_version_modelo is not None else None,
        )
        for a in CatalogoMotorM02Adapter(db).animales()
    ])


@router.post(
    "/activos/{id_activo}/version",
    response_model=VersionMotorResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Versión propia en SOMBRA para un animal nuevo (copia de la vigente de su tipo)",
)
def asignar_version(id_activo: int, db: Session = Depends(get_db_sistema)) -> VersionMotorResponse:
    """404 ANIMAL_FUERA_DEL_MOTOR o SIN_MODELO_DE_REFERENCIA; si ya tenía versión, la devuelve."""
    version = AsignarVersionAnimalUseCase(
        db=db,
        catalogo=CatalogoMotorM02Adapter(db),
        repo=SqlAlchemyVersionModeloRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    ).execute(id_activo)
    return _version(version)


@router.get(
    "/versiones/{id_version}/artefacto",
    response_class=FileResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Artefacto .onnx de una versión ACTIVO o SOMBRA",
)
def artefacto(id_version: int, db: Session = Depends(get_db_sistema)) -> FileResponse:
    archivo = ObtenerArtefactoVersionUseCase(SqlAlchemyVersionModeloRepository(db)).execute(id_version)
    return FileResponse(archivo, media_type="application/octet-stream", filename=archivo.name)


@router.get(
    "/activos/{id_activo}/lecturas",
    response_model=LecturasMotorResponse,
    summary="Lecturas de ET-02 del animal en las últimas horas, para calibrar su línea base",
)
def lecturas(
    id_activo: int,
    horas: float = Query(..., gt=0, le=MAX_HORAS_LECTURAS),
    db: Session = Depends(get_db_sistema),
) -> LecturasMotorResponse:
    hasta = datetime.now(timezone.utc)
    return LecturasMotorResponse(
        lecturas=CatalogoMotorM02Adapter(db).lecturas(id_activo, hasta - timedelta(hours=horas), hasta)
    )


def _procesar(db: Session) -> ProcesarReentrenamientoUseCase:
    return ProcesarReentrenamientoUseCase(db=db, procesos=SqlAlchemyProcesoReentrenamientoRepository(db),
                                          auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db))


@router.get(
    "/activos/{id_activo}/retroalimentaciones",
    response_model=RetroalimentacionesMotorResponse,
    summary="Diagnósticos clínicos vigentes del animal con la ventana de su inferencia (AJF-14, RF-72)",
)
def retroalimentaciones(id_activo: int, db: Session = Depends(get_db_sistema)) -> RetroalimentacionesMotorResponse:
    """Insumo de ``feat_real_etiquetado``: con ellas el pipeline retira lo sintético (RF-72)."""
    return RetroalimentacionesMotorResponse(
        retroalimentaciones=SqlAlchemyProcesoReentrenamientoRepository(db).retroalimentaciones_verificadas(id_activo))


@router.post(
    "/reentrenamientos/tomar",
    response_model=ProcesoReentrenamientoResponse,
    responses={204: {"description": "No hay procesos pendientes."}},
    summary="Tomar el reentrenamiento pendiente más antiguo (AJF-14, RF-71)",
)
def tomar_reentrenamiento(db: Session = Depends(get_db_sistema)):
    proceso = _procesar(db).tomar()
    if proceso is None:
        return Response(status_code=204)
    return ProcesoReentrenamientoResponse.from_entity(proceso)


@router.patch(
    "/reentrenamientos/{id_proceso}",
    response_model=ProcesoReentrenamientoResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Latido o cierre de un reentrenamiento (AJF-14, RF-71)",
)
def actualizar_reentrenamiento(id_proceso: uuid.UUID, dto: ActualizarProcesoDTO,
                               db: Session = Depends(get_db_sistema)) -> ProcesoReentrenamientoResponse:
    proceso = _procesar(db).actualizar(id_proceso, ActualizacionProceso(**dto.model_dump()))
    return ProcesoReentrenamientoResponse.from_entity(proceso)

