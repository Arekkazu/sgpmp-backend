# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: integra calidad temporal y alertas tecnicas |
# | 2026-10-22 | Leandro | DEV-42 RF-60: aplica alcance de finca al mantenimiento |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-24 | Arekkazu | USAB-M03 M3-10 RF-60: GET /iot/dispositivos, listado con estado de las fincas del usuario |
# | 2026-10-25 | Arekkazu | INC-M03-149-G89 RF-58: el cierre de la alerta recalcula el semáforo |
# | 2026-10-27 | Leandro | INC-M03-127-G27 RF-54/60: aplicar el alcance por finca existente a la consulta de estado usada por G27. |
"""Router FastAPI para infraestructura IoT y alertas técnicas.

RF-60 — CU05 Dev scope:
  POST  /iot/heartbeat                        — Recibir heartbeat de dispositivo
  POST  /iot/eventos-buffer                   — Aviso de buffer del Gateway Edge (RF-54 → RF-60, D10)
  GET   /iot/dispositivos/{id}/estado         — Estado actual + historial de transiciones
  GET   /iot/dispositivos/{id}/historial      — Solo historial de transiciones
  GET   /iot/alertas-tecnicas                 — Listar alertas técnicas (admin + ing ONLY)
  PATCH /iot/alertas-tecnicas/{id}/estado     — Actualizar estado de alerta técnica

Auth POST heartbeat: token de servicio del broker (`Authorization: Bearer`); device_id + serial en el body.
Auth POST eventos-buffer: token de servicio del broker; serial en el body (interno, lo llama solo el broker).
Auth REST: JWT Bearer + RBAC recurso 35 (infraestructura_iot) / recurso 36 (alertas_tecnicas_iot).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.shared.broker_auth import require_token_servicio_broker
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import get_db, get_db_sistema
from src.shared.errors import AuthenticationError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.telemetry.application.use_cases.alertas.actualizar_estado_alerta_use_case import ActualizarEstadoAlertaUseCase
from src.telemetry.application.use_cases.alertas.consultar_alertas_use_case import ConsultarAlertasUseCase
from src.telemetry.application.use_cases.infraestructura.aplicar_mantenimiento_dispositivo_use_case import AplicarMantenimientoDispositivoUseCase
from src.telemetry.application.use_cases.infraestructura.listar_dispositivos_use_case import ListarDispositivosUseCase
from src.telemetry.application.use_cases.infraestructura.obtener_estado_dispositivo_use_case import ObtenerEstadoDispositivoUseCase
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import RecibirHeartbeatUseCase
from src.telemetry.application.use_cases.infraestructura.registrar_evento_buffer_use_case import RegistrarEventoBufferUseCase
from src.telemetry.domain.entities.alerta import AmbitoAlerta
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.dto.aplicar_mantenimiento_dto import AplicarMantenimientoDTO
from src.telemetry.infrastructure.dto.evento_buffer_dto import RecibirEventoBufferDTO
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
from src.telemetry.infrastructure.schema.estado_dispositivo_iot_schema import DispositivoConEstadoSchema, EstadoDispositivoDetalleSchema, EstadoDispositivoIoTSchema, HistoricoTransicionSchema
from src.telemetry.infrastructure.schema.heartbeat_schema import EventoBufferReciboSchema, HeartbeatReciboSchema
from src.shared.fechas import FechaHoraUtc
from src.telemetry.infrastructure.workers.postcommit_worker import recalcular_semaforo_sensor

router = APIRouter(prefix="/iot", tags=["Telemetría IoT - Infraestructura"])


@router.post(
    "/heartbeat",
    response_model=HeartbeatReciboSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_token_servicio_broker)],
    summary="Recibir heartbeat de dispositivo IoT (RF-60)",
)
def recibir_heartbeat(
    dto: HeartbeatDTO,
    db: Session = Depends(get_db_sistema),
) -> HeartbeatReciboSchema:
    use_case = RecibirHeartbeatUseCase(
        db=db,
        dispositivo_port=DispositivoM09Adapter(db),
        heartbeat_repo=SqlAlchemyHeartbeatRepository(db),
    )
    heartbeat = use_case.execute(dto=dto)
    return HeartbeatReciboSchema.model_validate(heartbeat)


@router.post(
    "/eventos-buffer",
    response_model=EventoBufferReciboSchema,
    status_code=201,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_token_servicio_broker)],
    summary="Aviso de buffer del Gateway Edge → alerta técnica RF-60 + evento RF-63 (RF-54, D10)",
)
def recibir_evento_buffer(
    dto: RecibirEventoBufferDTO,
    db: Session = Depends(get_db_sistema),
) -> EventoBufferReciboSchema:
    resultado = RegistrarEventoBufferUseCase(
        db=db,
        dispositivo_port=DispositivoM09Adapter(db),
        alerta_repo=SqlAlchemyAlertaRepository(db),
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    ).execute(dto)
    return EventoBufferReciboSchema.model_validate(resultado)


@router.get(
    "/dispositivos",
    response_model=list[DispositivoConEstadoSchema],
    status_code=200,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission(35, 2))],
    summary="Listar dispositivos IoT con su estado actual (RF-60)",
)
def listar_dispositivos(
    estado: Optional[str] = Query(default=None, description="ACTIVO, SIN_SEÑAL, BUFFER_ACTIVO, INACTIVO, EN_MANTENIMIENTO o DESCONOCIDO"),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[DispositivoConEstadoSchema]:
    """Dispositivos activos de las fincas del usuario con estado, batería, señal y último
    contacto; primero los que fallan (M3-10). El Administrador ve todas las fincas.

    **Acceso:** `infraestructura_iot` · Leer.
    """
    filas = ListarDispositivosUseCase(SqlAlchemyEstadoDispositivoIoTRepository(db)).execute(
        AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(usuario_actual.id_usuario, usuario_actual.id_rol),
        estado=estado,
    )
    return [DispositivoConEstadoSchema.model_validate(f) for f in filas]


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
    resultado = use_case.execute(
        id_dispositivo_iot,
        limite_historial=limite_historial,
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario, usuario_actual.id_rol
        ),
    )
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
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario, usuario_actual.id_rol),
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
    fecha_desde: Optional[FechaHoraUtc] = Query(default=None),
    fecha_hasta: Optional[FechaHoraUtc] = Query(default=None),
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
        ambito=AmbitoAlerta.TECNICA,
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario,usuario_actual.id_rol),
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
        ambito=AmbitoAlerta.TECNICA,
        recalcular_semaforo=lambda id_sensor: recalcular_semaforo_sensor(db, id_sensor),
    )
    permitidas = AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
        usuario_actual.id_usuario,usuario_actual.id_rol)
    ConsultarAlertasUseCase(SqlAlchemyAlertaRepository(db),SqlAlchemyHistoricoEstadoAlertaRepository(db)).obtener_detalle(
        id_alerta,ambito=AmbitoAlerta.TECNICA,ids_fincas_permitidas=permitidas)
    alerta = use_case.execute(
        id_alerta=id_alerta,
        dto=dto,
        id_usuario=usuario_actual.id_usuario,
    )
    return AlertaSchema.model_validate(alerta.__dict__)
