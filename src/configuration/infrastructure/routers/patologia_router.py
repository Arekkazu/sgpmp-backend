"""Router FastAPI para patologías por especie (`/configuracion/patologias`).

Expone los cuatro flujos de RF-16 CU02 para patologías por especie:
  E) POST   /configuracion/patologias              — Registrar patología para especie
  F) PATCH  /configuracion/patologias/{id}         — Editar patología de la especie
  G) PATCH  /configuracion/patologias/{id}/desactivar — Desactivar patología de la especie
  H) GET    /configuracion/patologias              — Consultar patologías por especie

El path param {id} es el id_especies_patologias (identidad de la patología por especie).

Autorización RBAC:
  recurso patologias = id_recurso 18
  C=1, R=2, U=3, D=4
  Roles autorizados: Administrador (1) y Veterinario (3).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.patologias.consultar_patologias_use_case import ConsultarPatologiasUseCase
from src.configuration.application.use_cases.patologias.desactivar_patologia_use_case import DesactivarPatologiaUseCase
from src.configuration.application.use_cases.patologias.editar_patologia_use_case import EditarPatologiaUseCase
from src.configuration.application.use_cases.patologias.registrar_patologia_use_case import RegistrarPatologiaUseCase
from src.configuration.infrastructure.dto.editar_patologia_dto import EditarPatologiaDTO
from src.configuration.infrastructure.dto.registrar_patologia_dto import RegistrarPatologiaDTO
from src.configuration.infrastructure.repositories.auditoria_patologia_repository import SqlAlchemyAuditoriaPatologiaRepository
from src.configuration.infrastructure.repositories.dependencia_patologia_repository import SqlAlchemyDependenciaPatologiaRepository
from src.configuration.infrastructure.repositories.especie_patologia_repository import SqlAlchemyEspeciePatologiaRepository
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.configuration.infrastructure.schema.patologia_schema import (
    PatologiaEspecieItemResponse,
    PatologiasPorEspecieResponse,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/patologias", tags=["Configuración - Patologías"])

_RECURSO = 18  # modulo1.recursos: 'patologias'


@router.post(
    "",
    response_model=PatologiaEspecieItemResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Registrar patología para especie (Flujo E)",
)
def registrar_patologia(
    dto: RegistrarPatologiaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PatologiaEspecieItemResponse:
    use_case = RegistrarPatologiaUseCase(
        db=db,
        especie_patologia_repo=SqlAlchemyEspeciePatologiaRepository(db),
        especies_repo=SqlAlchemyEspecieRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaPatologiaRepository(db),
    )
    patologia = use_case.execute(dto, usuario_actual)
    return PatologiaEspecieItemResponse.model_validate(patologia)


@router.get(
    "",
    response_model=PatologiasPorEspecieResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Consultar patologías por especie (Flujo H)",
)
def consultar_patologias(
    id_especie: int = Query(..., description="ID de la especie a consultar."),
    solo_activas: bool = Query(False, description="Si es true, solo devuelve patologías activas."),
    db: Session = Depends(get_db),
) -> PatologiasPorEspecieResponse:
    use_case = ConsultarPatologiasUseCase(
        especie_patologia_repo=SqlAlchemyEspeciePatologiaRepository(db),
    )
    patologias = use_case.execute(id_especie, solo_activas=solo_activas)
    items = [PatologiaEspecieItemResponse.model_validate(p) for p in patologias]
    return PatologiasPorEspecieResponse(total=len(items), items=items)


@router.patch(
    "/{id_especies_patologias}",
    response_model=PatologiaEspecieItemResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        412: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Editar patología por especie (Flujo F)",
)
def editar_patologia(
    id_especies_patologias: int,
    dto: EditarPatologiaDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PatologiaEspecieItemResponse:
    use_case = EditarPatologiaUseCase(
        db=db,
        especie_patologia_repo=SqlAlchemyEspeciePatologiaRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaPatologiaRepository(db),
    )
    patologia = use_case.execute(id_especies_patologias, dto, usuario_actual)
    return PatologiaEspecieItemResponse.model_validate(patologia)


@router.patch(
    "/{id_especies_patologias}/desactivar",
    response_model=PatologiaEspecieItemResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Desactivar patología por especie (Flujo G)",
)
def desactivar_patologia(
    id_especies_patologias: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PatologiaEspecieItemResponse:
    use_case = DesactivarPatologiaUseCase(
        db=db,
        especie_patologia_repo=SqlAlchemyEspeciePatologiaRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaPatologiaRepository(db),
        dependencia_port=SqlAlchemyDependenciaPatologiaRepository(db),
    )
    patologia = use_case.execute(id_especies_patologias, usuario_actual)
    return PatologiaEspecieItemResponse.model_validate(patologia)
