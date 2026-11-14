# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | INC-M04-215/216 RF-72: validaciones de entrada responden 422       |
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: POST /ampliaciones (excepción por resultado) |
# | 2026-11-03 | Arekkazu | RF-72: GET /bandeja, inferencias por evaluar (la pantalla mostraba datos de ejemplo) |
"""Router FastAPI para retroalimentación clínica M04 (`/prediccion/retroalimentacion`).

RF-72 CU-08: registro de retroalimentación clínica sobre resultados de inferencia.
  POST /prediccion/retroalimentacion
  POST /prediccion/retroalimentacion/ampliaciones — excepción a la ventana para un resultado
  GET  /prediccion/retroalimentacion/bandeja — inferencias por evaluar, con su estado y totales

Autorización RBAC:
  recurso retroalimentacion_clinica = id_recurso 45, C=1 (Veterinario), R=2 (Veterinario, Administrador)
  ampliaciones: recurso configuraciones_globales = id_recurso 21, U=3 (Administrador)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.retroalimentacion.ampliar_ventana_retroalimentacion_use_case import AmpliarVentanaRetroalimentacionUseCase
from src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case import RegistrarRetroalimentacionUseCase
from src.prediction.application.use_cases.retroalimentacion.consultar_bandeja_retroalimentacion_use_case import (
    ConsultarBandejaRetroalimentacionUseCase,
)
from src.prediction.infrastructure.repositories.bandeja_retroalimentacion_repository import (
    SqlAlchemyBandejaRetroalimentacionRepository,
)
from src.prediction.infrastructure.schema.bandeja_retroalimentacion_schema import (
    BandejaRetroalimentacionResponse, IndicadoresBandejaResponse, InferenciaPorEvaluarResponse,
)
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.prediction.infrastructure.adapters.resultado_inferencia_adapter import SqlAlchemyResultadoInferenciaAdapter
from src.prediction.infrastructure.dto.ampliar_ventana_retroalimentacion_dto import AmpliarVentanaRetroalimentacionDTO
from src.prediction.infrastructure.dto.registrar_retroalimentacion_dto import RegistrarRetroalimentacionDTO
from src.prediction.infrastructure.repositories.ampliacion_ventana_retroalimentacion_repository import (
    SqlAlchemyAmpliacionVentanaRetroalimentacionRepository,
)
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.repositories.patologia_m04_repository import SqlAlchemyPatologiaM04Repository
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.prediction.infrastructure.repositories.retroalimentacion_clinica_repository import SqlAlchemyRetroalimentacionClinicaRepository
from src.prediction.infrastructure.schema.ampliacion_ventana_retroalimentacion_schema import (
    AmpliacionVentanaRetroalimentacionResponse,
)
from src.prediction.infrastructure.schema.retroalimentacion_clinica_schema import RetroalimentacionClinicaResponse
from src.shared.database import get_db
from src.shared.fechas import FechaHoraUtc
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(
    prefix="/prediccion/retroalimentacion",
    tags=["Predicción M04 - Retroalimentación Clínica"],
)

_RECURSO = 45


@router.post(
    "",
    status_code=201,
    response_model=RetroalimentacionClinicaResponse,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Registrar retroalimentación clínica sobre un resultado de inferencia (RF-72)",
    openapi_extra={"x-codigo-validacion": 422},
)
def registrar_retroalimentacion(
    dto: RegistrarRetroalimentacionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> RetroalimentacionClinicaResponse:
    use_case = RegistrarRetroalimentacionUseCase(
        db=db,
        repo=SqlAlchemyRetroalimentacionClinicaRepository(db),
        resultado_port=SqlAlchemyResultadoInferenciaAdapter(db),
        patologia_repo=SqlAlchemyPatologiaM04Repository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        parametros_port=SqlAlchemyParametrosMLOpsRepository(db),
        ampliacion_repo=SqlAlchemyAmpliacionVentanaRetroalimentacionRepository(db),
    )
    entidad = use_case.execute(dto, usuario_actual.id_usuario)
    return RetroalimentacionClinicaResponse.from_entity(entidad)


_RECURSO_CONFIGURACION_GLOBAL = 21  # modulo1.recursos: 'configuraciones_globales'


@router.post(
    "/ampliaciones",
    status_code=201,
    response_model=AmpliacionVentanaRetroalimentacionResponse,
    dependencies=[Depends(require_permission(_RECURSO_CONFIGURACION_GLOBAL, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Ampliar la ventana de retroalimentación de un resultado específico (RF-72)",
    openapi_extra={"x-codigo-validacion": 422},
)
def ampliar_ventana_retroalimentacion(
    dto: AmpliarVentanaRetroalimentacionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> AmpliacionVentanaRetroalimentacionResponse:
    """Excepción justificada del Administrador: solo ese resultado queda habilitado durante
    `dias_habilitados` días desde hoy. La ventana global no cambia y queda en RF-73
    como `VENTANA_RETROALIMENTACION_AMPLIADA`."""
    use_case = AmpliarVentanaRetroalimentacionUseCase(
        db=db,
        repo=SqlAlchemyAmpliacionVentanaRetroalimentacionRepository(db),
        resultado_port=SqlAlchemyResultadoInferenciaAdapter(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    )
    entidad = use_case.execute(
        id_resultado_inferencia=dto.id_resultado_inferencia,
        dias_habilitados=dto.dias_habilitados,
        justificacion=dto.justificacion,
        id_usuario=usuario_actual.id_usuario,
    )
    return AmpliacionVentanaRetroalimentacionResponse.model_validate(entidad)


@router.get(
    "/bandeja",
    response_model=BandejaRetroalimentacionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse},
               503: {"model": ErrorResponse}},
    summary="Inferencias por evaluar, con su estado de evaluación y totales (RF-72)",
)
def bandeja_retroalimentacion(
    estado_evaluacion: Optional[str] = Query(default=None, description="PENDIENTE | EVALUADO | VENTANA_VENCIDA"),
    nivel_riesgo: Optional[int] = Query(default=None, description="0 Normal, 1 Bajo, 2 Moderado, 3 Alto"),
    id_activo_biologico: Optional[int] = Query(default=None, gt=0),
    desde: Optional[FechaHoraUtc] = Query(default=None, description="Por defecto: la ventana de M09 más 30 días"),
    hasta: Optional[FechaHoraUtc] = Query(default=None),
    pagina: int = Query(default=1),
    por_pagina: int = Query(default=25, description="1 a 100."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> BandejaRetroalimentacionResponse:
    """Entran las inferencias que abren un episodio de riesgo moderado o alto (el nivel pasa a 2 o 3
    respecto a la anterior del mismo animal), las que generaron alerta y las que ya tienen una
    evaluación. Pendientes primero. ``puede_evaluar`` aplica las reglas del registro para el usuario
    actual: dentro de la ventana o con ampliación, sin evaluación propia y con el activo fuera de BAJA."""
    fincas = AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(usuario_actual.id_usuario, usuario_actual.id_rol)
    r = ConsultarBandejaRetroalimentacionUseCase(
        SqlAlchemyBandejaRetroalimentacionRepository(db), SqlAlchemyParametrosMLOpsRepository(db),
    ).execute(
        ids_fincas=fincas, id_usuario=usuario_actual.id_usuario, estado_evaluacion=estado_evaluacion,
        nivel_riesgo=nivel_riesgo, id_activo_biologico=id_activo_biologico, desde=desde, hasta=hasta,
        pagina=pagina, por_pagina=por_pagina,
    )
    return BandejaRetroalimentacionResponse(
        items=[InferenciaPorEvaluarResponse.from_entity(i) for i in r.items], total=r.total, pagina=r.pagina,
        por_pagina=r.por_pagina, ventana_dias=r.ventana_dias,
        indicadores=IndicadoresBandejaResponse(**vars(r.indicadores)),
    )
