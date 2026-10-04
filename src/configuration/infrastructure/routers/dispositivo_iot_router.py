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
  POST   /configuracion/dispositivos-iot/{id}/configuraciones/{id_config}/reintentar — Reintentar PENDIENTE/NO_CONF (U)
  PATCH  /configuracion/dispositivos-iot/{id}/configuraciones/{id_config}/cancelar   — Cancelar PENDIENTE/NO_CONF (U)

RF-21 — Gateway Edge (N:1):
  PATCH  /configuracion/dispositivos-iot/{id}/gateway         — Asignar o quitar su Edge (U)

RF-23 — Credencial MQTT del Gateway Edge (TC-M09-250/251):
  POST   /configuracion/dispositivos-iot/{id}/credencial-mqtt — Emitir o rotar (U)
  GET    /configuracion/dispositivos-iot/{id}/credencial-mqtt — Estado (R)
  DELETE /configuracion/dispositivos-iot/{id}/credencial-mqtt — Revocar (D)

RBAC: id_recurso=11 (dispositivos_iot).
  Admin: C=1, R=2, U=3, D=4  |  Prod: R=2  |  Ing: C=1, R=2, U=3, D=4
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.dispositivos_iot.configurar_remotamente_use_case import (
    CancelarConfiguracionUseCase,
    ConfigurarRemotamenteUseCase,
    ConsultarConfiguracionesUseCase,
    ReintentarConfiguracionUseCase,
)
from src.configuration.application.use_cases.dispositivos_iot.consultar_dispositivos_iot_use_case import ConsultarDispositivosIotUseCase
from src.configuration.application.use_cases.dispositivos_iot.credencial_mqtt_use_case import (
    ConsultarCredencialMqttUseCase,
    EmitirCredencialMqttUseCase,
    RevocarCredencialMqttUseCase,
)
from src.configuration.application.use_cases.dispositivos_iot.desactivar_dispositivo_iot_use_case import DesactivarDispositivoIotUseCase
from src.configuration.application.use_cases.dispositivos_iot.gateway_edge_use_case import AsignarGatewayEdgeUseCase
from src.configuration.application.use_cases.dispositivos_iot.registrar_dispositivo_iot_use_case import RegistrarDispositivoIotUseCase
from src.configuration.application.use_cases.dispositivos_iot.registrar_sensor_use_case import ConsultarSensoresUseCase, RegistrarSensorUseCase
from src.configuration.infrastructure.adapters.bitacora_iot_m03_adapter import BitacoraIotM03Adapter
from src.configuration.infrastructure.adapters.mqtt_http_adapter import MqttHttpAdapter
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.configuration.infrastructure.dto.asignar_gateway_edge_dto import AsignarGatewayEdgeDTO
from src.configuration.infrastructure.dto.registrar_dispositivo_iot_dto import RegistrarDispositivoIotDTO
from src.configuration.infrastructure.dto.registrar_sensor_dto import RegistrarSensorDTO
from src.configuration.infrastructure.repositories.auditoria_dispositivo_iot_repository import SqlAlchemyAuditoriaDispositivoIotRepository
from src.configuration.infrastructure.repositories.configuracion_remota_repository import SqlAlchemyConfiguracionRemotaRepository
from src.configuration.infrastructure.repositories.dispositivo_iot_repository import SqlAlchemyDispositivoIotRepository
from src.configuration.infrastructure.repositories.infraestructura_repository import SqlAlchemyInfraestructuraRepository
from src.configuration.infrastructure.repositories.sensor_repository import SqlAlchemySensorRepository
from src.configuration.infrastructure.repositories.tipo_dispositivo_iot_repository import SqlAlchemyTipoDispositivoIotRepository
from src.configuration.infrastructure.schema.configuracion_remota_schema import ConfiguracionRemotaResponse, ListaConfiguracionesRemotasResponse
from src.configuration.infrastructure.schema.credencial_mqtt_schema import CredencialMqttResponse, EstadoCredencialMqttResponse
from src.configuration.infrastructure.schema.dispositivo_iot_schema import DispositivoIotResponse, ListaDispositivosIotResponse
from src.configuration.infrastructure.schema.sensor_schema import ListaSensoresResponse, SensorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.errors import GatewayTimeoutError
from src.shared.rate_limit import rate_limit
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/dispositivos-iot", tags=["Configuración - Dispositivos IoT"])

_RECURSO = 11  # modulo1.recursos: 'dispositivos_iot'
# INC-M09-21-G125-02: sin este límite, una ráfaga de registros con seriales
# secuenciales (enumeración masiva) se procesaba entera sin ningún 429.
_LIMITE_REGISTRO = rate_limit(10, 60, alcance="dispositivos_iot_registrar")
# Cada emisión rota la clave y desconecta al Gateway Edge: no tiene sentido en ráfaga.
_LIMITE_CREDENCIAL = rate_limit(10, 60, alcance="dispositivos_iot_credencial_mqtt")


# ── RF-21: Registrar dispositivo ─────────────────────────────────────────────

@router.post(
    "",
    response_model=DispositivoIotResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1)), Depends(_LIMITE_REGISTRO)],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
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
        tipo_repo=SqlAlchemyTipoDispositivoIotRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaDispositivoIotRepository(db),
        mqtt_port=MqttHttpAdapter(),
        bitacora=BitacoraIotM03Adapter(db),
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
    dispositivos = use_case.listar(
        usuario_actual,
        solo_activos=solo_activos,
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario, usuario_actual.id_rol
        ),
    )
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
    dispositivo = use_case.obtener(
        id_dispositivo_iot,
        usuario_actual,
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario, usuario_actual.id_rol
        ),
    )
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
        mqtt_port=MqttHttpAdapter(),
        bitacora=BitacoraIotM03Adapter(db),
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


def _respuesta_envio(config, mensaje: str) -> JSONResponse:
    """APLICADA → 200, PENDIENTE → 202, NO_CONF → 504 (RF-23)."""
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
        tipo_repo=SqlAlchemyTipoDispositivoIotRepository(db),
        mqtt_port=MqttHttpAdapter(),
    )
    config, mensaje = use_case.execute(
        id_dispositivo_iot,
        dto,
        usuario_actual,
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario, usuario_actual.id_rol
        ),
    )
    return _respuesta_envio(config, mensaje)


# ── RF-23: Historial de configuraciones ──────────────────────────────────────

@router.get(
    "/{id_dispositivo_iot}/configuraciones",
    response_model=ListaConfiguracionesRemotasResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
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
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
    )
    configs = use_case.listar_por_dispositivo(
        id_dispositivo_iot,
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario, usuario_actual.id_rol
        ),
    )
    items = [ConfiguracionRemotaResponse.from_entity(c) for c in configs]
    return ListaConfiguracionesRemotasResponse(total=len(items), items=items)


# ── RF-23: Reintentar o cancelar una configuración sin aplicar ───────────────

@router.post(
    "/{id_dispositivo_iot}/configuraciones/{id_configuracion_remota}/reintentar",
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        200: {"model": ConfiguracionRemotaResponse},
        202: {"model": ConfiguracionRemotaResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Reintentar una configuración PENDIENTE o NO_CONF (RF-23)",
)
def reintentar_configuracion(
    id_dispositivo_iot: int,
    id_configuracion_remota: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> JSONResponse:
    use_case = ReintentarConfiguracionUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        config_repo=SqlAlchemyConfiguracionRemotaRepository(db),
        mqtt_port=MqttHttpAdapter(),
        bitacora=BitacoraIotM03Adapter(db),
    )
    config, mensaje = use_case.execute(
        id_dispositivo_iot,
        id_configuracion_remota,
        usuario_actual,
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario, usuario_actual.id_rol
        ),
    )
    return _respuesta_envio(config, mensaje)


@router.patch(
    "/{id_dispositivo_iot}/configuraciones/{id_configuracion_remota}/cancelar",
    response_model=ConfiguracionRemotaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Cancelar una configuración PENDIENTE o NO_CONF (RF-23)",
)
def cancelar_configuracion(
    id_dispositivo_iot: int,
    id_configuracion_remota: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ConfiguracionRemotaResponse:
    use_case = CancelarConfiguracionUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        config_repo=SqlAlchemyConfiguracionRemotaRepository(db),
        bitacora=BitacoraIotM03Adapter(db),
    )
    config = use_case.execute(
        id_dispositivo_iot,
        id_configuracion_remota,
        usuario_actual,
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario, usuario_actual.id_rol
        ),
    )
    return ConfiguracionRemotaResponse.from_entity(config)


# ── RF-21: Gateway Edge del dispositivo (N:1) ────────────────────────────────

@router.patch(
    "/{id_dispositivo_iot}/gateway",
    response_model=DispositivoIotResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Asignar, cambiar o quitar el Gateway Edge de un dispositivo IoT (RF-21)",
)
def asignar_gateway_edge(
    id_dispositivo_iot: int,
    dto: AsignarGatewayEdgeDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> DispositivoIotResponse:
    use_case = AsignarGatewayEdgeUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        infra_repo=SqlAlchemyInfraestructuraRepository(db),
        tipo_repo=SqlAlchemyTipoDispositivoIotRepository(db),
        mqtt_port=MqttHttpAdapter(),
        bitacora=BitacoraIotM03Adapter(db),
    )
    dispositivo = use_case.execute(
        id_dispositivo_iot, dto, usuario_actual, ids_fincas_permitidas=_alcance(db, usuario_actual)
    )
    return DispositivoIotResponse.from_entity(dispositivo)


# ── RF-23: Credencial MQTT del Gateway Edge (TC-M09-250/251) ─────────────────

def _alcance(db: Session, usuario_actual: UsuarioActual) -> list[int] | None:
    return AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
        usuario_actual.id_usuario, usuario_actual.id_rol
    )


@router.post(
    "/{id_dispositivo_iot}/credencial-mqtt",
    response_model=CredencialMqttResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 3)), Depends(_LIMITE_CREDENCIAL)],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Emitir o rotar la credencial MQTT de un Gateway Edge (RF-23, TC-M09-250/251)",
)
def emitir_credencial_mqtt(
    id_dispositivo_iot: int,
    response: Response,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> CredencialMqttResponse:
    use_case = EmitirCredencialMqttUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        mqtt_port=MqttHttpAdapter(),
        bitacora=BitacoraIotM03Adapter(db),
    )
    credencial = use_case.execute(
        id_dispositivo_iot, usuario_actual, ids_fincas_permitidas=_alcance(db, usuario_actual)
    )
    # La contraseña se muestra una sola vez: que ningún proxy ni el navegador la guarde.
    response.headers["Cache-Control"] = "no-store"
    return CredencialMqttResponse.from_entity(credencial)


@router.get(
    "/{id_dispositivo_iot}/credencial-mqtt",
    response_model=EstadoCredencialMqttResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Estado de la credencial MQTT de un Gateway Edge (RF-23)",
)
def consultar_credencial_mqtt(
    id_dispositivo_iot: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EstadoCredencialMqttResponse:
    use_case = ConsultarCredencialMqttUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        mqtt_port=MqttHttpAdapter(),
    )
    estado = use_case.execute(id_dispositivo_iot, ids_fincas_permitidas=_alcance(db, usuario_actual))
    return EstadoCredencialMqttResponse.from_entity(estado)


@router.delete(
    "/{id_dispositivo_iot}/credencial-mqtt",
    status_code=204,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Revocar la credencial MQTT de un Gateway Edge (RF-23, TC-M09-250/251)",
)
def revocar_credencial_mqtt(
    id_dispositivo_iot: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> Response:
    use_case = RevocarCredencialMqttUseCase(
        db=db,
        dispositivo_repo=SqlAlchemyDispositivoIotRepository(db),
        mqtt_port=MqttHttpAdapter(),
        bitacora=BitacoraIotM03Adapter(db),
    )
    use_case.execute(id_dispositivo_iot, usuario_actual, ids_fincas_permitidas=_alcance(db, usuario_actual))
    return Response(status_code=204)
