"""Router FastAPI para infraestructura IoT y alertas técnicas.

RF-60 — CU05 Dev scope:
  POST  /iot/heartbeat                        — Recibir heartbeat de dispositivo
  GET   /iot/dispositivos/{id}/estado         — Estado actual + historial de transiciones
  GET   /iot/dispositivos/{id}/historial      — Solo historial de transiciones
  GET   /iot/alertas-tecnicas                 — Listar alertas técnicas (admin + ing ONLY)
  PATCH /iot/alertas-tecnicas/{id}/estado     — Actualizar estado de alerta técnica

Auth POST heartbeat: dispositivo IoT — X-Device-API-Key + X-Device-Id en headers (sin JWT).
Auth REST: JWT Bearer + RBAC recurso 35 (infraestructura_iot) / recurso 36 (alertas_tecnicas_iot).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.errors import AuthenticationError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.telemetry.application.use_cases.alertas.actualizar_estado_alerta_use_case import ActualizarEstadoAlertaUseCase
from src.telemetry.application.use_cases.alertas.consultar_alertas_use_case import ConsultarAlertasUseCase
from src.telemetry.application.use_cases.infraestructura.aplicar_mantenimiento_dispositivo_use_case import AplicarMantenimientoDispositivoUseCase
from src.telemetry.application.use_cases.infraestructura.obtener_estado_dispositivo_use_case import ObtenerEstadoDispositivoUseCase
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import RecibirHeartbeatUseCase
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.dto.aplicar_mantenimiento_dto import AplicarMantenimientoDTO
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO
from src.telemetry.infrastructure.dto.actualizar_estado_alerta_dto import ActualizarEstadoAlertaDTO
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.estado_dispositivo_iot_repository import SqlAlchemyEstadoDispositivoIoTRepository
from src.telemetry.infrastructure.repositories.heartbeat_repository import SqlAlchemyHeartbeatRepository
from src.telemetry.infrastructure.repositories.historico_estado_alerta_repository import SqlAlchemyHistoricoEstadoAlertaRepository
from src.telemetry.infrastructure.repositories.historico_transicion_dispositivo_repository import SqlAlchemyHistoricoTransicionDispositivoRepository
from src.telemetry.infrastructure.repositories.periodo_inactividad_repository import SqlAlchemyPeriodoInactividadRepository
from src.telemetry.infrastructure.schema.alerta_schema import AlertaSchema, ListaAlertasSchema
from src.telemetry.infrastructure.schema.estado_dispositivo_iot_schema import EstadoDispositivoDetalleSchema, EstadoDispositivoIoTSchema, HistoricoTransicionSchema
from src.telemetry.infrastructure.schema.heartbeat_schema import HeartbeatReciboSchema

router = APIRouter(prefix="/iot", tags=["Telemetría IoT - Infraestructura"])


@router.post(
    "/heartbeat",
    response_model=HeartbeatReciboSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Recibir heartbeat de dispositivo IoT (RF-60)",
)
def recibir_heartbeat(
    dto: HeartbeatDTO,
    db: Session = Depends(get_db),
    x_device_api_key: str = Header(..., alias="X-Device-API-Key"),
    x_device_id: int = Header(..., alias="X-Device-Id"),
) -> HeartbeatReciboSchema:
    use_case = RecibirHeartbeatUseCase(
        db=db,
        dispositivo_port=DispositivoM09Adapter(db),
        heartbeat_repo=SqlAlchemyHeartbeatRepository(db),
        estado_repo=SqlAlchemyEstadoDispositivoIoTRepository(db),
        transicion_repo=SqlAlchemyHistoricoTransicionDispositivoRepository(db),
        periodo_repo=SqlAlchemyPeriodoInactividadRepository(db),
        alerta_repo=SqlAlchemyAlertaRepository(db),
        historico_alerta_repo=SqlAlchemyHistoricoEstadoAlertaRepository(db),
    )
    heartbeat = use_case.execute(dto=dto, device_id=x_device_id, access_key=x_device_api_key)
    return HeartbeatReciboSchema.model_validate(heartbeat)


@router.get(
    "/dispositivos/{id_dispositivo_iot}/estado",
    response_model=EstadoDispositivoDetalleSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(35, 2))],
    summary="Consultar estado actual e historial de transiciones del dispositivo (RF-60)",
)
def obtener_estado_dispositivo(
    id_dispositivo_iot: int,
    limite_historial: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EstadoDispositivoDetalleSchema:
    use_case = ObtenerEstadoDispositivoUseCase(
        db=db,
        estado_repo=SqlAlchemyEstadoDispositivoIoTRepository(db),
        transicion_repo=SqlAlchemyHistoricoTransicionDispositivoRepository(db),
    )
    resultado = use_case.execute(id_dispositivo_iot, limite_historial=limite_historial)
    return EstadoDispositivoDetalleSchema(
        estado=EstadoDispositivoIoTSchema.model_validate(resultado.estado),
        historial=[HistoricoTransicionSchema.model_validate(t) for t in resultado.historial],
    )


@router.get(
    "/dispositivos/{id_dispositivo_iot}/historial",
    response_model=list[HistoricoTransicionSchema],
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(35, 2))],
    summary="Historial de transiciones de estado del dispositivo (RF-60)",
)
def listar_historial_dispositivo(
    id_dispositivo_iot: int,
    limite: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[HistoricoTransicionSchema]:
    repo = SqlAlchemyHistoricoTransicionDispositivoRepository(db)
    transiciones = repo.listar_por_dispositivo(id_dispositivo_iot, limite=limite)
    return [HistoricoTransicionSchema.model_validate(t) for t in transiciones]


@router.patch(
    "/dispositivos/{id_dispositivo_iot}/mantenimiento",
    response_model=EstadoDispositivoIoTSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(35, 3))],
    summary="Transición manual de mantenimiento del dispositivo (RF-60 CA-7/CA-8) — solo Admin, Ing",
)
def aplicar_mantenimiento_dispositivo(
    id_dispositivo_iot: int,
    dto: AplicarMantenimientoDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EstadoDispositivoIoTSchema:
    detalle = SqlAlchemyUsuarioRepository(db).obtener_detalle(usuario_actual.id_usuario)
    nombre_usuario = f"{detalle.nombre} {detalle.apellidos}" if detalle else str(usuario_actual.id_usuario)
    use_case = AplicarMantenimientoDispositivoUseCase(
        db=db,
        estado_repo=SqlAlchemyEstadoDispositivoIoTRepository(db),
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    estado = use_case.execute(
        id_dispositivo_iot=id_dispositivo_iot,
        dto=dto,
        id_usuario=usuario_actual.id_usuario,
        nombre_usuario=nombre_usuario,
    )
    return EstadoDispositivoIoTSchema.model_validate(estado)


@router.get(
    "/alertas-tecnicas",
    response_model=ListaAlertasSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(36, 2))],
    summary="Listar alertas técnicas de dispositivos IoT (RF-60) — solo admin e Ingeniero",
)
def listar_alertas_tecnicas(
    estado: Optional[str] = Query(default=None),
    severidad: Optional[str] = Query(default=None),
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
        tipo_alerta='TECNICA',  # siempre filtrar por tipo TECNICA
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    return ListaAlertasSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=[AlertaSchema.model_validate(a) for a in alertas],
    )


@router.patch(
    "/alertas-tecnicas/{id_alerta}/estado",
    response_model=AlertaSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(36, 3))],
    summary="Actualizar estado de alerta técnica (RF-60)",
)
def actualizar_estado_alerta_tecnica(
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
