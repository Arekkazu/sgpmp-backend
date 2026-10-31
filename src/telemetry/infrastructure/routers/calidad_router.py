# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: integra calidad temporal y alertas tecnicas |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-24 | Arekkazu | USAB-M03 M3-14 RF-62: calidad limitada a las fincas del usuario |
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: evaluacion de calidad de vision bajo demanda |
# | 2026-10-26 | Leandro | INC-M03-103-G164 RF-62: validar enums y declarar errores de consulta HTTP 422. |
# | 2026-10-26 | Arekkazu | Lote fixes M03/M04 RF-62: 422 por ruta con la clave común x-codigo-validacion |
# | 2026-10-27 | Leandro | INC-M03-132-G30 RF-53/54/62: pasar a RF62 el reloj de la lectura original sin consultar estado actual. |
# | 2026-10-27 | Leandro | INC-M03-133-G170 RF-62: restringir lote al administrador e inyectar contexto y alertas reales. |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 T-18 RF-62: sensor y lectura por nombre en calidad |
"""Router FastAPI para evaluación de calidad de telemetría.

RF-62 — CU06 Dev scope:
  GET  /iot/calidad                         — Listar evaluaciones con filtros
  GET  /iot/calidad/{id_telemetria}         — Calidad de una lectura específica
  POST /iot/calidad/{id_telemetria}/evaluar — Disparar evaluación puntual
  POST /iot/calidad/reevaluar               — Re-evaluación explícita admin (FA-08)
  POST /iot/calidad/vision/{id}/evaluar     — Calidad de una observación de visión (AIOT-SPEC-01)

Auth: JWT Bearer + RBAC recurso 38 (calidad_telemetria).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import get_db
from src.shared.errors import NotFoundError, AuthorizationError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.telemetry.application.use_cases.calidad.consultar_calidad_use_case import ConsultarCalidadUseCase
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.application.use_cases.calidad.evaluar_calidad_vision_use_case import EvaluarCalidadVisionUseCase
from src.telemetry.infrastructure.adapters.dispositivo_m09_adapter import DispositivoM09Adapter
from src.telemetry.infrastructure.adapters.parametros_vision_mlops_adapter import ParametrosVisionMLOpsAdapter
from src.telemetry.infrastructure.repositories.observacion_vision_repository import SqlAlchemyObservacionVisionRepository
from src.telemetry.infrastructure.schema.telemetria_schema import ObservacionVisionResponse
from src.telemetry.application.use_cases.calidad.solicitar_reevaluacion_use_case import SolicitarReevaluacionUseCase
from src.telemetry.domain.entities.telemetria_calidad import ClasificacionCalidad, EstadoEvaluacion
from src.telemetry.infrastructure.adapters.parametros_calidad_mlops_adapter import ParametrosCalidadMLOpsAdapter
from src.telemetry.infrastructure.adapters.contexto_calidad_m09_rf60_adapter import ContextoCalidadM09RF60Adapter
from src.telemetry.application.use_cases.calidad.generar_alerta_calidad_use_case import GenerarAlertaCalidadUseCase
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository
from src.telemetry.infrastructure.dto.solicitar_reevaluacion_dto import SolicitarReevaluacionDTO
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.telemetria_calidad_repository import SqlAlchemyTelemetriaCalidadRepository
from src.telemetry.infrastructure.repositories.telemetria_repository import SqlAlchemyTelemetriaRepository
from src.telemetry.infrastructure.schema.telemetria_calidad_schema import (
    ListaCalidadSchema,
    ReevaluacionResponseSchema,
    TelemetriaCalidadSchema,
)
from src.shared.fechas import FechaHoraUtc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iot/calidad", tags=["Telemetría IoT - Calidad RF-62"])



def _con_nombres(db: Session, items: list[TelemetriaCalidadSchema]) -> list[TelemetriaCalidadSchema]:
    """T-18: sensor y lectura por nombre, una consulta por página (mismo patrón que vinculaciones)."""
    ids = list({e.id_telemetria for e in items})
    if not ids:
        return items
    try:
        filas = db.execute(text(
        'SELECT t.id_telemetria, s.nombre, va.nombre, coalesce(t.valor_ajustado, t.valor_crudo), '
        'coalesce(va.unidad, t.unidad_medida) FROM modulo3.telemetrias t '
        'LEFT JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = t.id_variable '
        'LEFT JOIN modulo9.sensores s ON s.id_sensores = t.id_sensor '
        'WHERE t.id_telemetria = ANY(:ids)'), {'ids': ids}).all()
        lecturas = {f[0]: tuple(f[1:]) for f in filas}
    except Exception:
        # Los nombres son de presentación: si no se resuelven, la evaluación sale con sus IDs.
        logger.warning('No se resolvieron los nombres de sensor y lectura de calidad.', exc_info=True)
        return items
    for e in items:
        e.nombre_sensor, e.nombre_variable, valor, e.unidad_lectura = lecturas.get(e.id_telemetria, (None,) * 4)
        e.valor_lectura = float(valor) if valor is not None else None
    return items

@router.get(
    "",
    response_model=ListaCalidadSchema,
    status_code=200,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    openapi_extra={"x-codigo-validacion": 422},
    dependencies=[Depends(require_permission(38, 2))],
    summary="Listar evaluaciones de calidad (RF-62)",
)
def listar_calidad(
    id_sensor: Optional[int] = Query(default=None),
    clasificacion: Optional[ClasificacionCalidad] = Query(default=None),
    fecha_desde: Optional[FechaHoraUtc] = Query(default=None),
    fecha_hasta: Optional[FechaHoraUtc] = Query(default=None),
    estado_evaluacion: Optional[EstadoEvaluacion] = Query(default=None),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaCalidadSchema:
    use_case = ConsultarCalidadUseCase(
        calidad_repo=SqlAlchemyTelemetriaCalidadRepository(db),
    )
    items, total = use_case.listar(
        id_sensor=id_sensor,
        clasificacion=clasificacion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado_evaluacion=estado_evaluacion,
        pagina=pagina,
        por_pagina=por_pagina,
        ids_fincas_permitidas=AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
            usuario_actual.id_usuario, usuario_actual.id_rol
        ),
    )
    return ListaCalidadSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=_con_nombres(db, [TelemetriaCalidadSchema.model_validate(e) for e in items]),
    )


@router.get(
    "/{id_telemetria}",
    response_model=TelemetriaCalidadSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(38, 2))],
    summary="Obtener calidad de una lectura (RF-62)",
)
def obtener_calidad(
    id_telemetria: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> TelemetriaCalidadSchema:
    use_case = ConsultarCalidadUseCase(
        calidad_repo=SqlAlchemyTelemetriaCalidadRepository(db),
    )
    return _con_nombres(db, [TelemetriaCalidadSchema.model_validate(use_case.get(id_telemetria))])[0]


@router.post(
    "/vision/{id_observacion_vision}/evaluar",
    response_model=ObservacionVisionResponse,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(38, 5))],
    summary="Evaluar la calidad de una observación de visión (RF-62)",
)
def evaluar_calidad_vision(
    id_observacion_vision: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ObservacionVisionResponse:
    """Calcula el índice ponderado de RF-62 (AIOT-SPEC-01) de una observación ya ingerida.

    **Acceso:** `calidad_telemetria` · Ejecutar.

    El worker post-commit evalúa cada observación por su cuenta; este endpoint
    lo adelanta. Es idempotente: si ya estaba evaluada devuelve esa evaluación
    sin recalcular. 503 `PARAMETRO_CONFIGURACION_AUSENTE` si faltan los pesos en
    M09 y 503 `PARAMETRO_CONFIGURACION_INVALIDO` si la cámara no tiene fps (RF-23).
    """
    observacion = EvaluarCalidadVisionUseCase(
        db,
        SqlAlchemyObservacionVisionRepository(db),
        ParametrosVisionMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db)),
        DispositivoM09Adapter(db),
    ).execute(id_observacion_vision)
    return ObservacionVisionResponse.desde(observacion)


@router.post(
    "/{id_telemetria}/evaluar",
    response_model=TelemetriaCalidadSchema,
    status_code=201,
    responses={
        200: {"description":"Evaluación omitida por inactividad RF-60; no se crea evaluación."},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(38, 5))],
    summary="Disparar evaluación de calidad puntual (RF-62)",
)
def evaluar_calidad(
    id_telemetria: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> TelemetriaCalidadSchema:
    from sqlalchemy import text
    row = db.execute(
        text(
            'SELECT id_sensor, id_variable, valor_crudo, valor_ajustado, '
            'timestamp_captura, estado_calidad, parametros_calibracion, reloj_desincronizado, metadatos '
            'FROM modulo3.telemetrias WHERE id_telemetria = :id'
        ),
        {'id': id_telemetria},
    ).fetchone()
    if row is None:
        raise NotFoundError(code='TELEMETRIA_NO_ENCONTRADA', message='Lectura telemétrica no encontrada.')

    from decimal import Decimal
    use_case = EvaluarCalidadTelemetriaUseCase(
        db=db,
        telemetria_repo=SqlAlchemyTelemetriaRepository(db),
        calidad_repo=SqlAlchemyTelemetriaCalidadRepository(db),
        parametros_port=ParametrosCalidadMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db), SqlAlchemyConfiguracionGlobalRepository(db)),
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
        contexto_port=ContextoCalidadM09RF60Adapter(db),
        alertas_calidad=GenerarAlertaCalidadUseCase(SqlAlchemyAlertaRepository(db)),
    )
    evaluacion = use_case.execute(
        id_telemetria=id_telemetria,
        id_sensor=row[0],
        id_variable=row[1],
        valor=Decimal(str(row[2])),
        valor_ajustado=Decimal(str(row[3])) if row[3] is not None else None,
        timestamp_captura=row[4],
        estado_calidad_rf53=row[5],
        parametros_calibracion=row[6],
        reloj_desincronizado=row[7],
        evidencia_reloj=(row[8] or {}).get('rf53_reloj'),
    )
    if evaluacion is None:
        return JSONResponse(status_code=200,content={
            "id_telemetria":id_telemetria,"resultado":"EVALUACION_OMITIDA_POR_INACTIVIDAD"})
    return TelemetriaCalidadSchema.model_validate(evaluacion)


@router.post(
    "/reevaluar",
    response_model=ReevaluacionResponseSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(38, 5))],
    summary="Re-evaluación explícita ante error de configuración (FA-08)",
)
def solicitar_reevaluacion(
    dto: SolicitarReevaluacionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ReevaluacionResponseSchema:
    if not AlcanceFincaAdapter(db).es_global(usuario_actual.id_rol):
        raise AuthorizationError(code='ACCESO_DENEGADO',
            message='La re-evaluación masiva de calidad requiere un Administrador.')
    use_case = SolicitarReevaluacionUseCase(
        db=db,
        calidad_repo=SqlAlchemyTelemetriaCalidadRepository(db),
        telemetria_repo=SqlAlchemyTelemetriaRepository(db),
        parametros_port=ParametrosCalidadMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db), SqlAlchemyConfiguracionGlobalRepository(db)),
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
        contexto_port=ContextoCalidadM09RF60Adapter(db),
        alertas_calidad=GenerarAlertaCalidadUseCase(SqlAlchemyAlertaRepository(db)),
    )
    detalle = SqlAlchemyUsuarioRepository(db).obtener_detalle(usuario_actual.id_usuario)
    nombre_usuario = f"{detalle.nombre} {detalle.apellidos}" if detalle else str(usuario_actual.id_usuario)
    resultado = use_case.execute(dto=dto, id_usuario=usuario_actual.id_usuario, nombre_usuario=nombre_usuario)
    return ReevaluacionResponseSchema(
        evaluaciones_superadas=resultado.evaluaciones_superadas,
        evaluaciones_creadas=resultado.evaluaciones_creadas,
    )
