"""Router FastAPI para dispositivos IoT (`/configuracion/dispositivos-iot`).

RF-21 — CU05 Flujos A, E:
  POST   /configuracion/dispositivos-iot                  — Registrar dispositivo
  GET    /configuracion/dispositivos-iot                  — Listar dispositivos
  GET    /configuracion/dispositivos-iot/{id}             — Detalle dispositivo
  PATCH  /configuracion/dispositivos-iot/{id}/desactivar  — Desactivar

RF-22 — Sensores (precondición):
  POST   /configuracion/dispositivos-iot/{id}/sensores    — Registrar sensor
  GET    /configuracion/dispositivos-iot/{id}/sensores    — Listar sensores

RF-23 — CU05 Flujo C:
  POST   /configuracion/dispositivos-iot/{id}/configurar   — Configurar remotamente
  GET    /configuracion/dispositivos-iot/{id}/configuraciones — Historial de configuraciones

RBAC: id_recurso=11 (dispositivos_iot).
  Admin: C=1, R=2, U=3, D=4  |  Prod: R=2  |  Ing: C=1, R=2, U=3, D=4
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.dispositivos_iot.configurar_remotamente_use_case import ConfigurarRemotamenteUseCase, ConsultarConfiguracionesUseCase
from src.configuration.application.use_cases.dispositivos_iot.consultar_dispositivos_iot_use_case import ConsultarDispositivosIotUseCase
from src.configuration.application.use_cases.dispositivos_iot.desactivar_dispositivo_iot_use_case import DesactivarDispositivoIotUseCase
from src.configuration.application.use_cases.dispositivos_iot.registrar_dispositivo_iot_use_case import RegistrarDispositivoIotUseCase
from src.configuration.application.use_cases.dispositivos_iot.registrar_sensor_use_case import ConsultarSensoresUseCase, RegistrarSensorUseCase
from src.configuration.infrastructure.adapters.mqtt_http_adapter import MqttHttpAdapter
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.configuration.infrastructure.dto.registrar_dispositivo_iot_dto import RegistrarDispositivoIotDTO
from src.configuration.infrastructure.dto.registrar_sensor_dto import RegistrarSensorDTO
from src.configuration.infrastructure.repositories.auditoria_dispositivo_iot_repository import SqlAlchemyAuditoriaDispositivoIotRepository
from src.configuration.infrastructure.repositories.configuracion_remota_repository import SqlAlchemyConfiguracionRemotaRepository
from src.configuration.infrastructure.repositories.dispositivo_iot_repository import SqlAlchemyDispositivoIotRepository
from src.configuration.infrastructure.repositories.infraestructura_repository import SqlAlchemyInfraestructuraRepository
from src.configuration.infrastructure.repositories.sensor_repository import SqlAlchemySensorRepository
from src.configuration.infrastructure.schema.configuracion_remota_schema import ConfiguracionRemotaResponse, ListaConfiguracionesRemotasResponse
from src.configuration.infrastructure.schema.dispositivo_iot_schema import DispositivoIotResponse, ListaDispositivosIotResponse
from src.configuration.infrastructure.schema.sensor_schema import ListaSensoresResponse, SensorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.errors import GatewayTimeoutError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/dispositivos-iot", tags=["Configuración - Dispositivos IoT"])

_RECURSO = 11  # modulo1.recursos: 'dispositivos_iot'


# ── RF-21: Registrar dispositivo ─────────────────────────────────────────────

@router.post(
    "",
    response_model=DispositivoIotResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar dispositivo IoT (RF-21 Flujo A)",
)
def registrar_dispositivo_iot(
    dto: RegistrarDispositivoIotDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DispositivoIotResponse:
    use_case = RegistrarDispositivoIotUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaDispositivoIotRepository(db),
    )
    dispositivo = use_case.execute(dto, usuario_actual)
    return DispositivoIotResponse.from_entity(dispositivo)


# ── RF-21: Listar dispositivos ────────────────────────────────────────────────

@router.get(
    "",
    response_model=ListaDispositivosIotResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar dispositivos IoT (RF-21 Flujo E)",
)
def listar_dispositivos_iot(
    solo_activos: bool = Query(False, description="Si true, solo dispositivos activos."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaDispositivosIotResponse:
    use_case = ConsultarDispositivosIotUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaDispositivoIotRepository(db),
    )
    dispositivos = use_case.listar(usuario_actual, solo_activos=solo_activos)
    items = [DispositivoIotResponse.from_entity(d) for d in dispositivos]
    return ListaDispositivosIotResponse(total=len(items), items=items)


# ── RF-21: Detalle de dispositivo ─────────────────────────────────────────────

@router.get(
    "/{id_dispositivo_iot}",
    response_model=DispositivoIotResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Detalle de dispositivo IoT (RF-21)",
)
def obtener_dispositivo_iot(
    id_dispositivo_iot: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DispositivoIotResponse:
    use_case = ConsultarDispositivosIotUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaDispositivoIotRepository(db),
    )
    dispositivo = use_case.obtener(id_dispositivo_iot, usuario_actual)
    return DispositivoIotResponse.from_entity(dispositivo)


# ── RF-21: Desactivar dispositivo ────────────────────────────────────────────

@router.patch(
    "/{id_dispositivo_iot}/desactivar",
    response_model=DispositivoIotResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Desactivar dispositivo IoT (RF-21)",
)
def desactivar_dispositivo_iot(
    id_dispositivo_iot: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DispositivoIotResponse:
    use_case = DesactivarDispositivoIotUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        config_repo=SqlAlchemyConfiguracionRemotaRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaDispositivoIotRepository(db),
    )
    dispositivo = use_case.execute(id_dispositivo_iot, usuario_actual)
    return DispositivoIotResponse.from_entity(dispositivo)


# ── RF-22 (precondición): Registrar sensor ────────────────────────────────────

@router.post(
    "/{id_dispositivo_iot}/sensores",
    response_model=SensorResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Registrar sensor en dispositivo IoT",
)
def registrar_sensor(
    id_dispositivo_iot: int,
    dto: RegistrarSensorDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> SensorResponse:
    use_case = RegistrarSensorUseCase(
        db=db,
        sensor_repo=SqlAlchemySensorRepository(db),
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
    )
    sensor = use_case.execute(id_dispositivo_iot, dto, usuario_actual)
    return SensorResponse.from_entity(sensor)


# ── RF-22: Listar sensores del dispositivo ────────────────────────────────────

@router.get(
    "/{id_dispositivo_iot}/sensores",
    response_model=ListaSensoresResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar sensores de un dispositivo IoT (RF-22)",
)
def listar_sensores(
    id_dispositivo_iot: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaSensoresResponse:
    use_case = ConsultarSensoresUseCase(db=db, sensor_repo=SqlAlchemySensorRepository(db))
    sensores = use_case.listar_por_dispositivo(id_dispositivo_iot)
    items = [SensorResponse.from_entity(s) for s in sensores]
    return ListaSensoresResponse(total=len(items), items=items)


# ── RF-23: Configurar dispositivo remotamente ────────────────────────────────

_ESTADO_A_HTTP = {"APLICADA": 200, "PENDIENTE": 202}


@router.post(
    "/{id_dispositivo_iot}/configurar",
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        200: {"model": ConfiguracionRemotaResponse},
        202: {"model": ConfiguracionRemotaResponse},
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Configurar dispositivo IoT remotamente (RF-23 Flujo C)",
)
def configurar_remotamente(
    id_dispositivo_iot: int,
    dto: ConfigurarRemotamenteDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> JSONResponse:
    use_case = ConfigurarRemotamenteUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        config_repo=SqlAlchemyConfiguracionRemotaRepository(db),
        mqtt_port=MqttHttpAdapter(),
    )
    config, mensaje = use_case.execute(id_dispositivo_iot, dto, usuario_actual)

    if config.estado == "NO_CONF":
        raise GatewayTimeoutError(
            code="CONFIGURACION_NO_CONFIRMADA",
            message=mensaje,
        )

    response = ConfiguracionRemotaResponse.from_entity(config, mensaje=mensaje)
    return JSONResponse(
        status_code=_ESTADO_A_HTTP[config.estado],
        content=response.model_dump(mode="json"),
    )


# ── RF-23: Historial de configuraciones ──────────────────────────────────────

@router.get(
    "/{id_dispositivo_iot}/configuraciones",
    response_model=ListaConfiguracionesRemotasResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Historial de configuraciones remotas (RF-23)",
)
def listar_configuraciones(
    id_dispositivo_iot: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaConfiguracionesRemotasResponse:
    use_case = ConsultarConfiguracionesUseCase(
        db=db,
        config_repo=SqlAlchemyConfiguracionRemotaRepository(db),
    )
    configs = use_case.listar_por_dispositivo(id_dispositivo_iot)
    items = [ConfiguracionRemotaResponse.from_entity(c) for c in configs]
    return ListaConfiguracionesRemotasResponse(total=len(items), items=items)
