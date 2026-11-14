# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Router de ciclos productivos (`/configuracion/ciclos-productivos`, RF-16).

Un ciclo productivo ordena etapas de la especie; RF-37 lo usa para abrir y avanzar las fases de un activo,
y M05 exige ese ciclo abierto para registrar alimento y medicamento (RF-75, RF-76).

Acceso: recurso ``ciclos_biologicos`` (17), el mismo de las etapas: Administrador y Veterinario.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.ciclos_productivos.editar_ciclo_productivo_use_case import (
    EditarCicloProductivoUseCase,
)
from src.configuration.application.use_cases.ciclos_productivos.eliminar_ciclo_productivo_use_case import (
    EliminarCicloProductivoUseCase,
)
from src.configuration.application.use_cases.ciclos_productivos.listar_ciclos_productivos_use_case import (
    ListarCiclosProductivosUseCase,
)
from src.configuration.application.use_cases.ciclos_productivos.registrar_ciclo_productivo_use_case import (
    RegistrarCicloProductivoUseCase,
)
from src.configuration.infrastructure.dto.ciclo_productivo_dto import (
    EditarCicloProductivoDTO,
    RegistrarCicloProductivoDTO,
)
from src.configuration.infrastructure.repositories.ciclo_biologico_repository import SqlAlchemyCicloBiologicoRepository
from src.configuration.infrastructure.repositories.ciclo_productivo_repository import (
    SqlAlchemyCicloProductivoRepository,
)
from src.configuration.infrastructure.repositories.especie_repository import SqlAlchemyEspecieRepository
from src.configuration.infrastructure.schema.ciclo_productivo_schema import (
    CicloProductivoResponse,
    CiclosProductivosResponse,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/ciclos-productivos", tags=["Configuración - Ciclos Productivos"])

_RECURSO = 17  # modulo1.recursos: 'ciclos_biologicos'
_ERRORES = {c: {"model": ErrorResponse} for c in (400, 401, 403, 404, 409, 422)}


@router.get("", response_model=CiclosProductivosResponse, dependencies=[Depends(require_permission(_RECURSO, 2))],
            responses=_ERRORES, summary="Ciclos productivos de una especie con sus fases en orden")
def listar_ciclos_productivos(id_especie: int = Query(..., gt=0), db: Session = Depends(get_db)) -> CiclosProductivosResponse:
    items = [CicloProductivoResponse.desde(c)
             for c in ListarCiclosProductivosUseCase(SqlAlchemyCicloProductivoRepository(db)).execute(id_especie)]
    return CiclosProductivosResponse(total=len(items), items=items)


@router.post("", status_code=201, response_model=CicloProductivoResponse,
             dependencies=[Depends(require_permission(_RECURSO, 1))], responses=_ERRORES,
             summary="Registrar un ciclo productivo con sus fases en orden")
def registrar_ciclo_productivo(dto: RegistrarCicloProductivoDTO, db: Session = Depends(get_db),
                               usuario_actual: UsuarioActual = Depends(get_current_user)) -> CicloProductivoResponse:
    ciclo = RegistrarCicloProductivoUseCase(
        db, SqlAlchemyCicloProductivoRepository(db), SqlAlchemyCicloBiologicoRepository(db), SqlAlchemyEspecieRepository(db),
    ).execute(dto.id_especie, dto.nombre, dto.id_ciclos_biologicos)
    return CicloProductivoResponse.desde(ciclo)


@router.put("/{id_ciclo_productivo}", response_model=CicloProductivoResponse,
            dependencies=[Depends(require_permission(_RECURSO, 3))], responses=_ERRORES,
            summary="Editar nombre y fases (si ya hay activos en el ciclo, solo el nombre)")
def editar_ciclo_productivo(id_ciclo_productivo: int, dto: EditarCicloProductivoDTO, db: Session = Depends(get_db),
                            usuario_actual: UsuarioActual = Depends(get_current_user)) -> CicloProductivoResponse:
    ciclo = EditarCicloProductivoUseCase(
        db, SqlAlchemyCicloProductivoRepository(db), SqlAlchemyCicloBiologicoRepository(db),
    ).execute(id_ciclo_productivo, dto.nombre, dto.id_ciclos_biologicos)
    return CicloProductivoResponse.desde(ciclo)


@router.delete("/{id_ciclo_productivo}", status_code=204, dependencies=[Depends(require_permission(_RECURSO, 4))],
               responses=_ERRORES, summary="Eliminar un ciclo productivo que ningún activo ha usado")
def eliminar_ciclo_productivo(id_ciclo_productivo: int, db: Session = Depends(get_db),
                              usuario_actual: UsuarioActual = Depends(get_current_user)) -> Response:
    EliminarCicloProductivoUseCase(db, SqlAlchemyCicloProductivoRepository(db)).execute(id_ciclo_productivo)
    return Response(status_code=204)
