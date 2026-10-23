"""Router de la calibración por visión (RF-24 v2.0, modalidad VISION, RFC-011).

Endpoints:
  POST  /configuracion/calibraciones-vision                    — Calcular la línea base de un área (disparo manual)
  GET   /configuracion/calibraciones-vision?area_id=           — Historial de cálculos del área
  GET   /configuracion/calibraciones-vision/linea-base?area_id= — Línea base vigente del área

Mismo recurso RBAC que la calibración SENSOR (12, 'sensores'): crear para
calcular, leer para consultar.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import (
    MENSAJE_ACCESO_DENEGADO,
    CalibrarVisionUseCase,
    ConsultarCalibracionVisionUseCase,
    auditar_rechazo_vision,
)
from src.configuration.infrastructure.adapters.observacion_vision_m03_adapter import ObservacionVisionM03Adapter
from src.configuration.infrastructure.dto.calibrar_vision_dto import CalibrarVisionDTO
from src.configuration.infrastructure.repositories.calibracion_vision_repository import (
    SqlAlchemyCalibracionVisionRepository,
    SqlAlchemyLineaBaseVisionRepository,
)
from src.configuration.infrastructure.repositories.camara_area_repository import SqlAlchemyCamaraAreaRepository
from src.configuration.infrastructure.repositories.infraestructura_repository import (
    SqlAlchemyInfraestructuraRepository,
)
from src.configuration.infrastructure.schema.calibracion_vision_schema import (
    CalibracionVisionResponse,
    LineaBaseVisionResponse,
    ListaCalibracionesVisionResponse,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import get_db
from src.shared.errors import AuthorizationError
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

# HTTPBearer solo documenta el esquema de seguridad en el OpenAPI (QA lo revisa
# en el preflight de #514); auto_error=False para no cambiar nada: quien valida
# el token sigue siendo get_current_user.
router = APIRouter(
    prefix="/configuracion/calibraciones-vision",
    tags=["Configuración - Calibración por visión"],
    dependencies=[Depends(HTTPBearer(auto_error=False))],
)

_RECURSO = 12  # modulo1.recursos: 'sensores' (el mismo de la calibración SENSOR)


def _alcance(db: Session, usuario_actual: UsuarioActual) -> list[int] | None:
    return AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(
        usuario_actual.id_usuario, usuario_actual.id_rol
    )


def _permiso_calibrar_auditado(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> None:
    """Compuerta RBAC con el mensaje 403 de la ficha; el 403 también se audita (RFC-006).

    Corre como dependencia, antes de validar el body: un rol sin permiso recibe
    403 aunque el body sea inválido. Por eso el evento no lleva el área.
    """
    try:
        require_permission(_RECURSO, 1, mensaje_denegado=MENSAJE_ACCESO_DENEGADO)(
            db=db, usuario_actual=usuario_actual
        )
    except AuthorizationError as exc:
        auditar_rechazo_vision(
            db,
            SqlAlchemyEventoRepository(db),
            id_usuario=usuario_actual.id_usuario,
            id_infraestructura=None,
            error=exc,
        )
        raise


@router.post(
    "",
    response_model=CalibracionVisionResponse,
    status_code=201,
    dependencies=[Depends(_permiso_calibrar_auditado)],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Calibrar por visión: calcular la línea base de un área (RF-24 v2.0, modalidad VISION)",
)
def calibrar_vision(
    dto: CalibrarVisionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> CalibracionVisionResponse:
    """Calcula la línea base por visión de un área para su especie con las observaciones de sus cámaras (RF-24, modalidad VISION).

    **Acceso:** `sensores` · Crear.

    Si converge publica la nueva línea base; un cálculo fallido devuelve el estado y la etapa donde falló. Los rechazos por permiso también quedan auditados.
    """
    use_case = CalibrarVisionUseCase(
        db=db,
        infraestructura_repo=SqlAlchemyInfraestructuraRepository(db),
        camara_repo=SqlAlchemyCamaraAreaRepository(db),
        observacion_port=ObservacionVisionM03Adapter(db),
        calibracion_repo=SqlAlchemyCalibracionVisionRepository(db),
        linea_base_repo=SqlAlchemyLineaBaseVisionRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
    )
    calibracion = use_case.execute(dto, usuario_actual, ids_fincas_permitidas=_alcance(db, usuario_actual))
    return CalibracionVisionResponse.from_entity(calibracion)


def _consultar(db: Session) -> ConsultarCalibracionVisionUseCase:
    return ConsultarCalibracionVisionUseCase(
        infraestructura_repo=SqlAlchemyInfraestructuraRepository(db),
        calibracion_repo=SqlAlchemyCalibracionVisionRepository(db),
        linea_base_repo=SqlAlchemyLineaBaseVisionRepository(db),
    )


@router.get(
    "",
    response_model=ListaCalibracionesVisionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Historial de calibraciones por visión de un área (RF-24 v2.0)",
)
def listar_calibraciones_vision(
    area_id: int = Query(...),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaCalibracionesVisionResponse:
    """Historial de calibraciones por visión de un área, exitosas y fallidas (RF-24).

    **Acceso:** `sensores` · Leer.
    """
    calibraciones = _consultar(db).listar_por_area(area_id, ids_fincas_permitidas=_alcance(db, usuario_actual))
    items = [CalibracionVisionResponse.from_entity(c) for c in calibraciones]
    return ListaCalibracionesVisionResponse(total=len(items), items=items)


@router.get(
    "/linea-base",
    response_model=LineaBaseVisionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Línea base por visión vigente de un área para su especie (RF-24 v2.0)",
)
def obtener_linea_base_vision(
    area_id: int = Query(...),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> LineaBaseVisionResponse:
    """Línea base por visión vigente del área para su especie (RF-24).

    **Acceso:** `sensores` · Leer.

    Responde 404 si el área nunca se calibró con éxito.
    """
    linea_base = _consultar(db).obtener_linea_base_vigente(
        area_id, ids_fincas_permitidas=_alcance(db, usuario_actual)
    )
    return LineaBaseVisionResponse.from_entity(linea_base)
