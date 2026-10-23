# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-25 RF-17: PATCH /{id} marca es_critica, solo Administrador (RFC-016) |
"""Router FastAPI para el catálogo de variables ambientales (`/configuracion/variables-ambientales`).

Catálogo predefinido (RF-17) — el mismo consumido por
`/configuracion/umbrales` para validar rango físico y contigüidad de niveles
de alerta. Comparte el recurso RBAC `umbrales_ambientales` porque solo tiene
sentido para quien ya puede ver/gestionar umbrales.

RFC-016 B.7: `PATCH /{id}` marca la variable como crítica; solo el Administrador
tiene U sobre el recurso (DB-08).

Autorización RBAC:
  recurso umbrales_ambientales = id_recurso 20
  R = 2, U = 3
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.umbrales.actualizar_variable_critica_use_case import (
    ActualizarVariableCriticaUseCase,
)

from src.configuration.application.use_cases.umbrales.listar_variables_ambientales_use_case import (
    ListarVariablesAmbientalesUseCase,
)
from src.configuration.infrastructure.dto.actualizar_variable_ambiental_dto import ActualizarVariableAmbientalDTO
from src.configuration.infrastructure.repositories.variable_ambiental_repository import (
    SqlAlchemyVariableAmbientalRepository,
)
from src.configuration.infrastructure.schema.umbral_schema import VariableAmbientalResponse, VariablesAmbientalesResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix='/configuracion/variables-ambientales', tags=['Configuración - Variables Ambientales'])

_RECURSO = 20  # modulo1.recursos: 'umbrales_ambientales'


@router.get(
    '',
    response_model=VariablesAmbientalesResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
    },
    summary='Consultar catálogo de variables ambientales activas',
)
def consultar_variables_ambientales(db: Session = Depends(get_db)) -> VariablesAmbientalesResponse:
    """Catálogo de variables ambientales activas con su unidad y rango físico (RF-17).

    **Acceso:** `umbrales_ambientales` · Leer.
    """
    use_case = ListarVariablesAmbientalesUseCase(variable_repo=SqlAlchemyVariableAmbientalRepository(db))
    variables = use_case.execute()
    items = [VariableAmbientalResponse.model_validate(v) for v in variables]
    return VariablesAmbientalesResponse(total=len(items), items=items)


@router.patch(
    '/{id_variable_ambiental}',
    response_model=VariableAmbientalResponse,
    dependencies=[Depends(require_permission(_RECURSO, 3))],
    responses={
        401: {'model': ErrorResponse},
        403: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
    },
    summary='Marcar o desmarcar una variable ambiental como crítica (RFC-016)',
)
def actualizar_variable_critica(
    id_variable_ambiental: int,
    dto: ActualizarVariableAmbientalDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VariableAmbientalResponse:
    """Una lectura de una variable crítica entra como crítica en la cola de ingesta del
    broker (RF-53 E15), sin importar su nivel de umbral. El cambio queda auditado.

    **Acceso:** `umbrales_ambientales` · Actualizar (solo Administrador).
    """
    use_case = ActualizarVariableCriticaUseCase(
        db=db,
        variable_repo=SqlAlchemyVariableAmbientalRepository(db),
        eventos_repo=SqlAlchemyEventoRepository(db),
    )
    variable = use_case.execute(id_variable_ambiental, dto.es_critica, usuario_actual)
    return VariableAmbientalResponse.model_validate(variable)
