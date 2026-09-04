"""Router FastAPI para el catálogo de variables ambientales (`/configuracion/variables-ambientales`).

Catálogo predefinido y de solo lectura (RF-17) — el mismo consumido por
`/configuracion/umbrales` para validar rango físico y contigüidad de niveles
de alerta. Comparte el recurso RBAC `umbrales_ambientales` porque solo tiene
sentido para quien ya puede ver/gestionar umbrales.

Autorización RBAC:
  recurso umbrales_ambientales = id_recurso 20
  R = 2
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.umbrales.listar_variables_ambientales_use_case import (
    ListarVariablesAmbientalesUseCase,
)
from src.configuration.infrastructure.repositories.variable_ambiental_repository import (
    SqlAlchemyVariableAmbientalRepository,
)
from src.configuration.infrastructure.schema.umbral_schema import VariableAmbientalResponse, VariablesAmbientalesResponse
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
    use_case = ListarVariablesAmbientalesUseCase(variable_repo=SqlAlchemyVariableAmbientalRepository(db))
    variables = use_case.execute()
    items = [VariableAmbientalResponse.model_validate(v) for v in variables]
    return VariablesAmbientalesResponse(total=len(items), items=items)
