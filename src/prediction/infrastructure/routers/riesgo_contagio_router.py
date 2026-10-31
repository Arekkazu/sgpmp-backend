# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
# | 2026-10-29 | Arekkazu | PEND-456 RF-68: GET con los cálculos del alcance para la pestaña Contagio |
# | 2026-10-30 | Leandro | INC-M04-217-G026 RF-68: documentar umbrales dinámicos y condiciones de alerta. |
# | 2026-10-30 | Leandro | INC-M04-218-G029 RF-68: conectar el puerto de ocupación histórica y documentar el fallback E2. |
# | 2026-10-30 | Leandro | INC-M04-219-G030 RF-68: documentar el rechazo 422 por cobertura individual inferior al 60 %. |
# | 2026-10-30 | Leandro | INC-M04-220-G032 RF-68: documentar recálculo inmediato 201 y retirar el 429 de frecuencia obsoleto. |
# | 2026-10-30 | Leandro | INC-M04-221-G032 RF-68: documentar activación RF-65 y respuesta sin caché del perfil MVP. |
"""Router FastAPI del Modelo 4 — riesgo de contagio (RF-68).

  POST /prediccion/riesgo-contagio — Ejecutar el modelo para un lote
  GET  /prediccion/riesgo-contagio — Cálculos de las fincas del usuario, los más recientes primero

Auth: JWT Bearer + RBAC sobre el recurso 41 (configuracion_motor_ia): Ejecutar (5) / Leer (2).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import (
    EstimarRiesgoContagioUseCase,
)
from src.prediction.infrastructure.adapters.ocupacion_lote_m02_adapter import OcupacionLoteM02Adapter
from src.prediction.infrastructure.adapters.activo_biologico_m02_adapter import ActivoBiologicoM02Adapter
from src.prediction.infrastructure.adapters.alerta_contagio_rf57_adapter import AlertaContagioRf57Adapter
from src.prediction.infrastructure.dto.estimar_riesgo_contagio_dto import EstimarRiesgoContagioDTO
from src.prediction.infrastructure.repositories.configuracion_motor_ia_repository import (
    SqlAlchemyConfiguracionMotorIARepository,
)
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from src.prediction.infrastructure.repositories.resultado_riesgo_contagio_repository import (
    SqlAlchemyResultadoRiesgoContagioRepository,
)
from src.prediction.application.use_cases.monitor.listar_riesgo_contagio_use_case import ListarRiesgoContagioUseCase
from src.prediction.infrastructure.repositories.monitor_prediccion_repository import (
    SqlAlchemyMonitorPrediccionRepository,
)
from src.prediction.infrastructure.schema.monitor_prediccion_schema import RiesgoContagioMonitorResponse
from src.prediction.infrastructure.schema.riesgo_contagio_schema import RiesgoContagioResponse
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.fechas import FechaHoraUtc
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion/riesgo-contagio", tags=["Predicción M04 - Riesgo de contagio"])

_RECURSO = 41  # modulo1.recursos: 'configuracion_motor_ia'


@router.post(
    "",
    response_model=RiesgoContagioResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        200: {"model": RiesgoContagioResponse, "description": "Perfil ESTANDAR: mismas entradas en menos de 5 s, caché (5.1). MVP siempre recalcula."},
        201: {"model": RiesgoContagioResponse, "description": "Nuevo cálculo: entradas o configuración cambiantes recalculan sin esperar 5 s (CA-4/5.1)"},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "LOTE_NO_ENCONTRADO"},
        422: {"model": ErrorResponse, "description": (
            "CONFIGURACION_CONTAGIO_NO_DEFINIDA, ERROR_CONFIGURACION_PESOS, ERROR_DATOS_INSUFICIENTES "
            "(E4/E5/E8/CA-10: cobertura individual mínima 60 %) o ERROR_DATOS_DESINCRONIZADOS (> 35 s)"
        )},
    },
    summary="Ejecutar el modelo de riesgo de contagio de un lote (RF-68)",
)
def estimar_riesgo_contagio(
    dto: EstimarRiesgoContagioDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> JSONResponse:
    """P = W_fs·Fs + W_fa·Fa + W_fd·Fd con los pesos y rangos de RF-65, discretizado en
    Bajo/Medio/Alto (Medio desde 0.50, Alto desde umbral_riesgo_alto de RF-65).
    Con Alto, confianza normal y probabilidad >= umbral_alerta_critica genera la
    alerta RIESGO_CONTAGIO en RF-57 (`alerta_id`).
    Una densidad negativa usa el promedio temporal registrado de 30 días (E2); sin
    histórico útil usa capacidad máxima con confianza baja. Una densidad nula
    conserva el preventivo existente."""
    resultado = EstimarRiesgoContagioUseCase(
        db=db,
        config_repo=SqlAlchemyConfiguracionMotorIARepository(db),
        resultado_repo=SqlAlchemyResultadoRiesgoContagioRepository(db),
        activo_port=ActivoBiologicoM02Adapter(db),
        ocupacion_port=OcupacionLoteM02Adapter(db),
        alerta_port=AlertaContagioRf57Adapter(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    ).execute(dto, usuario_actual.id_usuario, usuario_actual.id_rol)
    return JSONResponse(
        content=RiesgoContagioResponse.from_resultado(resultado).model_dump(mode="json"),
        status_code=200 if resultado.desde_cache else 201,
    )


@router.get(
    "",
    response_model=list[RiesgoContagioMonitorResponse],
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Cálculos de riesgo de contagio en las fincas del usuario (RF-68)",
)
def listar_riesgo_contagio(
    nivel_riesgo: Optional[int] = Query(default=None, description="0 a 3"),
    desde: Optional[FechaHoraUtc] = Query(default=None),
    hasta: Optional[FechaHoraUtc] = Query(default=None),
    limite: int = Query(default=50, description="Máximo 200; los más recientes primero."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> list[RiesgoContagioMonitorResponse]:
    fincas = AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(usuario_actual.id_usuario, usuario_actual.id_rol)
    items = ListarRiesgoContagioUseCase(SqlAlchemyMonitorPrediccionRepository(db)).execute(
        ids_fincas=fincas, nivel_riesgo=nivel_riesgo, desde=desde, hasta=hasta, limite=limite,
    )
    return [RiesgoContagioMonitorResponse.model_validate(i) for i in items]
