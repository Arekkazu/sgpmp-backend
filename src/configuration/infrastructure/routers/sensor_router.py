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
from src.configuration.application.use_cases.sensores.registrar_calibracion_use_case import (
    ConsultarCalibracionesUseCase,
    RegistrarCalibracionUseCase,
    auditar_rechazo_calibracion,
)
from src.configuration.infrastructure.adapters.asociacion_sensor_activo_m02_adapter import AsociacionSensorActivoM02Adapter
from src.configuration.infrastructure.dto.asociar_sensor_area_dto import AsociarSensorAreaDTO
from src.configuration.infrastructure.dto.registrar_calibracion_dto import RegistrarCalibracionDTO
from src.configuration.infrastructure.repositories.auditoria_calibracion_repository import SqlAlchemyAuditoriaCalibracionRepository
from src.configuration.infrastructure.repositories.auditoria_sensor_area_repository import SqlAlchemyAuditoriaSensorAreaRepository
from src.configuration.infrastructure.repositories.calibracion_repository import SqlAlchemyCalibracionRepository
from src.configuration.infrastructure.repositories.dispositivo_iot_repository import SqlAlchemyDispositivoIotRepository
from src.configuration.infrastructure.repositories.infraestructura_repository import SqlAlchemyInfraestructuraRepository
from src.configuration.infrastructure.repositories.rango_calibracion_repository import SqlAlchemyRangoCalibracionRepository
from src.configuration.infrastructure.repositories.sensor_area_repository import SqlAlchemySensorAreaRepository
from src.configuration.infrastructure.repositories.sensor_repository import SqlAlchemySensorRepository
from src.configuration.infrastructure.schema.calibracion_schema import (
    CalibracionResponse,
    ListaCalibracionesResponse,
    ListaRangosCalibracionResponse,
    RangoCalibracionResponse,
)
from src.configuration.infrastructure.schema.sensor_area_schema import (
    AsociarSensorAreaResponse,
    ListaSensorAreasResponse,
    SensorAreaResponse,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.shared.database import get_db
from src.shared.errors import AuthorizationError
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/sensores", tags=["Configuración - Sensores"])

_RECURSO = 12  # modulo1.recursos: 'sensores'


# ── RF-22: Asociar sensor a área productiva ───────────────────────────────────

@router.post(
    "/{id_sensor}/asociar",
    response_model=AsociarSensorAreaResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Asociar sensor a área productiva (RF-22 Flujo B). 409 distingue por error_code: "
            "ASOCIACION_DUPLICADA (misma área) vs. REASIGNACION_REQUIERE_CONFIRMACION "
            "(área distinta; reenviar con confirmar=true para completar la reasignación).",
)
def asociar_sensor_area(
    id_sensor: int,
    dto: AsociarSensorAreaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AsociarSensorAreaResponse:
    use_case = AsociarSensorAreaUseCase(
        db=db,
        sensor_repo=SqlAlchemySensorRepository(db),
        sensor_area_repo=SqlAlchemySensorAreaRepository(db),
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaSensorAreaRepository(db),
        asociacion_sensor_activo_port=AsociacionSensorActivoM02Adapter(db),
    )
    asociacion, superadas = use_case.execute(id_sensor, dto, usuario_actual)
    return AsociarSensorAreaResponse.from_resultado(asociacion, superadas)


# ── RF-22: Historial de asociaciones del sensor ───────────────────────────────

@router.get(
    "/{id_sensor}/asociaciones",
    response_model=ListaSensorAreasResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Historial de asociaciones sensor-área (RF-22)",
)
def listar_asociaciones(
    id_sensor: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaSensorAreasResponse:
    ids_permitidas = AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
        usuario_actual.id_usuario, usuario_actual.id_rol
    )
    use_case = ConsultarAsociacionesUseCase(
        db=db,
        sensor_area_repo=SqlAlchemySensorAreaRepository(db),
        sensor_repo=SqlAlchemySensorRepository(db),
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
    )
    asociaciones = use_case.listar_por_sensor(id_sensor, ids_fincas_permitidas=ids_permitidas)
    items = [SensorAreaResponse.from_entity(a) for a in asociaciones]
    return ListaSensorAreasResponse(total=len(items), items=items)


# ── RF-24: Registrar calibración de sensor ────────────────────────────────────

def _alcance(db: Session, usuario_actual: UsuarioActual) -> list[int] | None:
    return AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
        usuario_actual.id_usuario, usuario_actual.id_rol
    )


def _permiso_calibrar_auditado(
    id_sensor: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> None:
    """La misma compuerta RBAC de siempre; RF-24 v1.1 (RFC-006) pide además auditar el 403."""
    try:
        require_permission(
            _RECURSO, 1,
            mensaje_denegado=(
                "Acceso denegado: La calibración de sensores es una función crítica restringida "
                "exclusivamente al Ingeniero de Campo o al Administrador."
            ),
        )(db=db, usuario_actual=usuario_actual)
    except AuthorizationError as exc:
        auditar_rechazo_calibracion(
            db,
            SqlAlchemyEventoRepository(db),
            id_usuario=usuario_actual.id_usuario,
            id_sensor=id_sensor,
            error=exc,
        )
        raise


@router.post(
    "/{id_sensor}/calibrar",
    response_model=CalibracionResponse,
    status_code=201,
    dependencies=[Depends(_permiso_calibrar_auditado)],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
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
        rango_repo=SqlAlchemyRangoCalibracionRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaCalibracionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
    )
    calibracion = use_case.execute(
        id_sensor, dto, usuario_actual, ids_fincas_permitidas=_alcance(db, usuario_actual)
    )
    return CalibracionResponse.from_entity(calibracion)


# ── RF-24: Catálogo de rangos de calibración por tipo de sensor ────────────────

@router.get(
    "/rangos-calibracion",
    response_model=ListaRangosCalibracionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar rangos de seguridad de calibración por tipo de sensor (RF-24)",
)
def listar_rangos_calibracion(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaRangosCalibracionResponse:
    rangos = SqlAlchemyRangoCalibracionRepository(db).listar()
    items = [RangoCalibracionResponse.from_entity(r) for r in rangos]
    return ListaRangosCalibracionResponse(total=len(items), items=items)


# ── RF-24: Historial de calibraciones del sensor ──────────────────────────────

@router.get(
    "/{id_sensor}/calibraciones",
    response_model=ListaCalibracionesResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
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
        sensor_repo=SqlAlchemySensorRepository(db),
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
    )
    calibraciones = use_case.listar_por_sensor(
        id_sensor, ids_fincas_permitidas=_alcance(db, usuario_actual)
    )
    items = [CalibracionResponse.from_entity(c) for c in calibraciones]
    return ListaCalibracionesResponse(total=len(items), items=items)
