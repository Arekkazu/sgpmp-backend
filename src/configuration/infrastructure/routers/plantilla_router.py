"""Router FastAPI para plantillas de configuración (`/configuracion/plantillas`).

  A) GET  /configuracion/plantillas             — Listar plantillas (RF-30)
  B) POST /configuracion/plantillas             — Crear plantilla (RF-31)
  C) GET  /configuracion/plantillas/{id}        — Detalle de plantilla (RF-30)
  D) POST /configuracion/plantillas/{id}/aplicar — Aplicar plantilla (RF-32)
  E) GET  /configuracion/plantillas/historial   — Historial de aplicaciones (RF-30)

  Autorización RBAC: recurso = id_recurso 28
    C=1 (crear), R=2 (leer), E=5 (aplicar)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.plantillas.aplicar_plantilla_use_case import AplicarPlantillaUseCase
from src.configuration.application.use_cases.plantillas.consultar_plantillas_use_case import ConsultarPlantillasUseCase
from src.configuration.application.use_cases.plantillas.registrar_plantilla_use_case import RegistrarPlantillaUseCase
from src.configuration.infrastructure.dto.aplicar_plantilla_dto import AplicarPlantillaDTO
from src.configuration.infrastructure.dto.registrar_plantilla_dto import RegistrarPlantillaDTO
from src.configuration.infrastructure.repositories.aplicacion_plantilla_repository import SqlAlchemyAplicacionPlantillaRepository
from src.configuration.infrastructure.repositories.auditoria_plantilla_repository import SqlAlchemyAuditoriaPlantillaRepository
from src.configuration.infrastructure.repositories.ciclo_biologico_repository import SqlAlchemyCicloBiologicoRepository
from src.configuration.infrastructure.repositories.especie_patologia_repository import SqlAlchemyEspeciePatologiaRepository
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.configuration.infrastructure.repositories.metrica_produccion_repository import SqlAlchemyMetricaProduccionRepository
from src.configuration.infrastructure.repositories.plantilla_repository import SqlAlchemyPlantillaRepository
from src.configuration.infrastructure.repositories.umbral_ambiental_repository import SqlAlchemyUmbralAmbientalRepository
from src.configuration.infrastructure.schema.plantilla_schema import (
    AplicacionPlantillaResponse,
    HistorialAplicacionesResponse,
    PlantillaResponse,
    PlantillasListResponse,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/plantillas", tags=["Configuración - Plantillas"])

_RECURSO = 28


@router.get(
    "/historial",
    response_model=HistorialAplicacionesResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Historial de aplicaciones de plantillas (Flujo E)",
)
def listar_historial(
    db: Session = Depends(get_db),
) -> HistorialAplicacionesResponse:
    use_case = ConsultarPlantillasUseCase(
        db=db,
        plantilla_repo=SqlAlchemyPlantillaRepository(db),
        aplicacion_repo=SqlAlchemyAplicacionPlantillaRepository(db),
    )
    items = [AplicacionPlantillaResponse.model_validate(a) for a in use_case.listar_historial()]
    return HistorialAplicacionesResponse(total=len(items), items=items)


@router.get(
    "",
    response_model=PlantillasListResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar plantillas disponibles (Flujo A — RF-30)",
)
def listar_plantillas(
    db: Session = Depends(get_db),
) -> PlantillasListResponse:
    use_case = ConsultarPlantillasUseCase(
        db=db,
        plantilla_repo=SqlAlchemyPlantillaRepository(db),
        aplicacion_repo=SqlAlchemyAplicacionPlantillaRepository(db),
    )
    items = [PlantillaResponse.model_validate(p) for p in use_case.listar_plantillas()]
    return PlantillasListResponse(total=len(items), items=items)


@router.post(
    "",
    response_model=PlantillaResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Crear plantilla de configuración (Flujo B — RF-31)",
)
def registrar_plantilla(
    dto: RegistrarPlantillaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PlantillaResponse:
    use_case = RegistrarPlantillaUseCase(
        db=db,
        plantilla_repo=SqlAlchemyPlantillaRepository(db),
        especie_repo=SqlAlchemyEspecieRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaPlantillaRepository(db),
    )
    plantilla = use_case.execute(dto, usuario_actual)
    return PlantillaResponse.model_validate(plantilla)


@router.get(
    "/{id_plantilla}",
    response_model=PlantillaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Detalle de plantilla (Flujo C — RF-30)",
)
def detalle_plantilla(
    id_plantilla: int,
    db: Session = Depends(get_db),
) -> PlantillaResponse:
    use_case = ConsultarPlantillasUseCase(
        db=db,
        plantilla_repo=SqlAlchemyPlantillaRepository(db),
        aplicacion_repo=SqlAlchemyAplicacionPlantillaRepository(db),
    )
    from src.shared.errors import NotFoundError
    plantilla = use_case.obtener_plantilla(id_plantilla)
    if plantilla is None:
        raise NotFoundError(
            code="PLANTILLA_NO_ENCONTRADA",
            message=f"No existe la plantilla con id {id_plantilla}.",
        )
    return PlantillaResponse.model_validate(plantilla)


@router.post(
    "/{id_plantilla}/aplicar",
    response_model=AplicacionPlantillaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Aplicar plantilla a especie destino (Flujo D — RF-32)",
)
def aplicar_plantilla(
    id_plantilla: int,
    dto: AplicarPlantillaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AplicacionPlantillaResponse:
    use_case = AplicarPlantillaUseCase(
        db=db,
        plantilla_repo=SqlAlchemyPlantillaRepository(db),
        especie_repo=SqlAlchemyEspecieRepository(db),
        ciclo_repo=SqlAlchemyCicloBiologicoRepository(db),
        metrica_repo=SqlAlchemyMetricaProduccionRepository(db),
        umbral_repo=SqlAlchemyUmbralAmbientalRepository(db),
        patologia_repo=SqlAlchemyEspeciePatologiaRepository(db),
        aplicacion_repo=SqlAlchemyAplicacionPlantillaRepository(db),
    )
    aplicacion = use_case.execute(id_plantilla, dto, usuario_actual)
    return AplicacionPlantillaResponse.model_validate(aplicacion)
