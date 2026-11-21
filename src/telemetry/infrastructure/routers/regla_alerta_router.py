# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: CRUD de reglas de alerta sin SQL manual |
"""Router FastAPI del CRUD de reglas de alerta (`/iot/reglas-alertas`, RF-55/RF-57).

  POST  /iot/reglas-alertas                    — Crear regla
  GET   /iot/reglas-alertas                    — Listar (filtros tipo_sensor, es_activa, es_regla_compuesta)
  GET   /iot/reglas-alertas/{id}               — Obtener una regla
  PUT   /iot/reglas-alertas/{id}               — Editar (concurrencia optimista, 412)
  PATCH /iot/reglas-alertas/{id}/desactivar    — Baja lógica
  PATCH /iot/reglas-alertas/{id}/reactivar     — Reactivar

Una compuesta con ``tiene_ejecutar_edge`` se propaga a sus Gateway Edge después
de cada escritura (``sincronizacion_edge`` en la respuesta); la propagación
manual sigue en ``regla_alerta_edge_router``.

Autorización RBAC: recurso ``reglas_alertas`` (su id sale de la secuencia; se
ubica por nombre). C=1, R=2, U=3, D=4 para el Administrador; R para el
Ingeniero de Campo.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission_sobre
from src.shared.schemas import ErrorResponse
from src.telemetry.application.use_cases.reglas.consultar_reglas_alertas_use_case import ConsultarReglasAlertasUseCase
from src.telemetry.application.use_cases.reglas.crear_regla_alerta_use_case import CrearReglaAlertaUseCase
from src.telemetry.application.use_cases.reglas.desactivar_regla_alerta_use_case import DesactivarReglaAlertaUseCase
from src.telemetry.application.use_cases.reglas.editar_regla_alerta_use_case import EditarReglaAlertaUseCase
from src.telemetry.application.use_cases.reglas.reactivar_regla_alerta_use_case import ReactivarReglaAlertaUseCase
from src.telemetry.application.use_cases.reglas.sincronizar_regla_edge_use_case import SincronizarReglaEdgeUseCase
from src.telemetry.infrastructure.adapters.regla_compuesta_edge_mqtt_adapter import ReglaCompuestaEdgeMqttAdapter
from src.telemetry.infrastructure.dto.regla_alerta_dto import (
    CrearReglaAlertaDTO,
    EditarReglaAlertaDTO,
    TipoSensorRegla,
)
from src.telemetry.infrastructure.repositories.regla_alerta_repository import SqlAlchemyReglaAlertaRepository
from src.telemetry.infrastructure.repositories.sincronizacion_regla_edge_repository import (
    SqlAlchemySincronizacionReglaEdgeRepository,
)
from src.telemetry.infrastructure.schema.regla_alerta_schema import ReglaAlertaResponse

router = APIRouter(prefix="/iot/reglas-alertas", tags=["Telemetría IoT - Reglas de alerta"])

_RECURSO = "reglas_alertas"
_ERRORES = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _sincronizar(db: Session) -> SincronizarReglaEdgeUseCase:
    return SincronizarReglaEdgeUseCase(
        db=db,
        regla_repo=SqlAlchemyReglaAlertaRepository(db),
        sincronizacion_repo=SqlAlchemySincronizacionReglaEdgeRepository(db),
        edge_port=ReglaCompuestaEdgeMqttAdapter(),
    )


@router.post(
    "",
    response_model=ReglaAlertaResponse,
    status_code=201,
    responses={**_ERRORES, 400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission_sobre(_RECURSO, 1))],
    summary="Crear regla de alerta (RF-55/RF-57)",
)
def crear_regla_alerta(
    dto: CrearReglaAlertaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ReglaAlertaResponse:
    """400 si no trae umbral o el rango es inválido; 409 si el nombre ya existe."""
    use_case = CrearReglaAlertaUseCase(db=db, regla_repo=SqlAlchemyReglaAlertaRepository(db), sincronizar=_sincronizar(db))
    return ReglaAlertaResponse.de(*use_case.execute(dto, usuario_actual.id_usuario))


@router.get(
    "",
    response_model=List[ReglaAlertaResponse],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission_sobre(_RECURSO, 2))],
    summary="Listar reglas de alerta (RF-55/RF-57)",
)
def listar_reglas_alertas(
    tipo_sensor: Optional[TipoSensorRegla] = Query(default=None),
    es_activa: Optional[bool] = Query(default=None),
    es_regla_compuesta: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
) -> List[ReglaAlertaResponse]:
    reglas = ConsultarReglasAlertasUseCase(SqlAlchemyReglaAlertaRepository(db)).listar(
        tipo_sensor=tipo_sensor, es_activa=es_activa, es_regla_compuesta=es_regla_compuesta,
    )
    return [ReglaAlertaResponse.de(r) for r in reglas]


@router.get(
    "/{id_regla_alertas}",
    response_model=ReglaAlertaResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission_sobre(_RECURSO, 2))],
    summary="Obtener una regla de alerta (RF-55/RF-57)",
)
def obtener_regla_alerta(id_regla_alertas: int, db: Session = Depends(get_db)) -> ReglaAlertaResponse:
    return ReglaAlertaResponse.de(ConsultarReglasAlertasUseCase(SqlAlchemyReglaAlertaRepository(db)).obtener(id_regla_alertas))


@router.put(
    "/{id_regla_alertas}",
    response_model=ReglaAlertaResponse,
    responses={**_ERRORES, 400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 412: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission_sobre(_RECURSO, 3))],
    summary="Editar regla de alerta (RF-55/RF-57)",
)
def editar_regla_alerta(
    id_regla_alertas: int,
    dto: EditarReglaAlertaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ReglaAlertaResponse:
    """Reemplaza la regla. 412 si ``fecha_actualizacion`` no es la vigente; 422 si está inactiva."""
    use_case = EditarReglaAlertaUseCase(db=db, regla_repo=SqlAlchemyReglaAlertaRepository(db), sincronizar=_sincronizar(db))
    return ReglaAlertaResponse.de(*use_case.execute(id_regla_alertas, dto, usuario_actual.id_usuario))


@router.patch(
    "/{id_regla_alertas}/desactivar",
    response_model=ReglaAlertaResponse,
    responses=_ERRORES,
    dependencies=[Depends(require_permission_sobre(_RECURSO, 4))],
    summary="Desactivar regla de alerta (RF-55/RF-57)",
)
def desactivar_regla_alerta(
    id_regla_alertas: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ReglaAlertaResponse:
    """Baja lógica; si estaba en el Edge, el Gateway la retira. 422 si ya está inactiva."""
    use_case = DesactivarReglaAlertaUseCase(db=db, regla_repo=SqlAlchemyReglaAlertaRepository(db), sincronizar=_sincronizar(db))
    return ReglaAlertaResponse.de(*use_case.execute(id_regla_alertas, usuario_actual.id_usuario))


@router.patch(
    "/{id_regla_alertas}/reactivar",
    response_model=ReglaAlertaResponse,
    responses=_ERRORES,
    dependencies=[Depends(require_permission_sobre(_RECURSO, 4))],
    summary="Reactivar regla de alerta (RF-55/RF-57)",
)
def reactivar_regla_alerta(
    id_regla_alertas: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ReglaAlertaResponse:
    """**Acceso:** Desactivar, igual que en ciclos y especies. 422 si ya está activa."""
    use_case = ReactivarReglaAlertaUseCase(db=db, regla_repo=SqlAlchemyReglaAlertaRepository(db), sincronizar=_sincronizar(db))
    return ReglaAlertaResponse.de(*use_case.execute(id_regla_alertas, usuario_actual.id_usuario))
