"""Router FastAPI para umbrales ambientales (`/configuracion/umbrales`).

Flujos RF-17 CU03:
  A) POST   /configuracion/umbrales              — Registrar umbral + niveles
  B) PATCH  /configuracion/umbrales/{id}         — Editar umbral + reemplazar niveles
  C) GET    /configuracion/umbrales              — Consultar por especie
  D) PATCH  /configuracion/umbrales/{id}/desactivar — Desactivar umbral

Autorización RBAC:
  recurso umbrales_ambientales = id_recurso 20
  C=1, R=2, U=3, D=4
  Roles autorizados: Administrador (1) y Veterinario (3).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.umbrales.consultar_umbrales_use_case import ConsultarUmbralesUseCase
from src.configuration.application.use_cases.umbrales.desactivar_umbral_use_case import DesactivarUmbralUseCase
from src.configuration.application.use_cases.umbrales.editar_umbral_use_case import EditarUmbralUseCase
from src.configuration.application.use_cases.umbrales.registrar_umbral_use_case import RegistrarUmbralUseCase
from src.configuration.infrastructure.dto.editar_umbral_dto import EditarUmbralDTO
from src.configuration.infrastructure.dto.registrar_umbral_dto import RegistrarUmbralDTO
from src.configuration.infrastructure.repositories.auditoria_umbral_repository import SqlAlchemyAuditoriaUmbralRepository
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.configuration.infrastructure.repositories.umbral_ambiental_repository import SqlAlchemyUmbralAmbientalRepository
from src.configuration.infrastructure.repositories.variable_ambiental_repository import SqlAlchemyVariableAmbientalRepository
from src.configuration.infrastructure.schema.umbral_schema import UmbralAmbientalResponse, UmbralesPorEspecieResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix='/configuracion/umbrales', tags=['Configuración - Umbrales Ambientales'])

_RECURSO = 20  # modulo1.recursos: 'umbrales_ambientales'


@router.post(
    '',
    response_model=UmbralAmbientalResponse,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 1))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        409: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Registrar umbral ambiental con niveles de alerta (Flujo A)',
)
def registrar_umbral(
    dto: RegistrarUmbralDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> UmbralAmbientalResponse:
    use_case = RegistrarUmbralUseCase(
        db=db,
        umbral_repo=SqlAlchemyUmbralAmbientalRepository(db),
        especie_repo=SqlAlchemyEspecieRepository(db),
        variable_repo=SqlAlchemyVariableAmbientalRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaUmbralRepository(db),
    )
    umbral = use_case.execute(dto, usuario_actual)
    return UmbralAmbientalResponse.model_validate(umbral)


@router.get(
    '',
    response_model=UmbralesPorEspecieResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
    },
    summary='Consultar umbrales ambientales por especie (Flujo C)',
)
def consultar_umbrales(
    id_especie: int = Query(..., description='ID de la especie a consultar.'),
    solo_activas: bool = Query(False, description='Si es true, solo devuelve umbrales activos.'),
    db: Session = Depends(get_db),
) -> UmbralesPorEspecieResponse:
    use_case = ConsultarUmbralesUseCase(umbral_repo=SqlAlchemyUmbralAmbientalRepository(db))
    umbrales = use_case.execute(id_especie, solo_activas=solo_activas)
    items = [UmbralAmbientalResponse.model_validate(u) for u in umbrales]
    return UmbralesPorEspecieResponse(total=len(items), items=items)


@router.patch(
    '/{id_umbral_ambiental}',
    response_model=UmbralAmbientalResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        412: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Editar umbral ambiental y reemplazar niveles de alerta (Flujo B)',
)
def editar_umbral(
    id_umbral_ambiental: int,
    dto: EditarUmbralDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> UmbralAmbientalResponse:
    use_case = EditarUmbralUseCase(
        db=db,
        umbral_repo=SqlAlchemyUmbralAmbientalRepository(db),
        variable_repo=SqlAlchemyVariableAmbientalRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaUmbralRepository(db),
    )
    umbral = use_case.execute(id_umbral_ambiental, dto, usuario_actual)
    return UmbralAmbientalResponse.model_validate(umbral)


@router.patch(
    '/{id_umbral_ambiental}/desactivar',
    response_model=UmbralAmbientalResponse,
    dependencies=[Depends(require_permission(_RECURSO, 4))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        422: {'model': ErrorResponse},
    },
    summary='Desactivar umbral ambiental (Flujo D)',
)
def desactivar_umbral(
    id_umbral_ambiental: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> UmbralAmbientalResponse:
    use_case = DesactivarUmbralUseCase(
        db=db,
        umbral_repo=SqlAlchemyUmbralAmbientalRepository(db),
        auditoria_repo=SqlAlchemyAuditoriaUmbralRepository(db),
    )
    umbral = use_case.execute(id_umbral_ambiental, usuario_actual)
    return UmbralAmbientalResponse.model_validate(umbral)
