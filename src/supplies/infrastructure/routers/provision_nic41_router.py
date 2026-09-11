"""Router FastAPI para la provisión de costos NIC-41 (`/suministros/nic41`).

Expone los flujos de RF-79 (CU-05):
  POST   /suministros/nic41/ciclo/{id_gestion_fases}/consolidar         — Consolidar al cierre del ciclo
  POST   /suministros/nic41/ciclo/{id_gestion_fases}/consolidar-manual  — Provisión ad-hoc (auditoría/recálculo)
  POST   /suministros/nic41/{id_provision}/correccion                  — Nueva versión de un reporte
  GET    /suministros/nic41/{id_provision}                             — Consultar un reporte (paginado)
  GET    /suministros/nic41/ciclo/{id_gestion_fases}/versiones         — Listar la cadena de versiones

Autorización delegada al RBAC centralizado (``src/shared/rbac.py``):
  recurso ``provision_nic41`` = id_recurso 56; acciones E=5, R=2.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.supplies.infrastructure.dto.corregir_provision_dto import CorregirProvisionDTO
from src.supplies.infrastructure.factories.provision_nic41_factory import (
    build_consolidar_ciclo_use_case,
    build_consultar_provision_use_case,
    build_corregir_provision_use_case,
    build_generar_provision_manual_use_case,
    build_listar_versiones_provision_use_case,
)
from src.supplies.infrastructure.schema.provision_nic41_schema import (
    ListaVersionesProvisionResponse,
    ProvisionNic41Response,
)

router = APIRouter(prefix="/suministros/nic41", tags=["Suministros - Provisión NIC-41 (RF-79)"])

_RECURSO = 56  # modulo1.recursos: 'provision_nic41'


@router.post(
    "/ciclo/{id_gestion_fases}/consolidar",
    response_model=ProvisionNic41Response,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Consolidar el reporte NIC-41 al cierre de una instancia de ciclo (RF-79)",
)
def consolidar_ciclo(
    id_gestion_fases: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ProvisionNic41Response:
    use_case = build_consolidar_ciclo_use_case(db)
    resultado = use_case.execute(id_gestion_fases, usuario_actual)
    return ProvisionNic41Response.desde_entidad(resultado)


@router.post(
    "/ciclo/{id_gestion_fases}/consolidar-manual",
    response_model=ProvisionNic41Response,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Generar una provisión CONSOLIDADO manual ad-hoc, sin exigir cierre (RF-79)",
)
def consolidar_ciclo_manual(
    id_gestion_fases: int,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ProvisionNic41Response:
    use_case = build_generar_provision_manual_use_case(db)
    resultado = use_case.execute(id_gestion_fases, usuario_actual)
    return ProvisionNic41Response.desde_entidad(resultado)


@router.post(
    "/{id_provision}/correccion",
    response_model=ProvisionNic41Response,
    status_code=201,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Generar una nueva versión de un reporte consolidado NIC-41 (RF-79 E4)",
)
def corregir_provision(
    id_provision: int,
    dto: CorregirProvisionDTO,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ProvisionNic41Response:
    use_case = build_corregir_provision_use_case(db)
    resultado = use_case.execute(id_provision, dto.motivo_correccion, usuario_actual)
    return ProvisionNic41Response.desde_entidad(resultado)


@router.get(
    "/{id_provision}",
    response_model=ProvisionNic41Response,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Consultar un reporte consolidado NIC-41 (lista_registros paginada)",
)
def consultar_provision(
    id_provision: int,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ProvisionNic41Response:
    use_case = build_consultar_provision_use_case(db)
    resultado = use_case.execute(id_provision)
    return ProvisionNic41Response.desde_entidad(resultado, pagina=pagina, por_pagina=por_pagina)


@router.get(
    "/ciclo/{id_gestion_fases}/versiones",
    response_model=ListaVersionesProvisionResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Listar la cadena de versiones del reporte consolidado de una instancia de ciclo (RF-79)",
)
def listar_versiones_provision(
    id_gestion_fases: int,
    db: Session = Depends(get_db),
) -> ListaVersionesProvisionResponse:
    use_case = build_listar_versiones_provision_use_case(db)
    versiones = use_case.execute(id_gestion_fases)
    # lista_registros vacía en el listado — solo metadatos de cada versión.
    items = [ProvisionNic41Response.desde_entidad(v, pagina=1, por_pagina=0) for v in versiones]
    return ListaVersionesProvisionResponse(total=len(items), versiones=items)
