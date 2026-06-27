"""Router FastAPI para sensores (`/configuracion/sensores`).

RF-22 — CU05 Flujo B:
  POST  /configuracion/sensores/{id}/asociar         — Asociar sensor a área productiva
  GET   /configuracion/sensores/{id}/asociaciones    — Historial de asociaciones

RF-24 — CU05 Flujo D:
  POST  /configuracion/sensores/{id}/calibrar        — Registrar calibración
  GET   /configuracion/sensores/{id}/calibraciones   — Historial de calibraciones

RBAC: id_recurso=12 (sensores).
  Admin: C=1, R=2, U=3  |  Prod: R=2  |  Vet: R=2  |  Ing: C=1, R=2, U=3
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.sensores.asociar_sensor_area_use_case import AsociarSensorAreaUseCase, ConsultarAsociacionesUseCase
from src.configuration.application.use_cases.sensores.registrar_calibracion_use_case import ConsultarCalibracionesUseCase, RegistrarCalibracionUseCase
from src.configuration.infrastructure.dto.asociar_sensor_area_dto import AsociarSensorAreaDTO
from src.configuration.infrastructure.dto.registrar_calibracion_dto import RegistrarCalibracionDTO
from src.configuration.infrastructure.repositories.auditoria_sensor_area_repository import SqlAlchemyAuditoriaSensorAreaRepository
from src.configuration.infrastructure.repositories.calibracion_repository import SqlAlchemyCalibracionRepository
from src.configuration.infrastructure.repositories.dispositivo_iot_repository import SqlAlchemyDispositivoIotRepository
from src.configuration.infrastructure.repositories.infraestructura_repository import SqlAlchemyInfraestructuraRepository
from src.configuration.infrastructure.repositories.sensor_area_repository import SqlAlchemySensorAreaRepository
from src.configuration.infrastructure.repositories.sensor_repository import SqlAlchemySensorRepository
from src.configuration.infrastructure.schema.calibracion_schema import CalibracionResponse, ListaCalibracionesResponse
from src.configuration.infrastructure.schema.sensor_area_schema import ListaSensorAreasResponse, SensorAreaResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/sensores", tags=["Configuración - Sensores"])

_RECURSO = 12  # modulo1.recursos: 'sensores'


# ── RF-22: Asociar sensor a área productiva ───────────────────────────────────

@router.post(
    "/{id_sensor}/asociar",
    response_model=SensorAreaResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Asociar sensor a área productiva (RF-22 Flujo B)",
)
def asociar_sensor_area(
    id_sensor: int,
    dto: AsociarSensorAreaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> SensorAreaResponse:
    use_case = AsociarSensorAreaUseCase(
        db=db,
        sensor_repo=SqlAlchemySensorRepository(db),
        sensor_area_repo=SqlAlchemySensorAreaRepository(db),
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaSensorAreaRepository(db),
    )
    asociacion = use_case.execute(id_sensor, dto, usuario_actual)
    return SensorAreaResponse.from_entity(asociacion)


# ── RF-22: Historial de asociaciones del sensor ───────────────────────────────

@router.get(
    "/{id_sensor}/asociaciones",
    response_model=ListaSensorAreasResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Historial de asociaciones sensor-área (RF-22)",
)
def listar_asociaciones(
    id_sensor: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaSensorAreasResponse:
    use_case = ConsultarAsociacionesUseCase(
        db=db,
        sensor_area_repo=SqlAlchemySensorAreaRepository(db),
    )
    asociaciones = use_case.listar_por_sensor(id_sensor)
    items = [SensorAreaResponse.from_entity(a) for a in asociaciones]
    return ListaSensorAreasResponse(total=len(items), items=items)


# ── RF-24: Registrar calibración de sensor ────────────────────────────────────

@router.post(
    "/{id_sensor}/calibrar",
    response_model=CalibracionResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar calibración de sensor (RF-24 Flujo D)",
)
def registrar_calibracion(
    id_sensor: int,
    dto: RegistrarCalibracionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> CalibracionResponse:
    use_case = RegistrarCalibracionUseCase(
        db=db,
        sensor_repo=SqlAlchemySensorRepository(db),
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        sensor_area_repo=SqlAlchemySensorAreaRepository(db),
        calibracion_repo=SqlAlchemyCalibracionRepository(db),
    )
    calibracion = use_case.execute(id_sensor, dto, usuario_actual)
    return CalibracionResponse.from_entity(calibracion)


# ── RF-24: Historial de calibraciones del sensor ──────────────────────────────

@router.get(
    "/{id_sensor}/calibraciones",
    response_model=ListaCalibracionesResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Historial de calibraciones de sensor (RF-24)",
)
def listar_calibraciones(
    id_sensor: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaCalibracionesResponse:
    use_case = ConsultarCalibracionesUseCase(
        db=db,
        calibracion_repo=SqlAlchemyCalibracionRepository(db),
    )
    calibraciones = use_case.listar_por_sensor(id_sensor)
    items = [CalibracionResponse.from_entity(c) for c in calibraciones]
    return ListaCalibracionesResponse(total=len(items), items=items)
