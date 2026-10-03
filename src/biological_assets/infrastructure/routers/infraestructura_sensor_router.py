from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.biological_assets.application.use_cases.gestion.asociar_sensor_infraestructura_use_case import (
    AsociarSensorInfraestructuraUseCase,
)
from src.biological_assets.application.use_cases.gestion.cambiar_estado_asociacion_sensor_use_case import (
    CambiarEstadoAsociacionSensorUseCase,
)
from src.biological_assets.infrastructure.adapters.infraestructura_m09_adapter import InfraestructuraM09Adapter
from src.biological_assets.infrastructure.adapters.sensor_m09_adapter import SensorM09Adapter
from src.biological_assets.infrastructure.dto.asociar_sensor_infraestructura_dto import (
    AsociarSensorInfraestructuraDTO,
)
from src.biological_assets.infrastructure.dto.cambiar_estado_asociacion_sensor_dto import (
    CambiarEstadoAsociacionSensorDTO,
)
from src.biological_assets.infrastructure.rbac_auditoria import require_permission_m02
from src.biological_assets.infrastructure.repositories.asociacion_sensor_activo_repository import (
    SqlAlchemyAsociacionSensorActivoRepository,
)
from src.biological_assets.infrastructure.repositories.bitacora_auditoria_repository import (
    SqlAlchemyBitacoraAuditoriaRepository,
)
from src.biological_assets.infrastructure.schema.activo_biologico_schema import AsociacionSensorActivoResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import get_db
from src.shared.schemas import ErrorResponse

# Mismo recurso RBAC que el resto de CU11 RF-49 (`_RECURSO_SENSOR` en
# activo_biologico_router.py) -- es la misma tabla/agregado
# (asociaciones_activos_sensores), solo cambia si la fila queda anclada a un
# activo o a una infraestructura completa.
_RECURSO_SENSOR = 30
_ROL_PRODUCTOR = 2

router = APIRouter(prefix='/infraestructuras', tags=['Infraestructuras (Sensores IoT)'])


@router.post(
    '/{id_infraestructura}/sensores',
    status_code=201,
    response_model=AsociacionSensorActivoResponse,
    responses={
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Asociar sensor AMBIENTAL a una infraestructura (RF-49 Tipo B, INC-M02-66-G90/#217)',
    dependencies=[Depends(require_permission_m02(_RECURSO_SENSOR, 1, rf_origen='RF49'))],
)
def asociar_sensor_a_infraestructura(
    id_infraestructura: int,
    dto: AsociarSensorInfraestructuraDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AsociacionSensorActivoResponse:
    """Asociación Ambiental Compartida (RF-49 Tipo B): el sensor queda ligado
    a la infraestructura completa (`id_activo_biologico = NULL`), no a un
    activo puntual, y aplica automáticamente a todos los activos que residan
    en ella -- `GET /activos-biologicos/{id_activo}/sensores` la refleja para
    cualquier activo de esta infraestructura."""
    use_case = AsociarSensorInfraestructuraUseCase(
        db=db,
        repo=SqlAlchemyAsociacionSensorActivoRepository(db),
        sensor_port=SensorM09Adapter(db),
        infra_port=InfraestructuraM09Adapter(db),
        bitacora_repo=SqlAlchemyBitacoraAuditoriaRepository(db),
    )
    ids_fincas_permitidas = None
    if usuario_actual.id_rol == _ROL_PRODUCTOR:
        ids_fincas_permitidas = AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario,
            usuario_actual.id_rol,
        )
    resultado = use_case.execute(
        id_infraestructura,
        dto,
        usuario_actual,
        ids_fincas_permitidas=ids_fincas_permitidas,
    )
    return AsociacionSensorActivoResponse(
        id_asociacion_activo_sensor=resultado.id_asociacion_activo_sensor,
        id_activo_biologico=resultado.id_activo_biologico,
        tipo_activo=resultado.tipo_activo,
        tipo_asociacion=resultado.tipo_asociacion,
        dispositivo_iot_id=resultado.dispositivo_iot_id,
        sensor_id=resultado.sensor_id,
        id_infraestructura=resultado.id_infraestructura,
        fecha_inicio=resultado.fecha_inicio,
        fecha_fin=resultado.fecha_fin,
        estado_asociacion=resultado.estado_asociacion,
        motivo=resultado.motivo,
        advertencia=None,
    )


@router.patch(
    '/{id_infraestructura}/sensores/{id_asociacion}',
    response_model=AsociacionSensorActivoResponse,
    status_code=200,
    dependencies=[Depends(require_permission_m02(_RECURSO_SENSOR, 3, rf_origen='RF49'))],
    responses={
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Cambiar estado (activar/desactivar) de una asociación sensor-infraestructura (RF-49 Tipo B, INC-M02-50-G84/#398)',
)
def cambiar_estado_asociacion_sensor_infraestructura(
    id_infraestructura: int,
    id_asociacion: int,
    dto: CambiarEstadoAsociacionSensorDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AsociacionSensorActivoResponse:
    """RF-49 Regla 5 (`ACTIVA → INACTIVA → ACTIVA`) no hace excepción por tipo
    de asociación: las asociaciones AMBIENTALES (Tipo B, ancladas a la
    infraestructura completa) también deben poder desactivarse/reactivarse,
    igual que las DIRECTA/POBLACIONAL ancladas a un activo puntual."""
    use_case = CambiarEstadoAsociacionSensorUseCase(
        db=db,
        repo=SqlAlchemyAsociacionSensorActivoRepository(db),
    )
    resultado = use_case.execute_infraestructura(id_infraestructura, id_asociacion, dto, usuario_actual)
    return AsociacionSensorActivoResponse(
        id_asociacion_activo_sensor=resultado.id_asociacion_activo_sensor,
        id_activo_biologico=resultado.id_activo_biologico,
        tipo_activo=resultado.tipo_activo,
        tipo_asociacion=resultado.tipo_asociacion,
        dispositivo_iot_id=resultado.dispositivo_iot_id,
        sensor_id=resultado.sensor_id,
        id_infraestructura=resultado.id_infraestructura,
        fecha_inicio=resultado.fecha_inicio,
        fecha_fin=resultado.fecha_fin,
        estado_asociacion=resultado.estado_asociacion,
        motivo=resultado.motivo,
        advertencia=None,
    )
