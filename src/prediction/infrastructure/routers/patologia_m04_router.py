"""Router FastAPI para el catálogo de patologías M04 (`/prediccion/patologias`).

RF-64 CU-01: gestión del catálogo de patologías por especie.
  POST   /prediccion/patologias              — Registrar patología
  GET    /prediccion/patologias              — Listar patologías (filtros: especie, activas, base)
  GET    /prediccion/patologias/{id}         — Detalle de patología
  PATCH  /prediccion/patologias/{id}         — Editar patología
  PATCH  /prediccion/patologias/{id}/desactivar — Desactivar patología

Autorización RBAC:
  recurso patologias = id_recurso 18
  C=1 (Administrador, Veterinario), R=2, U=3, D=4
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.catalogo_patologias.consultar_patologias_use_case import ConsultarPatologiasUseCase
from src.prediction.application.use_cases.catalogo_patologias.desactivar_patologia_use_case import DesactivarPatologiaUseCase
from src.prediction.application.use_cases.catalogo_patologias.editar_patologia_use_case import EditarPatologiaUseCase
from src.prediction.application.use_cases.catalogo_patologias.obtener_patologia_use_case import ObtenerPatologiaUseCase
from src.prediction.application.use_cases.catalogo_patologias.registrar_patologia_use_case import RegistrarPatologiaUseCase
from src.prediction.infrastructure.adapters.especie_m09_adapter import EspecieM09Adapter
from src.prediction.infrastructure.adapters.modelo_activo_stub_adapter import ModeloActivoStubAdapter
from src.prediction.infrastructure.adapters.variable_i3p1_m09_adapter import VariableI3P1M09Adapter
from src.prediction.infrastructure.dto.editar_patologia_dto import EditarPatologiaDTO
from src.prediction.infrastructure.dto.registrar_patologia_dto import RegistrarPatologiaDTO
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.repositories.historial_catalogo_repository import SqlAlchemyHistorialCatalogoRepository
from src.prediction.infrastructure.repositories.patologia_m04_repository import SqlAlchemyPatologiaM04Repository
from src.prediction.infrastructure.schema.patologia_m04_schema import PatologiaM04ListResponse, PatologiaM04Response
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion/patologias", tags=["Predicción M04 - Catálogo de Patologías"])

_RECURSO = 18  # modulo1.recursos: 'patologias'


@router.post(
    "",
    response_model=PatologiaM04Response,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar patología en el catálogo M04 (RF-64)",
)
def registrar_patologia(
    dto: RegistrarPatologiaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PatologiaM04Response:
    use_case = RegistrarPatologiaUseCase(
        db=db,
        repo=SqlAlchemyPatologiaM04Repository(db),
        historial_repo=SqlAlchemyHistorialCatalogoRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        variable_port=VariableI3P1M09Adapter(db),
        especie_port=EspecieM09Adapter(db),
    )
    entidad = use_case.execute(dto, usuario_actual.id_usuario)
    return PatologiaM04Response.from_entity(entidad)


@router.get(
    "",
    response_model=PatologiaM04ListResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Listar catálogo de patologías M04 (RF-64)",
)
def listar_patologias(
    especie_aplicable: Optional[str] = Query(None, description="Filtrar por especie ('TODAS' o id_especie)."),
    solo_activas: Optional[bool] = Query(None, description="Si true, solo patologías activas."),
    solo_base: Optional[bool] = Query(None, description="Si true, solo patologías base."),
    db: Session = Depends(get_db),
) -> PatologiaM04ListResponse:
    use_case = ConsultarPatologiasUseCase(repo=SqlAlchemyPatologiaM04Repository(db))
    items = use_case.execute(especie_aplicable=especie_aplicable, solo_activas=solo_activas, solo_base=solo_base)
    return PatologiaM04ListResponse(
        total=len(items),
        items=[PatologiaM04Response.from_entity(e) for e in items],
    )


@router.get(
    "/{id_patologia}",
    response_model=PatologiaM04Response,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Obtener detalle de una patología M04 (RF-64)",
)
def obtener_patologia(
    id_patologia: int,
    db: Session = Depends(get_db),
) -> PatologiaM04Response:
    use_case = ObtenerPatologiaUseCase(repo=SqlAlchemyPatologiaM04Repository(db))
    entidad = use_case.execute(id_patologia)
    return PatologiaM04Response.from_entity(entidad)


@router.patch(
    "/{id_patologia}",
    response_model=PatologiaM04Response,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Editar patología del catálogo M04 (RF-64)",
)
def editar_patologia(
    id_patologia: int,
    dto: EditarPatologiaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PatologiaM04Response:
    use_case = EditarPatologiaUseCase(
        db=db,
        repo=SqlAlchemyPatologiaM04Repository(db),
        historial_repo=SqlAlchemyHistorialCatalogoRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        variable_port=VariableI3P1M09Adapter(db),
        modelo_activo_port=ModeloActivoStubAdapter(),
    )
    entidad = use_case.execute(id_patologia, dto, usuario_actual.id_usuario)
    return PatologiaM04Response.from_entity(entidad)


@router.patch(
    "/{id_patologia}/desactivar",
    response_model=PatologiaM04Response,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Desactivar patología del catálogo M04 (RF-64)",
)
def desactivar_patologia(
    id_patologia: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PatologiaM04Response:
    use_case = DesactivarPatologiaUseCase(
        db=db,
        repo=SqlAlchemyPatologiaM04Repository(db),
        historial_repo=SqlAlchemyHistorialCatalogoRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        modelo_activo_port=ModeloActivoStubAdapter(),
    )
    entidad = use_case.execute(id_patologia, usuario_actual.id_usuario)
    return PatologiaM04Response.from_entity(entidad)
