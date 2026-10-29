# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
"""Router FastAPI del Modelo 4 — riesgo de contagio (RF-68).

  POST /prediccion/riesgo-contagio — Ejecutar el modelo para un lote

Auth: JWT Bearer + RBAC sobre el recurso 41 (configuracion_motor_ia), acción 5 (Ejecutar).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import (
    EstimarRiesgoContagioUseCase,
)
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
from src.prediction.infrastructure.schema.riesgo_contagio_schema import RiesgoContagioResponse
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
        200: {"model": RiesgoContagioResponse, "description": "Mismas entradas en menos de 5 s: resultado en caché (5.1)"},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "LOTE_NO_ENCONTRADO"},
        422: {"model": ErrorResponse, "description": (
            "CONFIGURACION_CONTAGIO_NO_DEFINIDA, ERROR_CONFIGURACION_PESOS, ERROR_DATOS_INSUFICIENTES "
            "(E4/E5/CA-10) o ERROR_DATOS_DESINCRONIZADOS (> 35 s)"
        )},
        429: {"model": ErrorResponse, "description": "EJECUCION_CONTAGIO_MUY_FRECUENTE: < 5 s desde la anterior"},
    },
    summary="Ejecutar el modelo de riesgo de contagio de un lote (RF-68)",
)
def estimar_riesgo_contagio(
    dto: EstimarRiesgoContagioDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> JSONResponse:
    """P = W_fs·Fs + W_fa·Fa + W_fd·Fd con los pesos y rangos de RF-65, discretizado en
    Bajo/Medio/Alto (fronteras 0.50 y 0.70). Con Alto y confianza normal genera la alerta
    RIESGO_CONTAGIO en RF-57 (`alerta_id`)."""
    resultado = EstimarRiesgoContagioUseCase(
        db=db,
        config_repo=SqlAlchemyConfiguracionMotorIARepository(db),
        resultado_repo=SqlAlchemyResultadoRiesgoContagioRepository(db),
        activo_port=ActivoBiologicoM02Adapter(db),
        alerta_port=AlertaContagioRf57Adapter(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    ).execute(dto, usuario_actual.id_usuario, usuario_actual.id_rol)
    return JSONResponse(
        content=RiesgoContagioResponse.from_resultado(resultado).model_dump(mode="json"),
        status_code=200 if resultado.desde_cache else 201,
    )
