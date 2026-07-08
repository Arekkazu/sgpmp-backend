"""Router FastAPI para gestión de alertas de monitoreo IoT (`/iot/alertas`).

RF-57 — CU03 Dev scope:
  POST  /iot/alertas                   — Generar alerta desde evento de desviación
  GET   /iot/alertas                   — Listar alertas con filtros y paginación
  GET   /iot/alertas/{id_alerta}       — Detalle de alerta con historial de estados
  PATCH /iot/alertas/{id_alerta}/estado — Transicionar estado de ciclo de vida

Auth POST: dispositivo IoT — identidad verificada via access_key + device_id en body (sin JWT).
Auth REST: JWT Bearer + RBAC recurso 32 (alertas_operativas).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.errors import AuthenticationError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.telemetry.application.use_cases.alertas.actualizar_estado_alerta_use_case import ActualizarEstadoAlertaUseCase
from src.telemetry.application.use_cases.alertas.consultar_alertas_use_case import ConsultarAlertasUseCase
from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.dto.actualizar_estado_alerta_dto import ActualizarEstadoAlertaDTO
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.historico_estado_alerta_repository import SqlAlchemyHistoricoEstadoAlertaRepository
from src.telemetry.infrastructure.repositories.regla_alerta_repository import SqlAlchemyReglaAlertaRepository
from src.telemetry.infrastructure.schema.alerta_schema import (
    AlertaDetalleSchema,
    AlertaSchema,
    ListaAlertasSchema,
    ResultadoGeneracionAlertaSchema,
)

router = APIRouter(prefix="/iot/alertas", tags=["Telemetría IoT - Alertas"])


def _build_generar_use_case(db: Session) -> GenararAlertaUseCase:
    return GenararAlertaUseCase(
        db=db,
        alerta_repo=SqlAlchemyAlertaRepository(db),
        historico_repo=SqlAlchemyHistoricoEstadoAlertaRepository(db),
        regla_repo=SqlAlchemyReglaAlertaRepository(db),
    )


@router.post(
    "",
    response_model=ResultadoGeneracionAlertaSchema,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Generar alerta desde evento de desviación (RF-57 FA-01–FA-08)",
)
def procesar_evento_alerta(
    dto: ProcesarEventoAlertaDTO,
    db: Session = Depends(get_db),
) -> ResultadoGeneracionAlertaSchema:
    dispositivo_port = DispositivoM09Adapter(db)
    info = dispositivo_port.obtener_dispositivo_activo(
        device_id=dto.device_id,
        sensor_id=dto.sensor_id,
        access_key=dto.access_key,
    )
    if info is None or not info.es_activo_dispositivo or not info.es_activo_sensor:
        raise AuthenticationError(
            code="DISPOSITIVO_NO_AUTORIZADO",
            message="Credenciales de dispositivo inválidas o dispositivo inactivo.",
        )

    resultado = _build_generar_use_case(db).execute(
        dto=dto,
        id_dispositivo_ioit=info.id_dispositivo_iot,
        id_infraestructura=info.id_infraestructura,
    )
    return ResultadoGeneracionAlertaSchema(
        es_duplicado=resultado.es_duplicado,
        id_alerta=resultado.id_alerta,
        tipo_alerta=resultado.tipo_alerta,
        severidad=resultado.severidad,
        alerta_existente_id=resultado.alerta_existente_id,
        motivo_descarte=resultado.motivo_descarte,
    )


@router.get(
    "",
    response_model=ListaAlertasSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(32, 2))],
    summary="Listar alertas con filtros (RF-57 FA-09)",
)
def listar_alertas(
    estado: Optional[str] = Query(default=None),
    severidad: Optional[str] = Query(default=None),
    tipo_alerta: Optional[str] = Query(default=None),
    id_sensor: Optional[int] = Query(default=None),
    id_activo_biologico: Optional[int] = Query(default=None),
    origen_evento: Optional[str] = Query(default=None),
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaAlertasSchema:
    use_case = ConsultarAlertasUseCase(
        alerta_repo=SqlAlchemyAlertaRepository(db),
        historico_repo=SqlAlchemyHistoricoEstadoAlertaRepository(db),
    )
    alertas, total = use_case.listar(
        estado=estado,
        severidad=severidad,
        tipo_alerta=tipo_alerta,
        id_sensor=id_sensor,
        id_activo_biologico=id_activo_biologico,
        origen_evento=origen_evento,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    return ListaAlertasSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=[AlertaSchema.model_validate(a.__dict__) for a in alertas],
    )


@router.get(
    "/{id_alerta}",
    response_model=AlertaDetalleSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(32, 2))],
    summary="Obtener detalle de alerta con historial de estados (RF-57 FA-09)",
)
def obtener_alerta(
    id_alerta: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AlertaDetalleSchema:
    use_case = ConsultarAlertasUseCase(
        alerta_repo=SqlAlchemyAlertaRepository(db),
        historico_repo=SqlAlchemyHistoricoEstadoAlertaRepository(db),
    )
    alerta, historico = use_case.obtener_detalle(id_alerta)
    return AlertaDetalleSchema(
        **alerta.__dict__,
        historico_estados=[h.__dict__ for h in historico],
    )


@router.patch(
    "/{id_alerta}/estado",
    response_model=AlertaSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(32, 3))],
    summary="Actualizar estado de alerta (RF-57 FA-10)",
)
def actualizar_estado_alerta(
    id_alerta: int,
    dto: ActualizarEstadoAlertaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AlertaSchema:
    use_case = ActualizarEstadoAlertaUseCase(
        db=db,
        alerta_repo=SqlAlchemyAlertaRepository(db),
        historico_repo=SqlAlchemyHistoricoEstadoAlertaRepository(db),
    )
    alerta = use_case.execute(
        id_alerta=id_alerta,
        dto=dto,
        id_usuario=usuario_actual.id_usuario,
    )
    return AlertaSchema.model_validate(alerta.__dict__)
